"""Hand-authored metadata oracle: binding is not scientific acceptance."""
from copy import deepcopy

import pytest
from qcl_negf_contracts import messages
from qcl_negf_contracts.messages import ContractError

REASONS = ('process_failure', 'iteration_not_converged', 'physical_gate_failed',
           'interrupted', 'data_unavailable', 'assessment_unavailable', 'metadata_invalid')
PROJECTION = ('id', 'definition_id', 'variant_id', 'method_id', 'purpose', 'label',
              'operation', 'point_ids', 'repetition')
PLAN = {
    'schema': 'qcl-negf-scientific-plan-v2', 'model_revision': 'transport-contract-v2',
    'root_definition_id': 'study', 'name': 'hand metadata', 'fingerprint': 'a' * 64,
    'scientific_fingerprint': 'b' * 64, 'computation_count': 8,
    'executions': [
        {'id': 'e1', 'definition_id': 'study', 'variant_id': 'v1', 'method_id': 'm1',
         'purpose': 'transport', 'label': 'forward', 'operation': 'transport',
         'point_ids': ['p1', 'p2', 'p3', 'p4', 'p5', 'p6', 'ip1'], 'repetition': 1,
         'policies': {'opaque': 'frozen'}, 'resolved_configuration': {'opaque': 17}},
        {'id': 'e2', 'definition_id': 'study', 'variant_id': 'v2', 'method_id': 'm1',
         'purpose': 'transport', 'label': 'other', 'operation': 'transport',
         'point_ids': ['q1'], 'repetition': 1, 'policies': {}, 'resolved_configuration': {}},
    ],
    'points': [
        {'id': 'p1', 'execution_id': 'e1', 'temperature_K': 70, 'voltage_per_period_V': 0, 'branch': 'forward', 'order': 1, 'predecessor_id': None},
        {'id': 'p2', 'execution_id': 'e1', 'temperature_K': 70, 'voltage_per_period_V': .01, 'branch': 'forward', 'order': 2, 'predecessor_id': 'p1'},
        {'id': 'p3', 'execution_id': 'e1', 'temperature_K': 70, 'voltage_per_period_V': .02, 'branch': 'forward', 'order': 3, 'predecessor_id': 'p2'},
        {'id': 'p4', 'execution_id': 'e1', 'temperature_K': 70, 'voltage_per_period_V': .03, 'branch': 'forward', 'order': 4, 'predecessor_id': 'p3'},
        {'id': 'p5', 'execution_id': 'e1', 'temperature_K': 70, 'voltage_per_period_V': .04, 'branch': 'forward', 'order': 5, 'predecessor_id': 'p4'},
        {'id': 'p6', 'execution_id': 'e1', 'temperature_K': 70, 'voltage_per_period_V': .05, 'branch': 'forward', 'order': 6, 'predecessor_id': 'p5'},
        {'id': 'ip1', 'execution_id': 'e1', 'temperature_K': 70, 'voltage_per_period_V': 0, 'branch': 'forward', 'order': 1, 'predecessor_id': None},
        {'id': 'q1', 'execution_id': 'e2', 'temperature_K': 90, 'voltage_per_period_V': 0, 'branch': 'reverse', 'order': 1, 'predecessor_id': None},
    ],
}
SELF = {'code': 'BRANCH_STOPPED', 'scope': 'branch', 'reason_kind': 'process_failure',
        'source_execution_id': 'e1', 'source_point_id': 'p4', 'source_attempt': 1,
        'message': 'hand failure'}
DEPENDENCY = {'code': 'DEPENDENCY_UNAVAILABLE', 'scope': 'branch', 'reason_kind': 'process_failure',
              'source_execution_id': 'e1', 'source_point_id': 'p4', 'source_attempt': 1,
              'message': 'historical failure'}
P4 = {'id': 'p4', 'execution_id': 'e1', 'attempt': 1, 'coordinates': {'temperature_K': 70,
      'voltage_per_period_V': .03, 'branch': 'forward', 'order': 4},
      'warnings': [SELF], 'status': 'failed', 'data': {'checkpoint_source_attempt': 99}}
P5 = {'id': 'p5', 'execution_id': 'e1', 'attempt': 1, 'coordinates': {'temperature_K': 70,
      'voltage_per_period_V': .04, 'branch': 'forward', 'order': 5},
      'warnings': [], 'status': 'skipped'}
