"""Bounded final-audit format helpers; never evaluate a physical map or gate.

Native HDF5 layout/preflight and owner hashing belong to the caller. Pass only
its bounded fixed-width UTF-8 payload, after removing right-hand NUL padding.
"""
from __future__ import annotations

import json
import math
import re
from importlib.resources import files

from .messages import ContractError

SCHEMA = 'qcl-negf-final-fixed-point-audit-v1'
MAX_FINAL_AUDIT_BYTES = 65536
_CHANNELS = ('LO', 'acoustic', 'impurity', 'IFR', 'alloy', 'electron_electron')
_CONTEXT_FIELDS = ('backend', 'energy_shift', 'hilbert', 'contraction', 'kernel_build',
                   'embedding', 'electron_electron_mode', 'embedding_periods',
                   'E0_eV', 'L0_m', 'lambda_P', 'map_kernels_shared_with_solver')
_IDENTITY_FIELDS = ('execution_id', 'point_id', 'state_id', 'attempt',
                    'state_sequence', 'plan_fingerprint')
_OPTIONAL = {('history', 'previous_lambda'), ('charge', 'lambda_change')}


def _fail(path: str, message: str) -> None:
    raise ContractError(f'final audit {path}: {message}')


def _pairs(pairs: list) -> dict:
    value = {}
    for key, item in pairs:
        if key in value:
            _fail('$', 'duplicate JSON key')
        value[key] = item
    return value


def _bad_constant(value: str) -> None:
    _fail('$', 'nonfinite JSON token')


def _budget(value: object, depth: int = 0, members: list | None = None) -> None:
    if members is None:
        members = [0]
    if depth > 9:
        _fail('$', 'depth exceeds 9')
    if isinstance(value, dict):
        members[0] += len(value)
        if members[0] > 1024:
            _fail('$', 'object members exceed 1024')
        for key, item in value.items():
            if not isinstance(key, str):
                _fail('$', 'object keys must be strings')
            _budget(key, depth + 1, members)
            _budget(item, depth + 1, members)
    elif isinstance(value, list):
        # No v1 array can have more than 27 entries. Bound traversal before
        # serializing a caller-supplied object, even if structurally malformed.
        if len(value) > 1024:
            _fail('$', 'array exceeds bounded record inventory')
        for item in value:
            _budget(item, depth + 1, members)
    elif isinstance(value, str):
        try:
            encoded = value.encode('utf-8', 'strict')
        except UnicodeError as error:
            raise ContractError('final audit: invalid UTF-8 string') from error
        if b'\0' in encoded or len(encoded) > 512:
            _fail('$', 'NUL or excessive string byte length')
    elif type(value) in (int, float):
        try:
            finite = math.isfinite(float(value))
        except (OverflowError, ValueError):
            finite = False
        if not finite:
            _fail('$', 'number is not finite Float64')
    elif value is not None and type(value) is not bool:
        _fail('$', 'unsupported JSON value')


def _matches_type(value: object, name: str) -> bool:
    return {
        'object': isinstance(value, dict), 'array': isinstance(value, list),
        'string': isinstance(value, str), 'null': value is None,
        'boolean': type(value) is bool, 'integer': type(value) is int,
        'number': type(value) in (int, float),
    }[name]


def _equal(left: object, right: object) -> bool:
    """IEEE64 equality for numeric measurements; strict bool and array semantics."""
    if type(left) is bool or type(right) is bool:
        return type(left) is type(right) and left == right
    if type(left) in (int, float) and type(right) in (int, float):
        return float(left) == float(right)
    if isinstance(left, dict) and isinstance(right, dict):
        return left.keys() == right.keys() and all(_equal(left[k], right[k]) for k in left)
    if isinstance(left, list) and isinstance(right, list):
        return len(left) == len(right) and all(_equal(a, b) for a, b in zip(left, right))
    return type(left) is type(right) and left == right


