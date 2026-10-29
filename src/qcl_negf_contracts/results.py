"""Strict result-v2 boundaries. Pure declarations, never file or scientific validation.

The caller decodes with an explicit byte budget and supplies checked immutable source
contexts. Referenced bytes, HDF5 datasets, exact Core semantics and acceptance are
verified by their owners. A syntactically valid SHA256 is not a verified hash.
"""
from __future__ import annotations

from functools import cache
from importlib.resources import files
import json
import math
import re
import struct

from . import schema_validator
from .artifacts import ARTIFACT_SCHEMA_CONTRACTS, CONTRACT_SET, NATIVE_SCHEMA_VERSION, Artifact, digest_value, relative_path
from .messages import ContractError, Object, encode, object_value

_SCHEMAS = {
    'manifest': ('result-manifest.schema.json', 'qcl-negf.result-manifest.v1'),
    'pointer': ('result-pointer.schema.json', 'qcl-negf.result-pointer.v1'),
    'catalog': ('scientific-catalog.schema.json', 'qcl-negf.scientific-catalog.v1'),
    'cursor': ('result-cursor.schema.json', 'qcl-negf.result-cursor.v1'),
    'checkpoint': ('checkpoint-declaration.schema.json', 'qcl-negf.checkpoint-declaration.v1'),
    'record': ('scientific-record.schema.json', 'qcl-negf.scientific-record.v1'),
    'final_diagnostics': ('final-diagnostics.schema.json', 'qcl-negf.final-diagnostics.v1'),
    'final_observations': ('final-observations.schema.json', 'qcl-negf.final-observations.v1'),
}
_TOTALS = ('records', 'scba_rows', 'outer_rows', 'witness_updates', 'last_record')


def _require(condition, path, message):
    if not condition:
        raise ContractError(f'{path}: {message}', 'corrupt_result')


@cache
def _validator(name):
    return schema_validator(name)


@cache
def _layout():
    return json.loads(files(__package__).joinpath('core_layout.json').read_text())


@cache
def _row_fields():
    return tuple(_validator('core-state.schema.json').schema['$defs']['ScientificRowKey']['required'])


def _walk(value, path='$'):
    """Check transport invariants that JSON Schema cannot express as field relations."""
    if isinstance(value, list):
        for index, item in enumerate(value):
            _walk(item, f'{path}[{index}]')
    elif isinstance(value, dict):
        if {'path', 'bytes', 'sha256', 'media_type', 'schema'} <= value.keys():
            _file(value, path=path)
        if value.get('kind') == 'integer':
            number = int(value['decimal'])
            kind = value['type']; signed = kind.startswith('Int')
            bits = int(kind[3:] if signed else kind[4:])
            _require(str(number) == value['decimal'], path, 'integer is not canonical')
            _require((-(1 << (bits-1)) if signed else 0) <= number < (1 << (bits-1 if signed else bits)),
                     path, 'integer out of declared width')
        if value.get('kind') == 'array':
            shape = [int(item) for item in value['shape']]
            if 'values' in value:
                _require(math.prod(shape) == len(value['values']), path, 'array shape/value count differs')
            else:
                allowed = {schema for (_, media), schemas in ARTIFACT_SCHEMA_CONTRACTS.items()
                           if media == 'application/x-hdf5' for schema in schemas}
                if value['file']['schema'] not in allowed:
                    raise ContractError(f'{path}.file: unsupported native array format', 'unsupported_format')
                _require(value['file']['media_type'] == 'application/x-hdf5', path+'.file', 'native array requires HDF5 declaration')
                dataset = value['dataset']
                _require(dataset.startswith('/') and '\\' not in dataset and '\x00' not in dataset
                         and all(part not in ('', '.', '..') for part in dataset[1:].split('/')),
                         path+'.dataset', 'invalid HDF5 dataset path')
        if value.get('kind') == 'dict':
            keys = [encode({'key': item['key']}) for item in value['entries']]
            _require(len(set(keys)) == len(keys), path, 'duplicate typed dictionary key')
        for name, item in value.items():
            _walk(item, path+'.'+name)


def _checked(kind, value):
    from jsonschema import ValidationError
    checked = object_value(value)
    filename, schema = _SCHEMAS[kind]
    if checked.get('schema') != schema or checked.get('contract_set') != CONTRACT_SET:
        raise ContractError(f'unsupported result format: {schema}/{CONTRACT_SET} required', 'unsupported_format')
    if kind == 'checkpoint' and isinstance(checked.get('core_layout_sha256'), str) and re.fullmatch(
            '[0-9a-f]{64}', checked['core_layout_sha256']) and checked['core_layout_sha256'] != _layout()['layout_sha256']:
        raise ContractError('unsupported Core layout', 'unsupported_format')
    try:
        encode(checked)  # finite JSON and valid UTF-8; no implicit size/lifetime quota
        _validator(filename).validate(checked)
    except ValidationError as error:
        path = '$'+''.join(f'[{item}]' if isinstance(item, int) else '.'+item for item in error.absolute_path)
        raise ContractError(f'{path}: {error.message}', 'invalid_input') from error
    except UnicodeError as error:
        raise ContractError('result contains invalid UTF-8', 'invalid_input') from error
    _walk(checked)
    return checked


def _file(value, schema=None, path='$'):
    for field, checker in (('path',relative_path), ('sha256',digest_value)):
        try:
            checker(value[field])
        except ContractError as error:
            raise ContractError(f'{path}.{field}: {error}', error.code) from error
    if schema is not None and value['schema'] != schema:
        raise ContractError(f'{path}.schema: requires {schema}', 'unsupported_format')


def _inventory(rows, *, dependencies=True):
    paths = [row['path'] for row in rows]
    _require(len(paths) == len(set(paths)), '$.artifacts', 'duplicate artifact path')
    for row in rows:
        # FileRef v2 decimal sizes adapt explicitly to the existing internal int model.
        Artifact.parse({**row, 'bytes': int(row['bytes'])})
        _require(len(set(row['dependencies'])) == len(row['dependencies']), '$.artifacts', 'duplicate dependency')
        if dependencies:
            _require(all(item in paths for item in row['dependencies']), '$.artifacts', 'dependency absent')