P6 = {'id': 'p6', 'execution_id': 'e1', 'attempt': 2, 'coordinates': {'temperature_K': 70,
      'voltage_per_period_V': .05, 'branch': 'forward', 'order': 6},
      'warnings': [DEPENDENCY], 'status': 'skipped', 'data': {'checkpoint_source_attempt': 7}}


def context(self_reason=False):
    plan = deepcopy(PLAN)
    snapshot = {'schema': 'qcl-negf-series-result-v3', 'contract_set': 'qcl-negf.results.v1',
                'plan_fingerprint': 'a' * 64, 'plan_scientific_fingerprint': 'b' * 64,
                'root_definition_id': 'study', 'name': 'hand metadata',
                'executions': [{key: deepcopy(entry[key]) for key in PROJECTION}
                               for entry in plan['executions']],
                'points': deepcopy([P4, P5, P6]), 'attempt_history': []}
    owner = snapshot['points'][0 if self_reason else 2]
    return {'plan': plan, 'owner_point': owner, 'owner_execution': plan['executions'][0],
            'source_points': snapshot}


def call(ctx):
    return messages.branch_reason(ctx['owner_point']['warnings'][0], **ctx)


def corrupt(ctx):
    with pytest.raises(ContractError) as error:
        call(ctx)
    assert error.value.code == 'corrupt_result'


@pytest.mark.parametrize('reason', REASONS)
def test_self_reason_is_detached_and_preserves_inputs(reason):
    ctx = context(True)
    ctx['owner_point']['warnings'][0]['reason_kind'] = reason
    before = deepcopy(ctx)
    expected = {**SELF, 'reason_kind': reason}
    actual = call(ctx)
    assert actual == expected
    assert ctx == before
    actual['message'] = 'detached'
    assert ctx == before


def test_exact_historical_ancestor_and_checkpoint_lineage():
    ctx = context()
    source = ctx['source_points']['points'].pop(0)
    ctx['source_points']['attempt_history'] = [source]
    assert call(ctx) == DEPENDENCY
    assert ctx['owner_point']['attempt'] == 2 and source['attempt'] == 1
    assert ctx['plan']['points'][5]['predecessor_id'] == 'p5'


@pytest.mark.parametrize('attempt', [2, 3, True, 1.0, '1', 0])
def test_exact_source_attempt_cannot_guess_latest(attempt):
    ctx = context()
    ctx['owner_point']['warnings'][0]['source_attempt'] = attempt
    corrupt(ctx)


def test_latest_source_without_historical_tuple_is_refused():
    ctx = context()
    ctx['source_points']['points'][0]['attempt'] = 2
    corrupt(ctx)


@pytest.mark.parametrize('change', ['absent', 'foreign', 'modified', 'unattached', 'projection', 'policy', 'result_descriptor', 'missing_history'])
def test_owner_and_snapshot_cannot_be_substituted(change):
    ctx = context()
    if change == 'absent': ctx['source_points']['points'].pop()
    if change == 'foreign': ctx['owner_point']['execution_id'] = 'e2'
    if change == 'modified':
        ctx['owner_point'] = deepcopy(ctx['owner_point']); ctx['owner_point']['status'] = 'completed'
    if change == 'unattached':
        record = deepcopy(ctx['owner_point']['warnings'][0]); ctx['owner_point']['warnings'] = []
        with pytest.raises(ContractError) as error: messages.branch_reason(record, **ctx)
        assert error.value.code == 'corrupt_result'; return
    if change == 'projection': ctx['owner_execution'] = ctx['source_points']['executions'][0]
    if change == 'policy':
        ctx['owner_execution'] = deepcopy(ctx['owner_execution']); ctx['owner_execution']['policies']['opaque'] = 'changed'
    if change == 'result_descriptor': ctx['source_points']['executions'][0]['extra'] = 1
    if change == 'missing_history': del ctx['source_points']['attempt_history']
    corrupt(ctx)