def _schema_check(value: object, spec: dict, root: dict, path: str = '$') -> None:
    """The bundled schema's small closed vocabulary, without a dependency."""
    if '$ref' in spec:
        _schema_check(value, root['$defs'][spec['$ref'].removeprefix('#/$defs/')], root, path)
        return
    for keyword, exact in (('anyOf', False), ('oneOf', True)):
        if keyword in spec:
            successes = 0
            for alternative in spec[keyword]:
                try:
                    _schema_check(value, alternative, root, path)
                    successes += 1
                except ContractError:
                    pass
            if (exact and successes != 1) or (not exact and successes == 0):
                _fail(path, f'{keyword} alternatives do not match')
    if 'type' in spec and not _matches_type(value, spec['type']):
        _fail(path, 'wrong JSON type')
    if 'const' in spec and not _equal(value, spec['const']):
        _fail(path, 'wrong constant')
    if 'enum' in spec and not any(_equal(value, choice) for choice in spec['enum']):
        _fail(path, 'unknown enum')
    if isinstance(value, dict):
        properties = spec.get('properties', {})
        if not set(spec.get('required', ())).issubset(value):
            _fail(path, 'missing field')
        if spec.get('additionalProperties') is False and set(value) - set(properties):
            _fail(path, 'unknown field')
        for key in value.keys() & properties.keys():
            _schema_check(value[key], properties[key], root, f'{path}.{key}')
    if isinstance(value, list):
        if len(value) < spec.get('minItems', 0) or len(value) > spec.get('maxItems', 1024):
            _fail(path, 'array inventory limit')
        if spec.get('uniqueItems') and any(value[i] in value[:i] for i in range(len(value))):
            _fail(path, 'duplicate array entry')
        if 'items' in spec:
            for item in value:
                _schema_check(item, spec['items'], root, f'{path}[]')
    if isinstance(value, str):
        length = len(value.encode('utf-8'))
        if length < spec.get('minLength', 0) or length > spec.get('maxLength', 512):
            _fail(path, 'UTF-8 byte limit')
        if 'pattern' in spec and re.fullmatch(spec['pattern'], value) is None:
            _fail(path, 'invalid string pattern')
    if type(value) in (int, float):
        if value < spec.get('minimum', -math.inf) or value > spec.get('maximum', math.inf):
            _fail(path, 'numeric bound')
        if 'exclusiveMinimum' in spec and value <= spec['exclusiveMinimum']:
            _fail(path, 'positive number required')


def _measurements(value: dict, path: tuple = ()):
    if set(value) == {'status', 'value', 'nonfinite', 'reason'}:
        yield path, value
    else:
        for key, item in value.items():
            if isinstance(item, dict):
                yield from _measurements(item, path + (key,))
            elif isinstance(item, list):
                for index, row in enumerate(item):
                    if isinstance(row, dict):
                        yield from _measurements(row, path + (key, index))


def _is_fresh(path: tuple) -> bool:
    return path[0] in {'dyson', 'spectral', 'keldysh', 'selfenergy'} or (
        path[0] == 'charge' and path[1] in {
            'candidate_raw_sheet', 'candidate_lambda', 'candidate_constraint'})


