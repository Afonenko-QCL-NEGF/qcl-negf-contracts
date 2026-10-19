"""Literal portable-format controls; no Core imports or numerical solver."""
import copy
import json

import pytest

from qcl_negf_contracts import schema_validator
from qcl_negf_contracts.final_audit import (
    encode_final_audit, validate_final_audit, validate_final_audit_pair,
)
from qcl_negf_contracts.messages import ContractError


def measured(value=0):
    return {'status': 'measured', 'value': value, 'nonfinite': None, 'reason': None}


def fixture():
    # Independent format fixture: values are manufactured scalar measurements.
    witness = {'status': 'measured', 'e_index': 1, 'k_index': 1,
               'numerator_F': measured(), 'D_F': measured(1), 'GR_F': measured(1),
               'identity_F': measured(1), 'denominator': measured(2), 'ratio': measured()}
    norm = {'numerator_F': measured(), 'scale_F': measured(),
            'denominator': measured(1e-14), 'ratio': measured(), 'floor': 1e-14}
    return {
        'schema': 'qcl-negf-final-fixed-point-audit-v1', 'record_status': 'measured',
        'reason': None, 'detail': '', 'detail_truncated': False,
        'state_identity': {'execution_id': 'e', 'point_id': 'p', 'state_id': 's',
                           'attempt': 1, 'state_sequence': 1, 'plan_fingerprint': 'a'*64},
        'shape': {'NE': 1, 'Nk': 1, 'Nb': 1},
        'units': {'native': '1', 'energy_scale': 'eV', 'length_scale': 'm', 'index': '1-based'},
        'context': {'status': 'known', 'reason': None, 'unknown_fields': [],
            'backend': 'production', 'energy_shift': 'linear', 'hilbert': 'direct',
            'contraction': 'reference', 'kernel_build': 'reference', 'embedding': 'finite_chain',
            'electron_electron_mode': 'none', 'embedding_periods': 4, 'enabled_scattering': [],
            'E0_eV': 1, 'L0_m': 1, 'lambda_P': 1, 'map_kernels_shared_with_solver': True,
            'independent_physics_oracle': False, 'state_alignment': 'producer_aligned',
            'alignment_reason': None, 'source_owner_role': 'physics.full',
            'source_paths': {'U': '/state_dimensionless/UH', 'n': '/state_dimensionless/density',
                'GR': '/state_dimensionless/GR', 'GL': '/state_dimensionless/GL',
                'GG': '/state_dimensionless/GG', 'A': '/state_dimensionless/A'}},
        'history': {'inner_last': 1, 'inner_previous': None, 'outer_last': 1,
                    'previous_lambda': {'status': 'not_applicable', 'value': None,
                        'nonfinite': None, 'reason': 'no_previous_inner_iteration'}},
        'dyson': {'ratio': measured(), 'global_abs_F': measured(), 'max_abs_F': measured(),
                  'ratio_witness': copy.deepcopy(witness), 'absolute_witness': copy.deepcopy(witness)},
        'spectral': copy.deepcopy(norm), 'keldysh': copy.deepcopy(norm),
        'selfenergy': {'rows': [dict(family=f, component=c,
                            **{k: measured(1e-14 if k == 'denominator' else 0)
                               for k in ('numerator_F', 'scale_F', 'denominator', 'ratio')})
                       for f in ('embedding_total', 'embedding_plus', 'embedding_minus')
                       for c in ('R', 'L', 'G')],
                      'winner': {'family': 'embedding_total', 'component': 'R'},
                      'max_ratio': measured(), 'floor': 1e-14},
        'charge': {k: measured(v) for k, v in {
            'target_sheet': 1, 'stored_raw_sheet': 1, 'normalized_sheet': 1,
            'candidate_raw_sheet': 1, 'stored_lambda': 1, 'candidate_lambda': 1,
            'stored_constraint': 0, 'candidate_constraint': 0, 'normalized_residual': 0}.items()},
        'poisson': {k: measured(v) for k, v in {
            'residual_ratio': 0, 'residual_numerator_F': 0, 'rhs_F': 0,
            'additive_floor': 1e-14, 'denominator': 1e-14, 'border_scale': 1,
            'zeta_signed': 0, 'neutrality_signed': 0, 'neutrality_abs': 0,
            'target_sheet': 1, 'neutrality_ratio': 0, 'rU_max': 0}.items()},
    }


def healthy():
    value = fixture()
    value['charge']['lambda_change'] = {
        'status': 'not_applicable', 'value': None, 'nonfinite': None,
        'reason': 'no_previous_inner_iteration'}
    return value


def raw(value):
    return json.dumps(value, separators=(',', ':'), allow_nan=False).encode()