@pytest.mark.parametrize('field,value', [('temperature_K', 71), ('temperature_K', True), ('voltage_per_period_V', -1), ('branch', 'reverse'), ('order', True), ('order', 7)])
@pytest.mark.parametrize('row_index', [0, 2])
def test_every_indexed_row_has_exact_frozen_coordinates(field, value, row_index):
    ctx = context(); ctx['source_points']['points'][row_index]['coordinates'][field] = value
    corrupt(ctx)


@pytest.mark.parametrize('change', ['later', 'independent', 'foreign', 'cycle', 'unknown', 'cross_branch', 'cross_temperature', 'nonpreceding'])
def test_declared_full_ancestor_path_must_be_valid(change):
    ctx = context()
    points = ctx['plan']['points']
    if change == 'later': ctx['owner_point']['warnings'][0]['source_point_id'] = 'p6'
    if change == 'later': ctx['owner_point']['warnings'][0]['source_attempt'] = 1
    if change == 'independent': points[5]['predecessor_id'] = 'ip1'
    if change == 'foreign': ctx['owner_point']['warnings'][0]['source_execution_id'] = 'e2'
    if change == 'cycle': points[0]['predecessor_id'] = 'p3'
    if change == 'unknown': points[0]['predecessor_id'] = 'absent'
    if change == 'cross_branch': points[2]['branch'] = 'reverse'
    if change == 'cross_temperature': points[2]['temperature_K'] = 90
    if change == 'nonpreceding': points[2]['order'] = 4
    corrupt(ctx)


def test_identical_duplicate_is_allowed_but_conflict_is_not():
    ctx = context(); ctx['source_points']['attempt_history'] = [deepcopy(ctx['source_points']['points'][0])]
    assert call(ctx) == DEPENDENCY
    ctx['source_points']['attempt_history'][0]['status'] = 'completed'
    corrupt(ctx)


@pytest.mark.parametrize('record', [
    {'code': 'UNKNOWN', 'message': 'physical gate failed'},
    {'code': 'DEPENDENCY_UNAVAILABLE', 'scope': 'branch', 'message': 'failure'},
    {'code': 'UNKNOWN', 'source_point_id': 'p4'},
])
def test_legacy_has_no_context_or_message_inference(record):
    before = deepcopy(record)
    assert messages.branch_reason(record, plan=None, owner_point=None,
                                  owner_execution=None, source_points=None) is None
    assert record == before


@pytest.mark.parametrize('change', ['missing', 'extra', 'code', 'scope', 'reason', 'partial', 'bool', 'float', 'unicode', 'nonfinite', 'long', 'id_long', 'id_nonascii'])
def test_typed_claim_cannot_downgrade_or_escape_contract_error(change):
    ctx = context(True); record = ctx['owner_point']['warnings'][0]
    if change == 'missing': del record['message']
    if change == 'extra': record['extra'] = []
    if change == 'code': record['code'] = 'UNKNOWN'
    if change == 'scope': record['scope'] = 'point'
    if change == 'reason': record['reason_kind'] = 'unknown'
    if change == 'partial': record.clear(); record.update(code='DEPENDENCY_UNAVAILABLE', source_attempt=1)
    if change == 'bool': record['source_attempt'] = True
    if change == 'float': record['source_attempt'] = 1.0
    if change == 'unicode': record['message'] = '\ud800'
    if change == 'nonfinite': record['source_attempt'] = float('nan')
    if change == 'long': record['message'] = 'я' * 1024 + 'x'
    if change == 'id_long': record['source_point_id'] = 'p' * 129
    if change == 'id_nonascii': record['source_point_id'] = 'п4'
    corrupt(ctx)


def test_utf8_limit_counts_bytes():
    ctx = context(True); ctx['owner_point']['warnings'][0]['message'] = 'я' * 1024
    assert call(ctx)['message'] == 'я' * 1024


@pytest.mark.parametrize('target,field', [('plan', 'schema'), ('plan', 'model_revision'), ('source_points', 'schema'), ('source_points', 'contract_set')])
def test_unknown_contract_is_incompatible(target, field):
    ctx = context(); ctx[target][field] = 'unknown'
    with pytest.raises(ContractError) as error: call(ctx)
    assert error.value.code == 'incompatible_contract'


@pytest.mark.parametrize('field', ['plan_fingerprint', 'plan_scientific_fingerprint', 'root_definition_id', 'name'])
def test_snapshot_header_identity_must_match(field):
    ctx = context(); ctx['source_points'][field] = 'different'
    corrupt(ctx)