def _semantics(record: dict) -> None:
    context = record['context']
    unknown = [key for key in _CONTEXT_FIELDS if context[key] is None]
    if context['unknown_fields'] != unknown:
        _fail('context', 'unknown_fields must exactly list nullable unknowns in canonical order')
    if (context['status'], context['reason']) != (
            ('unknown', 'missing_executed_context') if unknown else ('known', None)):
        _fail('context', 'status contradicts executed context')
    if context['alignment_reason'] != (
            'producer_precondition_unverified' if context['state_alignment'] == 'unknown' else None):
        _fail('context', 'alignment reason contradicts alignment')
    channels = context['enabled_scattering']
    if channels != [key for key in _CHANNELS if key in channels]:
        _fail('context', 'noncanonical channel order')
    rows = record['selfenergy']['rows']
    inventory = [(family, component) for family in
                 (*channels, 'embedding_total', 'embedding_plus', 'embedding_minus')
                 for component in ('R', 'L', 'G')]
    if [(row['family'], row['component']) for row in rows] != inventory:
        _fail('selfenergy', 'rows must exactly match canonical requested inventory')

    mandatory = []
    for path, item in _measurements(record):
        status, value, reason = item['status'], item['value'], item['reason']
        optional = path in _OPTIONAL
        if not optional:
            mandatory.append((path, item))
        if status == 'not_applicable' and (not optional or reason != 'no_previous_inner_iteration'):
            _fail(str(path), 'only optional previous-history fields may be not_applicable')
        if status == 'unavailable':
            allowed = {'history_unavailable'} if optional else {'map_unavailable'}
            if path == ('charge', 'lambda_change') and record['record_status'] == 'unavailable':
                allowed.add('map_unavailable')
            if reason not in allowed:
                _fail(str(path), 'unavailable scope/reason mismatch')
        if status == 'error' and value is not None:
            if reason not in {'nonfinite_measurement', 'nonpositive_target',
                              'nonpositive_stored_raw'}:
                _fail(str(path), 'finite error requires an actual invalid measurement')
        if reason == 'nonpositive_target' and (
                path not in {('charge', 'target_sheet'), ('poisson', 'target_sheet')} or
                value is None or value > 0):
            _fail(str(path), 'nonpositive target reason/value mismatch')
        if reason == 'nonpositive_stored_raw' and (
                path != ('charge', 'stored_raw_sheet') or value is None or value > 0):
            _fail(str(path), 'nonpositive stored raw reason/value mismatch')
        if value is not None and value <= 0:
            domain_reason = ('nonpositive_target' if path in {
                ('charge', 'target_sheet'), ('poisson', 'target_sheet')} else
                'nonpositive_stored_raw' if path == ('charge', 'stored_raw_sheet') else None)
            if domain_reason is not None and (status, reason) != ('error', domain_reason):
                _fail(str(path), 'domain-invalid measurement requires its exact error reason')
        if value is not None:
            nonnegative = (path[0] in {'dyson', 'spectral', 'keldysh', 'selfenergy'} or
                path[0] == 'poisson' and path[-1] not in {'zeta_signed', 'neutrality_signed', 'target_sheet'} or
                path[0] == 'charge' and path[-1] in {
                    'stored_constraint', 'candidate_constraint', 'normalized_residual'})
            if nonnegative and value < 0:
                _fail(str(path), 'norm/scale/residual must be nonnegative')
            if status == 'measured' and path[-1] == 'denominator' and value <= 0:
                _fail(str(path), 'measured denominator must be positive')
            if status == 'measured' and path in {('charge', 'target_sheet'), ('poisson', 'target_sheet'),
                        ('charge', 'stored_raw_sheet')} and value <= 0:
                _fail(str(path), 'domain-invalid value must be retained as error')

    history = record['history']
    previous = history['previous_lambda']
    change = record['charge']['lambda_change']
    if history['inner_last'] is None:
        if history['inner_previous'] is not None:
            _fail('history', 'previous row without last row')
        expected_history = ('unavailable', 'history_unavailable')
    elif history['inner_previous'] is None:
        expected_history = ('not_applicable', 'no_previous_inner_iteration')
    else:
        if history['inner_previous'] >= history['inner_last']:
            _fail('history', 'previous iteration must precede last (not necessarily adjacent)')
        expected_history = None
    for item in (previous, change):
        if expected_history is not None:
            if (item['status'], item['reason']) != expected_history:
                _fail('history', 'optional measurement contradicts actual history availability')
        elif item['status'] not in {'measured', 'error'} and not (
                item is change and record['record_status'] == 'unavailable' and
                (item['status'], item['reason']) == ('unavailable', 'map_unavailable')):
            _fail('history', 'existing previous row cannot be optional/unavailable')

    for name in ('ratio_witness', 'absolute_witness'):
        witness = record['dyson'][name]
        status = witness['status']
        e_index, k_index = witness['e_index'], witness['k_index']
        if (e_index is None) != (k_index is None):
            _fail(name, 'witness coordinate pair must be complete or null')
        if e_index is not None and (e_index > record['shape']['NE'] or k_index > record['shape']['Nk']):
            _fail(name, 'witness outside represented shape')
        values = [item for _, item in _measurements(witness)]
        if status == 'measured' and (e_index is None or any(x['status'] != 'measured' for x in values)):
            _fail(name, 'measured witness requires coordinates and finite measured fields')
        if status == 'unavailable' and (e_index is not None or any(x['status'] != 'unavailable' for x in values)):
            _fail(name, 'unavailable witness requires null coordinates and unavailable fields')
        if status == 'error' and not any(x['status'] == 'error' for x in values):
            _fail(name, 'error witness requires an error measurement')
        denominator, ratio = witness['denominator'], witness['ratio']
        if denominator['nonfinite'] is not None and ratio['value'] is not None:
            if (ratio['status'], ratio['reason']) != ('error', 'nonfinite_measurement'):
                _fail(name, 'finite quotient with nonfinite normalization remains error')
    ratio_witness = record['dyson']['ratio_witness']
    if ratio_witness['denominator']['nonfinite'] is not None:
        ratio = record['dyson']['ratio']
        if ratio['value'] is not None and (ratio['status'], ratio['reason']) != (
                'error', 'nonfinite_measurement'):
            _fail('dyson.ratio', 'nonfinite witness normalization cannot become measured zero')

    row_ratios = [row['ratio'] for row in rows]
    winner = record['selfenergy']['winner']
    all_rows_measured = all(item['status'] == 'measured'
                            for row in rows for _, item in _measurements(row))
    if all(item['status'] == 'measured' for item in row_ratios):
        index = max(range(len(rows)), key=lambda i: float(row_ratios[i]['value']))
        expected = {key: rows[index][key] for key in ('family', 'component')}
        if winner != expected and (winner is not None or all_rows_measured):
            _fail('selfenergy.winner', 'first canonical maximum row required')
    elif winner is not None:
        _fail('selfenergy.winner', 'unavailable/error ratios require null winner')

    errors = any(item['status'] == 'error' for _, item in mandatory)
    unavailable = record['record_status'] == 'unavailable'
    if unavailable:
        for path, item in mandatory:
            if _is_fresh(path) and item['status'] != 'unavailable':
                _fail(str(path), 'unavailable map requires fresh-dependent unavailable fields')
        if any(record['dyson'][key]['status'] != 'unavailable'
               for key in ('ratio_witness', 'absolute_witness')):
            _fail('dyson', 'unavailable map requires unavailable witnesses')
    elif any(item['status'] in {'unavailable', 'not_applicable'} for _, item in mandatory):
        _fail('record_status', 'evaluated map requires mandatory measurements')
    expected_status = 'unavailable' if unavailable else 'partial_error' if errors else 'measured'
    expected_reason = {'unavailable': 'map_unavailable', 'partial_error': 'measurement_error',
                       'measured': None}[expected_status]
    if (record['record_status'], record['reason']) != (expected_status, expected_reason):
        _fail('record_status', 'contradicts mandatory measurement statuses')
    if not unavailable:
        charge = record['charge']

        def undefined(item: dict) -> bool:
            return (item['status'], item['value'], item['nonfinite'], item['reason']) == (
                'error', None, None, 'invalid_prerequisite')

        dependencies = []
        if charge['target_sheet']['status'] == 'error':
            dependencies.extend(('stored_lambda', 'stored_constraint', 'candidate_lambda',
                                 'candidate_constraint', 'normalized_residual'))
        if charge['stored_raw_sheet']['status'] == 'error':
            dependencies.extend(('stored_lambda', 'stored_constraint'))
        if charge['candidate_raw_sheet']['nonfinite'] is not None:
            dependencies.extend(('candidate_lambda', 'candidate_constraint'))
        for key in dependencies:
            if not undefined(charge[key]):
                _fail(f'charge.{key}', 'invalid prerequisite requires error/tagless null')
        if previous['status'] == 'error' and not undefined(change):
            _fail('charge.lambda_change', 'invalid previous lambda requires undefined change')
    if record['poisson']['target_sheet']['status'] == 'error':
        item = record['poisson']['neutrality_ratio']
        if (item['status'], item['value'], item['nonfinite'], item['reason']) != (
                'error', None, None, 'invalid_prerequisite'):
            _fail('poisson.neutrality_ratio', 'invalid target requires undefined ratio')