def _pin(value, path='$.history'):
    counts = {key: int(value[key]) for key in ('entries',)+_TOTALS}
    _require(counts['records'] == counts['scba_rows']+counts['outer_rows']+counts['witness_updates'],
             path, 'record totals differ')
    _require(counts['last_record'] == counts['records'], path, 'stream cutoff differs from record count')
    if value['head'] is None:
        _require(all(item == 0 for item in counts.values()), path, 'empty pin has nonzero counts')
    else:
        _file(value['head'], _SCHEMAS['catalog'][1], path+'.head')
        _require(counts['entries'] > 0 and counts['records'] > 0, path, 'nonempty pin has empty counts')


def _lineage(value):
    parent = value['lineage']['parent_state']
    if parent is None:
        return
    _file(parent['manifest'], _SCHEMAS['manifest'][1], '$.lineage.parent_state.manifest')
    own, prior = value['identity'], parent['identity']
    _require(all(own[key] == prior[key] for key in ('run_id','execution_id','point_id','model_sha256','plan_sha256')),
             '$.lineage', 'parent scientific scope differs')
    _require(int(prior['attempt']) < int(own['attempt']), '$.lineage', 'parent attempt must precede child')


def validate_manifest(value: object) -> Object:
    value = _checked('manifest', value)
    _lineage(value); _pin(value['history']); _inventory(value['artifacts'])
    if value['checkpoint'] is not None:
        _file(value['checkpoint'], _SCHEMAS['checkpoint'][1], '$.checkpoint')
        _require(any(all(row[key] == value['checkpoint'][key] for key in value['checkpoint'])
                     for row in value['artifacts']), '$.checkpoint', 'declaration absent from inventory')
    return value


def validate_pointer(value: object) -> Object:
    value = _checked('pointer', value)
    _file(value['manifest'], _SCHEMAS['manifest'][1], '$.manifest')
    return value


def _context_definition(name, value, path):
    from jsonschema import ValidationError
    checked = object_value(value)
    try:
        encode(checked)
        common = _validator('result-common.schema.json')
        common.evolve(schema={'$ref': '#/$defs/'+name, '$defs': common.schema['$defs']}).validate(checked)
    except ValidationError as error:
        suffix = ''.join(f'[{item}]' if isinstance(item, int) else '.'+item for item in error.absolute_path)
        raise ContractError(f'{path}{suffix}: {error.message}', 'invalid_input') from error
    except UnicodeError as error:
        raise ContractError(f'{path}: invalid UTF-8', 'invalid_input') from error
    _walk(checked, path)
    return checked


def _catalog_content(value):
    """One page's local relations; never follows or requires its ancestors."""
    value = _checked('catalog', value)
    _inventory(value['artifacts'], dependencies=False)
    _require(all(row['role'] == 'science.history' for row in value['artifacts']),
             '$.artifacts', 'scientific catalog accepts only science.history leaves')
    prior = value['previous']
    if prior is not None:
        _pin(prior, '$.previous')
    totals = {key: int(value['totals'][key]) for key in _TOTALS}
    before = {key: int(prior[key]) if prior else 0 for key in _TOTALS}
    first, last = (int(value['range'][key]) for key in ('first_record','last_record'))
    _require(int(value['entries']) == (int(prior['entries']) if prior else 0)+len(value['artifacts']),
             '$.entries', 'artifact count differs')
    _require(first == before['last_record']+1 and last >= first and last == totals['last_record'],
             '$.range', 'scientific stream range overlaps or has a gap')
    _require(totals['records'] == last and totals['records'] == sum(totals[key] for key in
             ('scba_rows','outer_rows','witness_updates')), '$.totals', 'row totals differ')
    _require(all(totals[key] >= before[key] for key in _TOTALS), '$.totals', 'prefix counters decreased')
    return value


def _catalog_pin(value, reference):
    return dict(head=reference, entries=value['entries'], **value['totals'])


def validate_catalog_page(value: object, *, previous: object | None = None,
                          previous_page: object | None = None,
                          previous_ref: object | None = None) -> Object:
    """Check a page and its one caller-verified predecessor, without prefix traversal."""
    value = _catalog_content(value)
    prior = value['previous']
    _require(prior == previous, '$.previous', 'explicit previous pin required and must match')
    if prior is None:
        _require(previous_page is None and previous_ref is None, '$.previous', 'initial page has previous context')
    else:
        _require(previous_page is not None and previous_ref is not None, '$.previous', 'previous page and reference required')
        reference = _context_definition('FileRef', previous_ref, '$.previous_ref')
        _file(reference, _SCHEMAS['catalog'][1], '$.previous_ref')
        page = _catalog_content(previous_page)
        _require(reference == prior['head'] and _catalog_pin(page, reference) == prior,
                 '$.previous', 'previous page/reference differs from pin')
        _require(all(page[key] == value[key] for key in ('identity','invocation')),
                 '$.previous_page', 'previous page owner or epoch differs')
        _require({row['path'] for row in value['artifacts']}.isdisjoint(
                     row['path'] for row in page['artifacts']),
                 '$.artifacts', 'new page reuses immutable leaf path from supplied predecessor')
        _require(int(page['generation']) < int(value['generation']),
                 '$.generation', 'catalog generation must increase')
    return value