def test_measured_zero_is_preserved_without_acceptance():
    record = healthy()
    schema_validator('final-fixed-point-audit.schema.json').validate(record)
    assert validate_final_audit(raw(record)) == record
    assert validate_final_audit(encode_final_audit(record))['dyson']['ratio'] == measured(0)


@pytest.mark.parametrize('path,value', [
    (('schema',), 'wrong'), (('units', 'energy_scale'), 'meV'),
    (('record_status',), 'pass'), (('extra',), 0),
    (('state_identity', 'attempt'), True), (('state_identity', 'state_sequence'), 1.0),
    (('state_identity', 'plan_fingerprint'), 'A'*64),
    (('context', 'enabled_scattering'), ['acoustic', 'LO']),
    (('context', 'map_kernels_shared_with_solver'), False),
    (('context', 'unknown_fields'), ['backend']),
    (('context', 'state_alignment'), 'aligned'),
    (('context', 'E0_eV'), 0), (('shape', 'Nb'), 2**31),
    (('dyson', 'ratio', 'status'), 'unavailable'),
    (('dyson', 'ratio_witness', 'e_index'), 2),
    (('dyson', 'ratio_witness', 'denominator', 'value'), 0),
    (('spectral', 'floor'), 0), (('spectral', 'ratio', 'value'), -1),
    (('detail',), 'я'*257), (('context', 'hilbert'), 'я'*33),
    (('state_identity', 'state_id'), 'я'*65),
    (('selfenergy', 'winner'), {'family': 'embedding_minus', 'component': 'G'}),
    (('history', 'previous_lambda', 'status'), 'measured'),
])
def test_rejects_contract_mutations(path, value):
    record = healthy()
    target = record
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    with pytest.raises(ContractError):
        validate_final_audit(raw(record))


@pytest.mark.parametrize('payload', [
    b'{"schema":0,"schema":1}', b'{"x":NaN}', b'{"x":Infinity}',
    b'{"x":1e999}', b'\xff', b'\xef\xbb\xbf{}', b'{"x":"\x00"}',
    b' '*65537, b'{"x":' + b'['*10 + b'0' + b']'*10 + b'}',
    b'{' + b','.join(b'"k%d":0' % i for i in range(1025)) + b'}',
])
def test_hostile_json_is_rejected(payload):
    with pytest.raises(ContractError):
        validate_final_audit(payload)


def test_missing_and_noncanonical_rows_rejected():
    for mutate in (lambda x: x.pop('poisson'),
                   lambda x: x['selfenergy']['rows'].pop(),
                   lambda x: x['selfenergy']['rows'].reverse(),
                   lambda x: x['selfenergy']['rows'].append(x['selfenergy']['rows'][0])):
        record = healthy()
        mutate(record)
        with pytest.raises(ContractError):
            validate_final_audit(raw(record))


def test_partial_error_keeps_finite_zero_and_signed_candidate():
    record = healthy()
    record['charge']['candidate_raw_sheet'] = measured(-1)
    record['charge']['candidate_lambda'] = measured(-1)
    record['charge']['candidate_constraint'] = measured(2)
    assert validate_final_audit(raw(record))['charge']['candidate_raw_sheet']['value'] == -1
    record['record_status'], record['reason'] = 'partial_error', 'measurement_error'
    record['dyson']['ratio'] = {'status': 'error', 'value': 0,
                               'nonfinite': None, 'reason': 'nonfinite_measurement'}
    assert validate_final_audit(raw(record))['dyson']['ratio']['value'] == 0
    record['dyson']['ratio']['nonfinite'] = '+inf'
    with pytest.raises(ContractError):
        validate_final_audit(raw(record))


def test_tagged_null_and_required_status_consistency():
    record = healthy()
    record['record_status'], record['reason'] = 'partial_error', 'measurement_error'
    record['charge']['candidate_raw_sheet'] = {
        'status': 'error', 'value': None, 'nonfinite': 'nan', 'reason': 'nonfinite_measurement'}
    for key in ('candidate_lambda', 'candidate_constraint'):
        record['charge'][key] = {'status': 'error', 'value': None, 'nonfinite': None,
                                 'reason': 'invalid_prerequisite'}
    assert validate_final_audit(raw(record))['charge']['candidate_raw_sheet']['nonfinite'] == 'nan'
    record['record_status'], record['reason'] = 'measured', None
    with pytest.raises(ContractError):
        validate_final_audit(raw(record))


def test_context_unknown_is_explicit_and_ordered():
    record = healthy()
    context = record['context']
    context.update(status='unknown', reason='missing_executed_context', backend=None,
                   E0_eV=None, unknown_fields=['backend', 'E0_eV'])
    assert validate_final_audit(raw(record))['context']['backend'] is None
    context['unknown_fields'].reverse()
    with pytest.raises(ContractError):
        validate_final_audit(raw(record))