def _bind(record: dict, expected_identity: dict | None) -> None:
    if expected_identity is None:
        return
    if not isinstance(expected_identity, dict) or not all(k in expected_identity for k in _IDENTITY_FIELDS):
        _fail('state_identity', 'expected identity must supply all six binding fields')
    actual = record['state_identity']
    for key in _IDENTITY_FIELDS:
        expected = expected_identity[key]
        if type(actual[key]) is not type(expected) or actual[key] != expected:
            _fail('state_identity', f'{key} differs from actual commit/native identity')


def validate_final_audit(raw: bytes, *, expected_identity: dict | None = None) -> dict:
    """Decode bounded strict UTF-8 JSON and validate D2's portable record.

    ``expected_identity`` may be a larger actual commit identity; all six record
    fields must be present with exact types and values. No model defaults or
    acceptance conclusions are inferred. Return a newly decoded record.
    """
    if not isinstance(raw, bytes) or not 1 <= len(raw) <= MAX_FINAL_AUDIT_BYTES:
        _fail('$', 'bytes payload must contain 1..65536 bytes')
    try:
        text = raw.decode('utf-8', 'strict')
        if '\0' in text or text.startswith('\ufeff'):
            _fail('$', 'NUL/BOM forbidden')
        record = json.loads(text, object_pairs_hook=_pairs, parse_constant=_bad_constant)
    except (UnicodeError, ValueError, RecursionError) as error:
        raise ContractError('final audit: invalid strict UTF-8 JSON') from error
    _budget(record)
    schema = json.loads(files('qcl_negf_contracts').joinpath(
        'schemas/final-fixed-point-audit.schema.json').read_text(encoding='utf-8'))
    _schema_check(record, schema, schema)
    _semantics(record)
    _bind(record, expected_identity)
    return record