def validate_cursor(value: object, *, manifest: object, manifest_ref: object,
                    catalog_page: object | None = None) -> Object:
    """Check explicit pinned source/page contexts; caller verifies their bytes/reachability."""
    value = _checked('cursor', value); source = validate_manifest(manifest)
    for key in ('identity','invocation','history'):
        _require(value[key] == source[key], '$.'+key, 'cursor source differs from pinned manifest')
    _file(value['manifest'], _SCHEMAS['manifest'][1], '$.manifest')
    reference = _context_definition('FileRef', manifest_ref, '$.manifest_ref')
    _file(reference, _SCHEMAS['manifest'][1], '$.manifest_ref')
    _require(value['manifest'] == reference, '$.manifest', 'cursor manifest reference differs from verified source')
    _require(int(value['last_record']) <= int(value['history']['last_record']), '$.last_record', 'cursor beyond cutoff')
    if value['leaf'] is None:
        _require(value['row_offset'] == '0' and value['last_record'] == '0', '$.leaf', 'empty cursor has position')
        _require(catalog_page is None, '$.catalog_page', 'empty cursor has containing page context')
    else:
        _file(value['leaf'], 'qcl-negf-scientific-history-v5', '$.leaf')
        _require(catalog_page is not None, '$.catalog_page', 'containing catalog page context required')
        context = object_value(catalog_page)
        _require(set(context) == {'reference','document'}, '$.catalog_page', 'requires only reference and document')
        page_ref = _context_definition('FileRef', context['reference'], '$.catalog_page.reference')
        _file(page_ref, _SCHEMAS['catalog'][1], '$.catalog_page.reference')
        page = _catalog_content(context['document'])
        _require(all(page[key] == source[key] for key in ('identity','invocation')),
                 '$.catalog_page', 'containing page owner or epoch differs')
        _require(int(page['generation']) <= int(source['generation']), '$.catalog_page', 'page generation exceeds manifest')
        page_pin = _catalog_pin(page, page_ref)
        _require(all(int(page_pin[key]) <= int(source['history'][key]) for key in ('entries',)+_TOTALS),
                 '$.catalog_page', 'page counters exceed pinned history')
        if page_pin['last_record'] == source['history']['last_record']:
            _require(page_ref == source['history']['head'], '$.catalog_page.reference', 'cutoff page differs from pinned head')
        if page_ref == source['history']['head']:
            _require(page_pin == source['history'], '$.catalog_page', 'head page counters differ from pin')
        _require(any(all(row[key] == value['leaf'][key] for key in value['leaf']) for row in page['artifacts']),
                 '$.leaf', 'cursor leaf absent from containing page')
        _require(int(page['range']['first_record']) <= int(value['last_record']) <= int(page['range']['last_record']),
                 '$.last_record', 'cursor ordinal outside containing page range')
    return value


def _fields(value):
    return value['fields']


def _integer(value):
    return int(value['decimal'])


def _symbol(value):
    return value['value']


def _array_refs(value):
    if isinstance(value, dict):
        if value.get('kind') == 'array' and 'file' in value:
            yield value['file']
        for child in value.values():
            yield from _array_refs(child)
    elif isinstance(value, list):
        for child in value:
            yield from _array_refs(child)


def validate_checkpoint_declaration(value: object, *, manifest: object | None = None) -> Object:
    value = _checked('checkpoint', value); _lineage(value); _pin(value['history'])
    _require(value['core_layout_sha256'] == _layout()['layout_sha256'], '$.core_layout_sha256', 'unsupported Core layout')
    state = _fields(value['state'])
    _require(state['identity'] == value['numerical_binding']['identity'], '$.numerical_binding', 'Core identity differs')
    paths = [item['path'] for item in value['payloads']]
    _require(len(paths) == len(set(paths)), '$.payloads', 'duplicate payload path')
    for item in _array_refs(value['state']):
        _require(item in value['payloads'], '$.payloads', 'array dependency absent or differs')
    continuation = state['continuation']
    eligible = set()
    if _symbol(state['boundary']) == 'scba_accepted' and continuation is not None and continuation['type'] == 'SCBAContinuation':
        inner = _fields(continuation)
        if not _fields(inner['decision'])['terminal']:
            eligible = {_integer(index) for index in inner['witness_retention'][1:] if _integer(index) > 0}
    keys, indices = [], []
    for entry in value['witness_targets']:
        key, locator = entry['row_key'], entry['locator']
        keys.append(encode(key)); indices.append(_integer(key['inner_iteration']) if key['inner_iteration'] is not None else -1)
        _require(_symbol(key['stage']) == 'scba' and _integer(key['outer_iteration']) == _integer(_fields(state['progress'])['current_outer']),
                 '$.witness_targets', 'target stage differs from continuing inner stage')
        _require(locator['leaf'] in value['payloads'], '$.witness_targets', 'target leaf is not a direct checkpoint dependency')
        _file(locator['leaf'], 'qcl-negf-scientific-history-v5', '$.witness_targets.leaf')
        _require(all(locator['source_identity'][name] == value['identity'][name] for name in
                     ('run_id','execution_id','point_id','model_sha256','plan_sha256')),
                 '$.witness_targets', 'source scientific scope differs')
        _require(int(locator['source_identity']['attempt']) <= int(value['identity']['attempt']),
                 '$.witness_targets', 'source attempt is in the future')
        if (locator['source_identity'] == value['identity'] and
                locator['source_epoch'] == value['invocation']['source_epoch']):
            _require(value['history']['head'] is not None and
                     int(locator['append_ordinal']) <= int(value['history']['last_record']),
                     '$.witness_targets', 'original append exceeds committed history cutoff')
    _require(len(keys) == len(set(keys)) and len(indices) == len(set(indices)) and set(indices) == eligible,
             '$.witness_targets', 'targets differ from exact public worst/last retention receipt')
    if manifest is not None:
        source = validate_manifest(manifest)
        for key in ('identity','lineage','invocation','state_id','state_sequence','history','numerical_binding'):
            _require(value[key] == source[key], '$.'+key, 'checkpoint differs from pinned manifest')
    return value