@pytest.mark.parametrize('change', ['duplicate_point', 'duplicate_execution', 'count', 'point_ids', 'frozen_bool', 'hash', 'owner_attempt'])
def test_relevant_plan_identity_and_types_are_not_assumed(change):
    ctx = context()
    if change == 'duplicate_point': ctx['plan']['points'].append(deepcopy(ctx['plan']['points'][0]))
    if change == 'duplicate_execution': ctx['plan']['executions'].append(deepcopy(ctx['plan']['executions'][0]))
    if change == 'count': ctx['plan']['computation_count'] = True
    if change == 'point_ids': ctx['plan']['executions'][0]['point_ids'].append('p4')
    if change == 'frozen_bool': ctx['plan']['points'][0]['temperature_K'] = True
    if change == 'hash': ctx['plan']['fingerprint'] = 'not-a-hash'
    if change == 'owner_attempt': ctx['owner_point']['attempt'] = True
    corrupt(ctx)


def test_owner_can_be_contained_only_in_history():
    ctx = context(); owner = ctx['source_points']['points'].pop()
    ctx['source_points']['attempt_history'] = [owner]
    assert call(ctx) == DEPENDENCY


def test_portable_id_upper_bound_is_accepted():
    ctx = context(True); identifier = 'p' * 128
    ctx['owner_point']['id'] = identifier
    ctx['owner_point']['warnings'][0]['source_point_id'] = identifier
    ctx['plan']['points'][3]['id'] = identifier
    ctx['plan']['points'][4]['predecessor_id'] = identifier
    ctx['plan']['executions'][0]['point_ids'][3] = identifier
    ctx['source_points']['executions'][0]['point_ids'][3] = identifier
    expected = {**SELF, 'source_point_id': 'p' * 128}
    assert call(ctx) == expected


@pytest.mark.parametrize('change', ['nan', 'surrogate', 'wrong_container', 'missing_owner_descriptor'])
def test_invalid_context_does_not_escape_contract_error(change):
    ctx = context()
    if change == 'nan': ctx['source_points']['points'][0]['data']['opaque'] = float('nan')
    if change == 'surrogate': ctx['plan']['executions'][0]['policies']['opaque'] = '\ud800'
    if change == 'wrong_container': ctx['source_points']['points'][0]['coordinates'] = []
    if change == 'missing_owner_descriptor': ctx['source_points']['executions'].pop(0)
    corrupt(ctx)


def test_existing_later_row_is_not_an_ancestor():
    ctx = context(True)
    ctx['owner_point']['warnings'][0]['source_point_id'] = 'p6'
    ctx['owner_point']['warnings'][0]['source_attempt'] = 2
    corrupt(ctx)


def test_independent_owner_cannot_claim_valid_foreign_branch_source():
    ctx = context()
    owner = ctx['owner_point']
    owner.update(id='ip1', coordinates={'temperature_K': 70,
                 'voltage_per_period_V': 0, 'branch': 'forward', 'order': 1})
    corrupt(ctx)


@pytest.mark.parametrize('location', ['attached_warning', 'opaque_snapshot_data'])
def test_integer_encoding_limit_is_normalized_to_contract_error(location):
    import sys
    limit = sys.get_int_max_str_digits()
    print(f'runtime_int_digit_limit={limit}; boundary={location}')
    if limit == 0 or limit >= 5001:
        pytest.skip('active integer digit limit does not reject hand-literal 5001-digit int')
    ctx = context()
    huge = 10 ** 5000
    if location == 'attached_warning':
        ctx['owner_point']['warnings'][0]['source_attempt'] = huge
    else:
        ctx['source_points']['points'][0]['data']['opaque'] = huge
    corrupt(ctx)


@pytest.mark.parametrize('self_source', [False, True])
def test_present_exact_future_source_attempt_is_refused(self_source):
    ctx = context(self_source)
    source = deepcopy(ctx['source_points']['points'][0])
    source['attempt'] = 2 if self_source else 3
    ctx['source_points']['attempt_history'].append(source)
    ctx['owner_point']['warnings'][0]['source_attempt'] = 2 if self_source else 3
    # The exact claimed tuple exists; its attempt bound must cause the refusal.
    corrupt(ctx)