def test_identity_binding_and_exact_semantic_pair_equality():
    record = healthy()
    identity = dict(record['state_identity'], unrelated='preserved_by_caller')
    pair = validate_final_audit_pair(raw(record), record, expected_identity=identity)
    assert pair['record'] == record
    reordered = json.dumps(record, sort_keys=True).encode()
    assert validate_final_audit_pair(reordered, record, expected_identity=identity)['record'] == record
    for key, value in [('attempt', 2), ('state_sequence', 2), ('plan_fingerprint', 'b'*64)]:
        wrong = dict(identity, **{key: value})
        with pytest.raises(ContractError):
            validate_final_audit_pair(raw(record), record, expected_identity=wrong)
    other = copy.deepcopy(record)
    other['dyson']['ratio']['value'] = 1e-30
    with pytest.raises(ContractError):
        validate_final_audit_pair(raw(record), other, expected_identity=identity)


def test_legacy_recovery_and_one_sided_presence():
    record = healthy()
    identity = record['state_identity']
    assert validate_final_audit_pair(None, None, expected_identity=identity)['status'] == 'not_recorded'
    assert validate_final_audit_pair(None, None, expected_identity=identity,
                                     final_state=False)['status'] == 'not_applicable'
    for native, commit in [(raw(record), None), (None, record)]:
        with pytest.raises(ContractError):
            validate_final_audit_pair(native, commit, expected_identity=identity)
    with pytest.raises(ContractError):
        validate_final_audit_pair(raw(record), record, expected_identity=identity, final_state=False)


def test_unavailable_fresh_map_and_optional_empty_history():
    record = healthy()
    unavailable = {'status': 'unavailable', 'value': None, 'nonfinite': None,
                   'reason': 'map_unavailable'}
    record.update(record_status='unavailable', reason='map_unavailable')
    for key in ('ratio', 'global_abs_F', 'max_abs_F'):
        record['dyson'][key] = copy.deepcopy(unavailable)
    for key in ('ratio_witness', 'absolute_witness'):
        witness = record['dyson'][key]
        witness.update(status='unavailable', e_index=None, k_index=None)
        for field in ('numerator_F', 'D_F', 'GR_F', 'identity_F', 'denominator', 'ratio'):
            witness[field] = copy.deepcopy(unavailable)
    for name in ('spectral', 'keldysh'):
        for key in ('numerator_F', 'scale_F', 'denominator', 'ratio'):
            record[name][key] = copy.deepcopy(unavailable)
    for row in record['selfenergy']['rows']:
        for key in ('numerator_F', 'scale_F', 'denominator', 'ratio'):
            row[key] = copy.deepcopy(unavailable)
    record['selfenergy']['winner'] = None
    record['selfenergy']['max_ratio'] = copy.deepcopy(unavailable)
    for key in ('candidate_raw_sheet', 'candidate_lambda', 'candidate_constraint'):
        record['charge'][key] = copy.deepcopy(unavailable)
    assert validate_final_audit(raw(record))['record_status'] == 'unavailable'
    record['charge']['candidate_raw_sheet'] = measured(0)
    with pytest.raises(ContractError):
        validate_final_audit(raw(record))


def test_overflow_normalization_retains_zero_and_independent_finite_numerators():
    # Literal D2 clarification: no arithmetic is recomputed by this validator.
    record = healthy()
    error_zero = {'status': 'error', 'value': 0, 'nonfinite': None,
                  'reason': 'nonfinite_measurement'}
    error_inf = {'status': 'error', 'value': None, 'nonfinite': '+inf',
                 'reason': 'nonfinite_measurement'}
    record.update(record_status='partial_error', reason='measurement_error')
    record['dyson']['ratio'] = copy.deepcopy(error_zero)
    record['dyson']['global_abs_F'] = measured(2)
    record['dyson']['max_abs_F'] = measured(2)
    for key in ('ratio_witness', 'absolute_witness'):
        witness = record['dyson'][key]
        witness.update(status='error', numerator_F=measured(2),
                       D_F=copy.deepcopy(error_inf), denominator=copy.deepcopy(error_inf),
                       ratio=copy.deepcopy(error_zero))
    assert validate_final_audit(raw(record))['dyson']['global_abs_F'] == measured(2)
    for path in (('dyson', 'ratio'), ('dyson', 'ratio_witness', 'ratio'),
                 ('dyson', 'absolute_witness', 'ratio')):
        wrong = copy.deepcopy(record)
        target = wrong
        for key in path[:-1]:
            target = target[key]
        target[path[-1]] = measured(0)
        with pytest.raises(ContractError):
            validate_final_audit(raw(wrong))
    for key in ('ratio_witness', 'absolute_witness'):
        wrong = copy.deepcopy(record)
        wrong['dyson'][key]['ratio']['nonfinite'] = '+inf'
        with pytest.raises(ContractError):
            validate_final_audit(raw(wrong))