def validate_final_diagnostics(value: object, *, checkpoint: object, manifest: object,
                               artifact_ref: object) -> Object:
    """Bind complete stored observations to one caller-verified final source.

    Required contexts are immutable decoded documents and the selected analysis
    HDF FileRef. This pure check reads no files, verifies no hashes/native bytes,
    and never computes PSD metrics, thresholds, revalidation or scientific pass.
    Native owners check the header and same-open storage against this declaration.
    """
    value = _checked('final_diagnostics', value)
    source = validate_manifest(manifest)
    terminal = validate_checkpoint_declaration(checkpoint, manifest=source)
    reference = _context_definition('FileRef', artifact_ref, '$.artifact_ref')
    _file(reference, 'qcl-negf-physics-analysis-v5', '$.artifact_ref')
    _require(reference['media_type'] == 'application/x-hdf5', '$.artifact_ref', 'analysis requires HDF5')
    inventory = {row['path']: row for row in source['artifacts']}
    selected = inventory.get(reference['path'])
    _require(selected is not None and all(selected[key] == reference[key] for key in reference),
             '$.artifact_ref', 'selected analysis FileRef absent from manifest')
    _require(source['checkpoint'] is not None and value['checkpoint'] == source['checkpoint'],
             '$.checkpoint', 'checkpoint FileRef differs from selected manifest')
    _require(selected['role'] == 'physics.analysis' and selected['profile'] == 'science' and
             selected['dependencies'] == [value['checkpoint']['path']],
             '$.artifact_ref', 'analysis role/profile or direct checkpoint dependency differs')
    anchor = inventory[value['checkpoint']['path']]
    _require(set(anchor['dependencies']) == {item['path'] for item in terminal['payloads']},
             '$.checkpoint', 'checkpoint dependencies differ from declared payloads')
    for payload in terminal['payloads']:
        _require(payload['path'] not in (reference['path'], value['checkpoint']['path']),
                 '$.checkpoint', 'checkpoint payload would create an analysis/self hash cycle')
        row = inventory.get(payload['path'])
        _require(row is not None and all(row[key] == payload[key] for key in payload),
                 '$.checkpoint', 'checkpoint payload FileRef absent or differs from manifest')
    # Selected closure only; iterative DFS distinguishes back-edges from shared DAG leaves.
    active, completed = set(), set()
    pending = [(reference['path'], False)]
    while pending:
        path, leaving = pending.pop()
        if leaving:
            active.remove(path)
            completed.add(path)
        elif path not in completed:
            _require(path not in active, '$.artifact_ref', 'selected dependency closure contains a cycle')
            active.add(path)
            pending.append((path, True))
            pending.extend((dependency, False) for dependency in reversed(inventory[path]['dependencies']))
    for key in ('identity', 'invocation', 'state_id', 'state_sequence'):
        _require(value[key] == terminal[key], '$.'+key, 'diagnostics differ from final checkpoint')
    state = _fields(terminal['state'])
    _require(source['closed'] and source['status']['process']['state'] in
             ('succeeded', 'failed', 'cancelled', 'interrupted') and
             _symbol(state['boundary']) == 'final' and state['final_evidence'] is not None,
             '$.checkpoint', 'closed global-final evidence required')
    dimensions = {key: int(number) for key, number in value['dimensions'].items()}
    _require(all(number <= 2**63-1 for number in dimensions.values()),
             '$.dimensions', 'dimensions exceed actual Int64 domain')
    ne, nk, nb = (dimensions[key] for key in ('energy', 'momentum', 'basis'))
    shape = [str(ne), str(nk), str(nb), str(nb)]
    green = _fields(_fields(state['scba'])['green'])
    for name in ('Gᴿ', 'Gˡ', 'Gᵍ', 'A'):
        _require(green[name]['shape'] == shape, '$.dimensions', 'dimensions differ from checkpoint Green axes')
    for name, entries in value['solution_metrics'].items():
        if entries is not None:
            names = [row['name'] for row in entries]
            _require(names == sorted(set(names)), '$.solution_metrics.'+name, 'metric names must be sorted and unique')
    measured = value['positivity']
    if measured['data'] is None:
        _require(bool(measured['reason'].strip()), '$.positivity.reason', 'measurement cause must not be blank')
        return value
    data = measured['data']
    _require(_integer(data['metric_version']) > 0, '$.positivity.data.metric_version', 'metric version must be positive')
    for index, witness in enumerate(data['witnesses']):
        ei, ki = (_integer(witness[key]) for key in ('energy_index', 'momentum_index'))
        minimum = 1 if witness['status'] == 'measured' else 0
        _require(minimum <= ei <= ne and minimum <= ki <= nk,
                 '$.positivity.data.witnesses', 'witness coordinate outside declared domain')
        _require(witness['matrix_kind'] == data['matrix_kinds'][index] or
                 witness['status'] == 'error' and witness['matrix_kind'] == 'none',
                 '$.positivity.data.witnesses', 'witness kind differs from its channel')
        _require(witness['status'] != 'error' or not data['strict_threshold_satisfied'][index],
                 '$.positivity.data.strict_threshold_satisfied', 'error witness cannot declare measured threshold satisfaction')
    integrals = data['integrals']
    shapes = {'spectral_integral': [nk, nb, nb], 'spectral_integral_eigenvalues': [nk, nb],
              'spectral_trace_cumulative': [ne, nk], 'negative_energy_integral_scaled': [6, nk]}
    for name, expected in shapes.items():
        _require(integrals[name]['shape'] == [str(number) for number in expected],
                 '$.positivity.data.integrals.'+name, 'integral shape differs from final domain')
    total = _integer(integrals['total_blocks_per_kind'])
    _require(total == ne*nk, '$.positivity.data.integrals.total_blocks_per_kind', 'full-grid block count differs')
    for negative, beyond, invalid in zip(integrals['negative_block_count'],
            integrals['beyond_backward_error_block_count'], integrals['invalid_block_count']):
        n, b, e = map(_integer, (negative, beyond, invalid))
        _require(0 <= b <= n <= total-e and 0 <= e <= total,
                 '$.positivity.data.integrals', 'negative/beyond/invalid counts contradict full-grid coverage')
    return value