def _canonical_zero(value: object) -> object:
    if isinstance(value, dict):
        return {key: _canonical_zero(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_canonical_zero(item) for item in value]
    return 0.0 if type(value) is float and value == 0 else value


def encode_final_audit(record: dict, *, expected_identity: dict | None = None) -> bytes:
    """Validate and encode shortest-roundtrip JSON; canonicalize signed zero.

    Returns bytes for the same native/commit semantic record. It does not add
    identity: the caller must bind its actual identity before calling.
    """
    _budget(record)
    try:
        encoder = json.JSONEncoder(ensure_ascii=False, allow_nan=False, sort_keys=True,
                                   separators=(',', ':'))
        chunks, length = [], 0
        for chunk in encoder.iterencode(_canonical_zero(record)):
            encoded = chunk.encode('utf-8', 'strict')
            length += len(encoded)
            if length > MAX_FINAL_AUDIT_BYTES:
                _fail('$', 'encoded record exceeds byte budget')
            chunks.append(encoded)
        raw = b''.join(chunks)
    except (ValueError, TypeError, UnicodeError, RecursionError) as error:
        raise ContractError('final audit: cannot encode finite UTF-8 JSON') from error
    validate_final_audit(raw, expected_identity=expected_identity)
    return raw


def validate_final_audit_pair(native_raw: bytes | None, commit_record: dict | None, *,
                              expected_identity: dict, final_state: bool = True) -> dict:
    """Check presence, binding and exact native/commit semantic equality.

    Wrapper keys are ``record,status,reason``. Absent legacy final yields
    not_recorded; absent recovery yields not_applicable/not_a_final_state.
    Present final returns its measurement status, never acceptance/pass.
    The caller additionally binds native point identity and owner hashes.
    """
    if type(final_state) is not bool:
        _fail('$', 'final_state must be Boolean')
    if not final_state:
        if native_raw is not None or commit_record is not None:
            _fail('$', 'recovery must not publish a final audit')
        return {'record': None, 'status': 'not_applicable', 'reason': 'not_a_final_state'}
    if native_raw is None and commit_record is None:
        return {'record': None, 'status': 'not_recorded', 'reason': None}
    if native_raw is None or commit_record is None:
        _fail('$', 'native and commit record presence must agree')
    native = validate_final_audit(native_raw, expected_identity=expected_identity)
    commit = validate_final_audit(encode_final_audit(commit_record), expected_identity=expected_identity)
    if not _equal(native, commit):
        _fail('$', 'native and commit records differ')
    return {'record': native, 'status': native['record_status'], 'reason': native['reason']}