@pytest.mark.parametrize('target', [0, -1])
def test_invalid_target_preserved_and_dependents_cannot_look_measured(target):
    record = healthy()
    record.update(record_status='partial_error', reason='measurement_error')
    record['charge']['target_sheet'] = {
        'status': 'error', 'value': target, 'nonfinite': None, 'reason': 'nonpositive_target'}
    undefined = {'status': 'error', 'value': None, 'nonfinite': None,
                 'reason': 'invalid_prerequisite'}
    for key in ('stored_lambda', 'stored_constraint', 'candidate_lambda',
                'candidate_constraint', 'normalized_residual'):
        record['charge'][key] = copy.deepcopy(undefined)
    assert validate_final_audit(raw(record))['charge']['target_sheet']['value'] == target
    record['charge']['candidate_lambda'] = measured(0)
    with pytest.raises(ContractError):
        validate_final_audit(raw(record))


def test_empty_history_is_unavailable_not_optional_success():
    record = healthy()
    record['history'].update(inner_last=None, inner_previous=None)
    absent = {'status': 'unavailable', 'value': None, 'nonfinite': None,
              'reason': 'history_unavailable'}
    record['history']['previous_lambda'] = copy.deepcopy(absent)
    record['charge']['lambda_change'] = copy.deepcopy(absent)
    assert validate_final_audit(raw(record))['record_status'] == 'measured'
    record['history']['previous_lambda']['value'] = 0
    with pytest.raises(ContractError):
        validate_final_audit(raw(record))


def test_nonadjacent_actual_previous_history_and_signed_change():
    record = healthy()
    record['history'].update(inner_last=9, inner_previous=3, previous_lambda=measured(2))
    record['charge']['lambda_change'] = measured(-1)
    assert validate_final_audit(raw(record))['history']['inner_previous'] == 3


def test_encodes_zero_canonically_and_does_not_mutate_input():
    record = healthy()
    record['dyson']['ratio']['value'] = -0.0
    before = copy.deepcopy(record)
    encoded = encode_final_audit(record)
    assert b'-0.0' not in encoded
    assert record == before
    assert validate_final_audit(encoded)['dyson']['ratio']['value'] == 0


def test_identity_does_not_coerce_boolean_or_float():
    record = healthy()
    for value in (True, 1.0):
        identity = dict(record['state_identity'], attempt=value)
        with pytest.raises(ContractError):
            validate_final_audit(raw(record), expected_identity=identity)


@pytest.mark.parametrize('tag', ['nan', '+inf', '-inf'])
def test_all_nonfinite_candidate_tags_preserved_with_undefined_dependents(tag):
    record = healthy()
    record.update(record_status='partial_error', reason='measurement_error')
    record['charge']['candidate_raw_sheet'] = {
        'status': 'error', 'value': None, 'nonfinite': tag, 'reason': 'nonfinite_measurement'}
    for key in ('candidate_lambda', 'candidate_constraint'):
        record['charge'][key] = {'status': 'error', 'value': None, 'nonfinite': None,
                                 'reason': 'invalid_prerequisite'}
    assert validate_final_audit(raw(record))['charge']['candidate_raw_sheet']['nonfinite'] == tag
    record['charge']['candidate_constraint'] = measured(0)
    with pytest.raises(ContractError):
        validate_final_audit(raw(record))


def test_text_limits_apply_to_utf8_bytes_and_reject_escaped_nul_surrogate():
    record = healthy()
    record['detail'] = 'я'*256
    assert len(validate_final_audit(raw(record))['detail']) == 256
    for text in ('\0', '\ud800'):
        record['detail'] = text
        payload = json.dumps(record, ensure_ascii=True).encode()
        with pytest.raises(ContractError):
            validate_final_audit(payload)


@pytest.mark.parametrize('payload,diagnostic', [
    (b' '*65537, '65536'),
    (b'{"x":' + b'['*10 + b'0' + b']'*10 + b'}', 'depth exceeds 9'),
    (b'{' + b','.join(b'"k%d":0' % i for i in range(1025)) + b'}', 'members exceed 1024'),
])
def test_hostile_budgets_fail_before_structural_postprocessing(payload, diagnostic):
    with pytest.raises(ContractError, match=diagnostic):
        validate_final_audit(payload)