def _observation_context(resource, definition, value, path):
    """Validate a named bundled context, keeping the offline resource resolver."""
    from jsonschema import ValidationError
    checked = object_value(value)
    try:
        encode(checked)
        validator = _validator(resource)
        validator.evolve(schema={'$ref': '#/$defs/'+definition,
                                 '$defs': validator.schema['$defs']}).validate(checked)
    except ValidationError as error:
        suffix = ''.join(f'[{part}]' if isinstance(part, int) else '.'+part for part in error.absolute_path)
        raise ContractError(f'{path}{suffix}: {error.message}', 'invalid_input') from error
    except UnicodeError as error:
        raise ContractError(f'{path}: invalid UTF-8', 'invalid_input') from error
    # This context contains owning portable model metadata, not tagged Core values.
    # A metadata key named "kind" must not dispatch the Core transport grammar.
    return checked


def validate_nested_sweep_plan(value: object) -> Object:
    """Validate the existing decoded tree, never parse YAML or replace original bytes.

    The caller's bounded raw parser rejects aliases, tags, merges and duplicate keys
    before constructing this finite JSON-safe tree. A schema pass cannot prove those
    properties of unseen YAML. Canonical axis-value uniqueness remains an owner gate.
    """
    from jsonschema import ValidationError
    value = object_value(value)
    try:
        encode(value)
        _validator('nested-sweep-plan.schema.json').validate(value)
    except ValidationError as error:
        raise ContractError(f'$.plan: {error.message}', 'invalid_input') from error
    except UnicodeError as error:
        raise ContractError('$.plan: invalid UTF-8', 'invalid_input') from error
    paths = set()
    node = value['root']
    while node['kind'] == 'level':
        names = [axis['name'] for axis in node['axes']]
        _require(len(names) == len(set(names)), '$.plan.root.axes', 'duplicate axis name')
        for name in names:
            path = node['name']+'.'+name
            _require(path not in paths, '$.plan.root.axes', 'duplicate fully-qualified coordinate path')
            paths.add(path)
        node = node['child']
    return value


def _observation_selected(source, reference, role, path, dependencies):
    inventory = {row['path']: row for row in source['artifacts']}
    row = inventory.get(reference['path'])
    _require(row is not None and all(row[key] == reference[key] for key in reference),
             path, 'selected full FileRef absent or differs from manifest inventory')
    _require(row['role'] == role and row['profile'] == 'science' and
             row['dependencies'] == dependencies, path, 'role/profile or exact direct dependencies differ')
    return inventory


def _observation_dag(inventory, selected):
    # Iterative selected-closure DFS: shared descendants are not back-edges.
    active, completed = set(), set()
    pending = [(selected, False)]
    while pending:
        path, leaving = pending.pop()
        if leaving:
            active.remove(path)
            completed.add(path)
        elif path not in completed:
            _require(path not in active, '$.artifact_ref', 'selected dependency closure contains a cycle')
            active.add(path)
            pending.append((path, True))
            pending.extend((child, False) for child in reversed(inventory[path]['dependencies']))


def _observation_numeric_bits(value, path):
    """Encode a finite plan coordinate as f64, without a scientific tolerance."""
    _require(isinstance(value, (int, float)) and not isinstance(value, bool), path, 'numeric coordinate required')
    try:
        return struct.pack('>d', value).hex()
    except (OverflowError, struct.error) as error:
        raise ContractError(f'{path}: coordinate outside Float64 domain', 'invalid_input') from error


def _observation_request(value, source, plan, model):
    request = value['request']
    model = _observation_context('final-observations.schema.json', 'ModelEnvelope', model, '$.model')
    _require(model['configuration_hash'] == value['identity']['model_sha256'],
             '$.model.configuration_hash', 'actual point canonical model digest differs')
    flags = request['scattering_requested']
    _require(flags == model['configuration']['inputs']['scattering'] ==
             _fields(value['context']['problem_scattering']), '$.request.scattering_requested',
             'requested and actual model construction flags differ')
    plan_ref, model_ref = request['plan'], request['model']
    _file(model_ref, 'qcl-negf-resolved-configuration-v3', '$.request.model')
    _require(model_ref['media_type'] == 'application/json', '$.request.model', 'model requires JSON')
    _observation_selected(source, model_ref, 'model', '$.request.model', [])
    _require(plan_ref['sha256'] == value['identity']['plan_sha256'], '$.request.plan', 'original plan byte digest differs')
    _observation_selected(source, plan_ref, 'plan', '$.request.plan', [])
    if request['kind'] == 'scientific_plan_v2':
        from .messages import scientific_plan
        plan = scientific_plan(plan)
        from jsonschema import ValidationError
        try:
            encode(plan)
            _validator('scientific-plan.schema.json').validate(plan)
        except ValidationError as error:
            raise ContractError(f'$.plan: {error.message}', 'invalid_input') from error
        except UnicodeError as error:
            raise ContractError('$.plan: invalid UTF-8', 'invalid_input') from error
        _file(plan_ref, 'qcl-negf-scientific-plan-v2', '$.request.plan')
        _require(plan_ref['media_type'] == 'application/json', '$.request.plan', 'scientific plan requires JSON')
        points = [row for row in plan['points'] if row['id'] == value['identity']['point_id']]
        executions = [row for row in plan['executions'] if row['id'] == value['identity']['execution_id']]
        _require(len(points) == len(executions) == 1, '$.plan', 'selected point/execution absent or ambiguous')
        point, execution = points[0], executions[0]
        _require(point['execution_id'] == execution['id'] and point['id'] in execution['point_ids'],
                 '$.plan.points', 'point does not belong to selected execution')
        passport = point['effective_inputs']
        _require(passport['axes_applied'] and passport['model_sha256'] == model['configuration_hash'],
                 '$.plan.points.effective_inputs', 'point model binding differs from actual point model')
        for name in ('temperature_K', 'voltage_per_period_V'):
            _require(_observation_numeric_bits(point[name], '$.plan.points.'+name) == request[name]['bits'] ==
                     _observation_numeric_bits(passport[name], '$.plan.points.effective_inputs.'+name),
                     '$.request.'+name, 'requested coordinate differs from frozen point/passport')
    else:
        plan = validate_nested_sweep_plan(plan)
        _file(plan_ref, 'qcl-negf.nested-sweep-plan.v1', '$.request.plan')
        _require(plan_ref['media_type'] == 'text/plain', '$.request.plan', 'original nested YAML requires text/plain')
        _require(plan['name'] == 'configured_operating_points', '$.plan.name', 'configured plan differs')
        node = plan['root']
        for level, axis, coordinate in (('temperature', 'temperature_K', 'temperature_K'),
                                         ('voltage', 'voltage_per_period_V', 'voltage_per_period_V')):
            _require(node['kind'] == 'level' and node['name'] == level and
                     len(node['axes']) == 1 and node['axes'][0]['name'] == axis,
                     '$.plan.root', 'configured coordinate tree differs')
            values = node['axes'][0]['values']
            bits = [_observation_numeric_bits(item, '$.plan.root.axes.values') for item in values]
            _require(request[coordinate]['bits'] in bits, '$.request.'+coordinate,
                     'requested coordinate absent from original tree')
            node = node['child']
        _require(node == {'kind': 'leaf', 'name': 'poisson_scba'}, '$.plan.root.child', 'configured leaf differs')
    for name, requested, actual in (('temperature', request['temperature_K'], value['context']['inputs']['T_L_K']),
                                    ('voltage', request['voltage_per_period_V'], value['context']['inputs']['V_period_V'])):
        check = request['coordinate_checks'][name]
        _require(check['requested'] == requested and check['actual'] == actual,
                 '$.request.coordinate_checks.'+name, 'recorded coordinate samples differ')
        equal = requested == actual
        _require((equal and check['status'] == 'verified' and check['reason'] is None) or
                 (not equal and name == 'voltage' and check['status'] == 'not_verified' and
                  check['reason'] == 'field_period_roundtrip'),
                 '$.request.coordinate_checks.'+name, 'coordinate verification status/reason differs')


def _observation_shapes_and_state(value, terminal):
    context, views = value['context'], value['views']
    dimensions = {key: int(number) for key, number in context['dimensions'].items()}
    _require(all(number <= 2**63-1 for number in dimensions.values()), '$.context.dimensions', 'dimensions exceed Int64 domain')
    nz, ne, nk, nb = (dimensions[key] for key in ('Nz', 'NE', 'Nk', 'Nb'))
    state = _fields(terminal['state']); scba = _fields(state['scba'])
    _require(value['binding'] == {'identity': state['identity'], 'terminal_integrity': state['integrity']},
             '$.binding', 'Core identity or terminal integrity differs from checkpoint')
    _require(context['algorithms'] == _fields(state['measurement_context'])['algorithms'],
             '$.context.algorithms', 'algorithms differ from exact checkpoint context')
    for name in ('published_U', 'published_n'):
        _require(state[name]['shape'] == [str(nz)], '$.context.dimensions.Nz', 'spatial dimension differs from checkpoint')
    green = _fields(scba['green'])
    shape = [str(ne), str(nk), str(nb), str(nb)]
    bindings = value['state_bindings']
    _require(bindings['green'] == {a: green[b] for a, b in
             (('retarded', 'Gᴿ'), ('lesser', 'Gˡ'), ('greater', 'Gᵍ'), ('spectral', 'A'))},
             '$.state_bindings.green', 'Green descriptors differ from checkpoint')
    _require(all(green[name]['shape'] == shape for name in ('Gᴿ', 'Gˡ', 'Gᵍ', 'A')),
             '$.context.dimensions', 'Green dimensions differ from actual domain')
    def components(family):
        fields = _fields(family)
        result = {a: fields[b] for a, b in (('retarded', 'Σᴿ'), ('lesser', 'Σˡ'), ('greater', 'Σᵍ'))}
        _require(all(array['shape'] == shape for array in result.values()),
                 '$.state_bindings', 'selfenergy shape differs from actual domain')
        return result
    scattering = [dict(family=_symbol(item['key']), **components(item['value'])) for item in scba['scattering']['entries']]
    families = [item['family'] for item in scattering]
    _require(bindings['scattering'] == scattering and context['selfenergy_families'] == families and
             len(families) == len(set(families)), '$.state_bindings.scattering', 'actual family order or descriptors differ')
    _require(context['enabled_scattering'] == [name for name in families if name != 'electron_electron'],
             '$.context.enabled_scattering', 'actual five-family projection differs')
    _require([_symbol(item) for item in state['family_order']] == families+['embedding_plus', 'embedding_minus'],
             '$.state_bindings.scattering', 'checkpoint family order differs')
    _require(bindings['embedding'] == {name: components(scba[field]) for name, field in
             (('total', 'embedding'), ('plus', 'embedding_plus'), ('minus', 'embedding_minus'))},
             '$.state_bindings.embedding', 'embedding descriptors differ from checkpoint')
    adaptation = state['adaptation']
    _require(_integer(context['domain_revision']) == (0 if adaptation is None else _integer(_fields(adaptation)['expansions'])),
             '$.context.domain_revision', 'actual domain revision differs')
    if adaptation is not None:
        revisions = _fields(adaptation)['revisions']
        _require(bool(revisions) and _fields(revisions[-1])['evidence'] is not None,
                 '$.context', 'actual adaptive domain receipt missing')
        evidence = _fields(_fields(revisions[-1])['evidence'])
        _require(all(context[name] == evidence[name] for name in ('discretization_id', 'basis_id')),
                 '$.context', 'actual adaptive domain IDs differ')
    axis_counts = {'z': nz, 'E': ne, 'k': nk, 'state': nb, 'state_prime': nb}
    for owner in (context, views):
        for field, descriptor in owner.items():
            if isinstance(descriptor, dict) and 'dataset' in descriptor:
                _require(descriptor['shape'] == [str(axis_counts[axis]) for axis in descriptor['axes']],
                         '$.arrays.'+field, 'local shape differs from actual dimensions')
    _require(_integer(value['summary']['outer_confirmation_count']) >= 0, '$.summary.outer_confirmation_count', 'negative count')
    _require(_integer(context['inputs']['g_s']) >= 0,
             '$.context.inputs.g_s', 'negative count')
    return state


def _observation_issues(value, diagnostics):
    issues = {item['target']: item for item in value['issues']}
    _require(len(issues) == len(value['issues']), '$.issues', 'duplicate issue target')
    missing = {name for name, array in value['views'].items() if array is None}
    positivity = diagnostics['positivity']
    if positivity['data'] is None:
        missing.add('positivity')
        issue = issues.get('positivity')
        _require(issue is not None and issue['status'] == positivity['status'] and
                 positivity['reason'] == issue['reason']+': '+issue['detail'],
                 '$.issues', 'positivity issue differs from original diagnostic failure')
    _require(set(issues) == missing, '$.issues', 'issues do not match unavailable outputs')
    group = [value['views'][name] is None for name in ('effective_levels_eV',
             'effective_wavefunctions_per_sqrt_nm', 'effective_transform', 'effective_density_matrix_per_m2')]
    _require(all(group) or not any(group), '$.views', 'incomplete effective view group')


def _observation_restoration(value, source, terminal, parent_manifest, parent_checkpoint):
    state = _fields(terminal['state']); summary = value['summary']; restoration = value['restoration']
    if value['source_mode'] == 'produced':
        _require(restoration is None and parent_manifest is None and parent_checkpoint is None,
                 '$.restoration', 'produced observations cannot carry restoration contexts')
        original = _fields(state['final_evidence'])
        _require(summary['status'] == _symbol(original['original_status']) and
                 summary['converged'] == original['original_converged'], '$.summary', 'original classification differs')
        return
    _require(restoration is not None and parent_manifest is not None and parent_checkpoint is not None,
             '$.restoration', 'completed restore requires both verified parent contexts')
    prior_source = validate_manifest(parent_manifest)
    prior = validate_checkpoint_declaration(parent_checkpoint, manifest=prior_source)
    anchor = source['lineage']['parent_state']
    _require(anchor is not None and restoration['parent_state'] == anchor and
             all(anchor[key] == prior[key] for key in ('identity', 'state_id', 'state_sequence')) and
             restoration['parent_checkpoint'] == prior_source['checkpoint'] and
             restoration['history'] == prior['history'], '$.restoration', 'immediate parent state/reference/cutoff differs')
    _file(restoration['parent_checkpoint'], 'qcl-negf.checkpoint-declaration.v1', '$.restoration.parent_checkpoint')
    old = _fields(prior['state'])
    _require(prior_source['closed'] and prior_source['status']['process']['state'] in
             ('succeeded', 'failed', 'cancelled', 'interrupted') and
             _symbol(old['boundary']) == 'final' and old['final_evidence'] is not None,
             '$.restoration', 'parent is not a closed original final state')
    inventory = {row['path']: row for row in prior_source['artifacts']}
    checkpoint_row = inventory[restoration['parent_checkpoint']['path']]
    _require(set(checkpoint_row['dependencies']) == {item['path'] for item in prior['payloads']},
             '$.restoration.parent_checkpoint', 'parent checkpoint payload frontier differs')
    for payload in prior['payloads']:
        row = inventory.get(payload['path'])
        _require(row is not None and all(row[key] == payload[key] for key in payload),
                 '$.restoration.parent_checkpoint', 'parent payload full FileRef differs from inventory')
    _observation_dag(inventory, restoration['parent_checkpoint']['path'])
    # Core snapshot is preserved across attempts. Envelope attempt/branch/epoch are not Core identity.
    _require(all(state[name] == old[name] for name in ('identity', 'integrity', 'final_evidence')),
             '$.restoration.original', 'original Core binding/evidence differs from selected parent')
    _require(restoration['original'] == {'checkpoint': value['checkpoint'], 'field': 'final_evidence',
             'integrity': state['integrity']}, '$.restoration.original', 'original locator differs from child checkpoint')
    selected = _fields(restoration['revalidation']); oracle = _fields(restoration['independent_oracle'])
    status = _symbol(selected['status']); passed = _fields(selected['report'])['passed']
    _require(status in ('measured', 'error') and (status != 'error' or selected['reason'] is not None and not passed),
             '$.restoration.revalidation', 'selected-map receipt status/report inconsistent')
    context = _fields(selected['context'])
    _require(context['algorithms'] == value['context']['algorithms'] and
             _symbol(context['final_state_alignment']) == 'restored_aligned',
             '$.restoration.revalidation.context', 'restoration context differs')
    if status == 'measured':
        _require(_symbol(context['backend']) == 'production' and context['map_kernels_shared_with_solver'] is True,
                 '$.restoration.revalidation.context', 'measured receipt lacks selected-map context')
    oracle_status = _symbol(oracle['status'])
    _require(oracle_status in ('measured', 'not_measured', 'unsupported', 'error') and
             (oracle_status == 'measured' or oracle['reason'] is not None),
             '$.restoration.independent_oracle', 'independent receipt status/reason inconsistent')
    if oracle_status == 'measured':
        _require(oracle['report'] is not None and oracle['context'] is not None,
                 '$.restoration.independent_oracle', 'measured independent receipt lacks report/context')
        independent = _fields(oracle['context'])
        _require(_symbol(independent['backend']) == 'reference' and independent['map_kernels_shared_with_solver'] is False,
                 '$.restoration.independent_oracle', 'oracle does not declare independent reference context')
    # Structural classification relationships only, never repeat numerical band/history gates.
    if summary['converged']:
        consistent = passed and summary['status'] == 'converged'
    elif summary['status'] == 'approximate':
        consistent = passed
    elif not passed:
        consistent = summary['status'] == 'validation_failed'
    else:
        consistent = summary['status'] == _symbol(state['status'])
    _require(consistent, '$.summary', 'current classification contradicts recorded revalidation')


def validate_final_observations(value: object, *, checkpoint: object, manifest: object,
                                artifact_ref: object, diagnostics: object, plan: object, model: object,
                                parent_manifest: object | None = None,
                                parent_checkpoint: object | None = None) -> Object:
    """Join caller-verified immutable final sources without files, hashes or numerics.

    The caller verifies bytes/HDF storage and supplies decoded documents for these
    exact refs. Model canonical bytes and safe original YAML parsing belong to the
    independent owners. Valid declarations never establish scientific acceptance.
    """
    value = _checked('final_observations', value)
    source = validate_manifest(manifest)
    terminal = validate_checkpoint_declaration(checkpoint, manifest=source)
    reference = _context_definition('FileRef', artifact_ref, '$.artifact_ref')
    _file(reference, 'qcl-negf-physics-analysis-v5', '$.artifact_ref')
    _require(reference['media_type'] == 'application/x-hdf5', '$.artifact_ref', 'analysis requires HDF5')
    refs = (value['checkpoint'], value['diagnostics'], value['request']['plan'], value['request']['model'])
    paths = [item['path'] for item in refs]
    _require(len(set(paths+[reference['path']])) == 5, '$.artifact_ref', 'selected immutable paths alias')
    inventory = _observation_selected(source, reference, 'physics.analysis', '$.artifact_ref', paths)
    _require(source['checkpoint'] == value['checkpoint'], '$.checkpoint', 'selected checkpoint reference differs')
    diagnostics = validate_final_diagnostics(diagnostics, checkpoint=terminal, manifest=source,
                                              artifact_ref=value['diagnostics'])
    state = _fields(terminal['state'])
    _require(source['closed'] and source['status']['process']['state'] in
             ('succeeded', 'failed', 'cancelled', 'interrupted') and _symbol(state['boundary']) == 'final' and
             state['final_evidence'] is not None, '$.checkpoint', 'closed global-final evidence required')
    for key in ('identity', 'invocation', 'state_id', 'state_sequence'):
        _require(value[key] == terminal[key], '$.'+key, 'observations differ from selected final checkpoint')
    _observation_shapes_and_state(value, terminal)
    dimensions = value['context']['dimensions']
    _require(diagnostics['dimensions'] == {'energy': dimensions['NE'], 'momentum': dimensions['Nk'], 'basis': dimensions['Nb']},
             '$.diagnostics', 'linked diagnostics domain differs')
    _observation_request(value, source, plan, model)
    _observation_issues(value, diagnostics)
    _observation_restoration(value, source, terminal, parent_manifest, parent_checkpoint)
    _observation_dag(inventory, reference['path'])
    return value


def validate_scientific_record(value: object, *, parent_checkpoint: object | None = None,
                               parent_state: object | None = None,
                               parent_manifest_ref: object | None = None) -> Object:
    """Bind updates to explicit original appends.

    For cross-attempt updates, the caller supplies the verified checkpoint, actual child
    lineage parent StateRef and its verified manifest FileRef. No files are read here.
    """
    value = _checked('record', value)
    core = _fields(value['core']); action = _symbol(core['action'])
    _require(value['row_key'] == {key: core[key] for key in _row_fields()}, '$.row_key', 'Core row projection differs')
    _require(action in ('append','witness_update'), '$.core.action', 'unknown history action')
    target = value['target']
    if action == 'append':
        _require(target is None, '$.target', 'append must not target another row')
        return value
    _require(target is not None, '$.target', 'witness update requires original append locator')
    if target['scope'] != 'parent_checkpoint':
        _require(target['source_identity'] == value['identity'] and target['source_epoch'] == value['invocation']['source_epoch'],
                 '$.target', 'current-stream target scope differs')
        _require(int(target['append_ordinal']) < int(value['stream_ordinal']), '$.target', 'target must precede update')
        if target['scope'] == 'sealed_leaf':
            _file(target['leaf'], 'qcl-negf-scientific-history-v5', '$.target.leaf')
        return value
    _require(parent_checkpoint is not None, '$.parent_checkpoint', 'pinned parent context required')
    _require(parent_state is not None and parent_manifest_ref is not None,
             '$.parent_state', 'actual child lineage parent and manifest reference required')
    parent = validate_checkpoint_declaration(parent_checkpoint)
    anchor = target['anchor_state']
    expected = _context_definition('StateRef', parent_state, '$.parent_state')
    reference = _context_definition('FileRef', parent_manifest_ref, '$.parent_manifest_ref')
    _file(reference, _SCHEMAS['manifest'][1], '$.parent_manifest_ref')
    _require(anchor == expected and expected['manifest'] == reference,
             '$.target.anchor_state', 'anchor differs from actual lineage parent or verified manifest reference')
    _require(all(anchor[key] == parent[key] for key in ('identity','state_id','state_sequence')) and
             target['anchor_history'] == parent['history'], '$.target', 'parent state/pin differs')
    _require(int(parent['identity']['attempt']) < int(value['identity']['attempt']), '$.target', 'parent attempt must precede update')
    _require(all(parent['identity'][key] == value['identity'][key] for key in
                 ('run_id','execution_id','point_id','model_sha256','plan_sha256')), '$.target', 'parent scope differs')
    locator = {key: target[key] for key in ('source_identity','source_epoch','append_ordinal','leaf','row_offset')}
    _require({'row_key':value['row_key'],'locator':locator} in parent['witness_targets'],
             '$.target', 'original append locator absent from parent dependencies')
    return value
