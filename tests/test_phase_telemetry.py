"""Manufactured producer metadata. No numerical run, old history, or referenced file reads."""
from copy import deepcopy
import importlib
import importlib.util
import json
import math
from pathlib import Path

import pytest

from qcl_negf_contracts import schema_validator
from qcl_negf_contracts.messages import ContractError, decode, encode

FIXTURES = Path(__file__).parent / 'fixtures/phase-telemetry'


def load(name):
    return json.loads((FIXTURES / name).read_text())


@pytest.fixture
def api():
    assert importlib.util.find_spec('qcl_negf_contracts.telemetry') is not None, 'producer phase API missing'
    return importlib.import_module('qcl_negf_contracts.telemetry')


@pytest.fixture
def normal():
    return load('normal-segment.json')


@pytest.fixture
def diagnostic():
    return load('diagnostic-segment.json')


@pytest.fixture
def messages():
    return load('source-messages.json')


def publish(api, segment, messages):
    return api.validate_phase_publication(messages['publication'], segment=segment,
        segment_ref=messages['normal_ref'], previous=messages['previous'], previous_ref=messages['previous_ref'])


def cursor(api, segment, messages):
    return api.validate_phase_cursor(messages['cursor'], publication=messages['publication'],
        publication_ref=messages['publication_ref'], segment=segment, segment_ref=messages['normal_ref'])


def incomplete(health, reason='manufactured_gap'):
    health.update(incomplete=True, incomplete_reasons=[reason])


def add_unprovided_ancestor(normal, messages):
    # A hypothetical ancestor can occupy generation 1/range 1..2. The supplied
    # previous header occupies generation 2/range 3..4; its segment is fresh.
    prior = messages['previous']
    prior.update(generation='2', first_sequence='3', last_sequence='4')
    prior['health'].update(events_seen='6', enqueued='6', sealed_events='4')
    prior['previous'] = dict(messages['previous_ref'], path='unprovided/ancestor.json')
    normal.update(first_sequence='6', last_sequence='10')
    normal['rows'][0].update(first_sequence='6', last_sequence='10')
    normal['rows'][1].update(first_sequence='8', last_sequence='8')
    messages['publication'].update(first_sequence='6', last_sequence='10')
    messages['cursor']['last_sequence']='10'


def test_new_api_is_present():
    module = importlib.import_module('qcl_negf_contracts.telemetry')
    for kind in ('segment', 'publication', 'current', 'cursor'):
        assert callable(getattr(module, 'validate_phase_'+kind, None)), 'producer phase API missing'


def test_diagnostic_preserves_exact_metrics_and_core_gaps(api, diagnostic):
    checked = api.validate_phase_segment(diagnostic)
    metrics = checked['rows'][1]['metrics']
    assert metrics[0] == dict(name='cpu_seconds', value=3.0, unit='s', measurement_status='measured', reason='process_inclusive_delta_on_end')
    assert metrics[1]['value'] == {'kind': 'integer', 'type': 'Int64', 'decimal': '9007199254740993'}
    assert math.copysign(1, metrics[2]['value']) == -1
    assert metrics[-1] == dict(name='optional', value=None, unit='', measurement_status='not_measured', reason='not_requested')
    assert checked['health']['incomplete'] is False
    checked['rows'][0]['metrics'].append(metrics[0])
    assert diagnostic['rows'][0]['metrics'] == []  # detached nested contents


def test_normal_nested_overlap_and_nonchronological_rows_are_legal(api, normal):
    checked = api.validate_phase_segment(normal)
    assert [r['last_sequence'] for r in checked['rows']] == ['8', '6']
    assert checked['rows'][0]['metrics'][1]['name'] == 'process_cpu_seconds'
    assert checked['rows'][0]['metrics'][2]['sum']['decimal'] == '9007199254740993'
    assert checked['health']['incomplete'] is False


@pytest.mark.parametrize('mode', ['normal', 'diagnostic'])
def test_modes_reject_other_kind_even_with_correct_bounds(api, normal, diagnostic, mode):
    value = normal if mode == 'diagnostic' else diagnostic
    value['mode'] = mode
    with pytest.raises(ContractError) as caught:
        api.validate_phase_segment(value)
    assert caught.value.code == 'invalid_input'


@pytest.mark.parametrize('field,new', [('schema', 'qcl-negf.producer-phase-segment.v2'), ('contract_set', 'qcl-negf.results.v1')])
def test_unknown_formats_are_unsupported(api, normal, field, new):
    normal[field] = new
    with pytest.raises(ContractError) as caught:
        api.validate_phase_segment(normal)
    assert caught.value.code == 'unsupported_format'


@pytest.mark.parametrize('change', ['unknown', 'missing_nullable', 'empty_rows', 'unsealed', 'numeric_count', 'count_overflow', 'extra_source'])
def test_closed_required_segment_shape(api, diagnostic, change):
    if change == 'unknown': diagnostic['unknown'] = None
    if change == 'missing_nullable': del diagnostic['rows'][0]['parent_span_id']
    if change == 'empty_rows': diagnostic['rows'] = []
    if change == 'unsealed': diagnostic['sealed'] = False
    if change == 'numeric_count': diagnostic['observed_events'] = 2
    if change == 'count_overflow': diagnostic['observed_events'] = '18446744073709551616'
    if change == 'extra_source': diagnostic['source']['host'] = 'not-a-field'
    with pytest.raises(ContractError) as caught:
        api.validate_phase_segment(diagnostic)
    assert caught.value.code == 'invalid_input'


@pytest.mark.parametrize('bad', [[], {}, {'kind':'integer','type':'Int64','decimal':'9223372036854775808'}, {'kind':'integer','type':'Int64','decimal':'01'}, {'kind':'integer','type':'UInt64','decimal':'1'}, float('nan'), float('inf')])
def test_scalar_rejects_non_scalar_nonfinite_and_bad_integer(api, diagnostic, bad):
    diagnostic['rows'][1]['metrics'][0]['value'] = bad
    with pytest.raises(ContractError):
        api.validate_phase_segment(diagnostic)


def test_error_metric_preserves_finite_value_and_null_nonfinite_reason(api, diagnostic):
    metric = diagnostic['rows'][1]['metrics'][0]
    metric.update(measurement_status='error', reason='counter_unavailable', value=3.0)
    assert api.validate_phase_segment(diagnostic)['rows'][1]['metrics'][0]['value'] == 3.0
    metric.update(value=None, reason='non_finite')
    assert api.validate_phase_segment(diagnostic)['rows'][1]['metrics'][0]['reason'] == 'non_finite'


@pytest.mark.parametrize('status,value,reason', [('measured', None, None), ('error', None, None), ('not_measured', 2.0, ''), ('not_applicable', None, None)])
def test_scalar_status_relations(api, diagnostic, status, value, reason):
    diagnostic['rows'][1]['metrics'][0].update(measurement_status=status, value=value, reason=reason)
    with pytest.raises(ContractError): api.validate_phase_segment(diagnostic)


@pytest.mark.parametrize('where', ['metrics', 'self_cost', 'aggregate_metrics', 'aggregate_key', 'reasons'])
def test_duplicate_keys_and_reasons_are_rejected(api, normal, diagnostic, where):
    if where == 'metrics':
        diagnostic['rows'][1]['metrics'].append(deepcopy(diagnostic['rows'][1]['metrics'][0])); value = diagnostic
    else:
        value = normal
        if where == 'self_cost': value['health']['self_cost'] *= 2
        if where == 'aggregate_metrics': value['rows'][0]['metrics'] *= 2
        if where == 'aggregate_key': value['rows'].append(deepcopy(value['rows'][0]))
        if where == 'reasons': value['rows'][0]['metrics'][0]['reasons'] = ['missing', 'missing']
    with pytest.raises(ContractError): api.validate_phase_segment(value)


def test_partial_sum_and_measured_input_overflow_remain_truthful(api, normal):
    metric = normal['rows'][0]['metrics'][0]
    metric.update(measured_calls='1', unavailable_calls='1', reasons=['not_measured'], sum=1.5)
    assert api.validate_phase_segment(normal)['rows'][0]['metrics'][0]['sum'] == 1.5
    metric.update(measured_calls='2', unavailable_calls='0', reasons=['counter_overflow'], sum=None)
    assert api.validate_phase_segment(normal)['rows'][0]['metrics'][0]['measured_calls'] == '2'
    metric.update(measured_calls='0', unavailable_calls='2', reasons=['not_requested'], sum=None)
    assert api.validate_phase_segment(normal)['rows'][0]['metrics'][0]['sum'] is None


@pytest.mark.parametrize('change', ['count', 'zero_nonnull', 'missing_sum_reason', 'unavailable_no_reason', 'cpu_old_name', 'core_half_null', 'core_reverse'])
def test_aggregate_relations(api, normal, change):
    row = normal['rows'][0]; metric = row['metrics'][0]
    if change == 'count': metric['measured_calls'] = '1'
    if change == 'zero_nonnull': metric.update(measured_calls='0', unavailable_calls='2', reasons=['unavailable'])
    if change == 'missing_sum_reason': metric['sum'] = None
    if change == 'unavailable_no_reason': metric.update(measured_calls='1', unavailable_calls='1')
    if change == 'cpu_old_name': metric['name'] = 'cpu_seconds'
    if change == 'core_half_null': row['first_core_sequence'] = None
    if change == 'core_reverse': row['first_core_sequence'] = '28'
    with pytest.raises(ContractError): api.validate_phase_segment(normal)


@pytest.mark.parametrize('change', ['bounds', 'coalesced', 'few_inputs', 'diagnostic_coalesced', 'diagnostic_order', 'diagnostic_gap'])
def test_local_ranges_and_batch_counts(api, normal, diagnostic, change):
    value = normal
    if change == 'bounds': value['first_sequence'] = '3'
    if change == 'coalesced': value['coalesced_events'] = '7'
    if change == 'few_inputs': value.update(observed_events='1', coalesced_events='0')
    if change.startswith('diagnostic'):
        value = diagnostic
        if change == 'diagnostic_coalesced': value['coalesced_events'] = '1'
        if change == 'diagnostic_order': value['rows'].reverse()
        if change == 'diagnostic_gap': value['rows'][1]['sequence'] = value['last_sequence'] = '3'
    with pytest.raises(ContractError): api.validate_phase_segment(value)


def test_diagnostic_explicit_gap_and_cross_segment_context(api, diagnostic):
    diagnostic['rows'][1]['sequence'] = diagnostic['last_sequence'] = '3'
    diagnostic['rows'][0].update(span_id=None, context_status='incomplete')
    incomplete(diagnostic['health'])
    assert api.validate_phase_segment(diagnostic)['last_sequence'] == '3'
    diagnostic['rows'] = [diagnostic['rows'][1]]
    diagnostic.update(first_sequence='3', observed_events='1')
    assert api.validate_phase_segment(diagnostic)['rows'][0]['action'] == 'phase_end'


@pytest.mark.parametrize('change', ['complete_no_span', 'self_parent', 'context_without_health', 'buffer_peak', 'drop_no_health', 'false_reasons', 'true_no_reason'])
def test_health_and_context_relations(api, diagnostic, change):
    health = diagnostic['health']; row = diagnostic['rows'][0]
    if change == 'complete_no_span': row['span_id'] = None
    if change == 'self_parent': row['parent_span_id'] = row['span_id']
    if change == 'context_without_health': row['context_status'] = 'incomplete'
    if change == 'buffer_peak': health['buffered_bytes'] = '257'
    if change == 'drop_no_health': health['dropped']['capacity'] = '1'
    if change == 'false_reasons': health['incomplete_reasons'] = ['missing']
    if change == 'true_no_reason': health['incomplete'] = True
    with pytest.raises(ContractError): api.validate_phase_segment(diagnostic)


@pytest.mark.parametrize('where,limit', [('clock', 512), ('span', 256)])
def test_utf8_byte_bounds_not_character_counts(api, diagnostic, where, limit):
    def assign(value):
        if where == 'clock': diagnostic['source']['clock_domain_id'] = value
        else: diagnostic['rows'][0]['span_id'] = value
    assign('я' * (limit//2))
    assert api.validate_phase_segment(diagnostic)
    assign('я' * (limit//2+1))
    with pytest.raises(ContractError): api.validate_phase_segment(diagnostic)


def test_publication_generation_gap_normal_coverage_and_later_health(api, normal, messages):
    messages['publication']['health']['events_seen'] = '14'
    messages['publication']['health']['self_cost'][0].update(value=0.001, measurement_status='measured', reason=None)
    assert publish(api, normal, messages)['generation'] == '3'
    assert publish(api, normal, messages)['health']['incomplete'] is False


@pytest.mark.parametrize('change', ['missing_previous', 'wrong_previous_ref', 'wrong_segment_ref', 'row_count', 'range', 'generation', 'owner', 'clock', 'decreasing_health', 'reuse_path', 'reuse_path_new_hash', 'missing_gap_evidence', 'previous_overlap', 'previous_generation', 'extra_initial_context', 'ref_media', 'ref_version', 'ref_path'])
def test_publication_rejects_bad_binding(api, normal, messages, change):
    pub = messages['publication']; prev = messages['previous']
    if change == 'missing_previous': messages['previous'] = None
    if change == 'wrong_previous_ref': messages['previous_ref']['sha256'] = '1'*64
    if change == 'wrong_segment_ref': messages['normal_ref']['sha256'] = '1'*64
    if change == 'row_count': pub['rows'] = '3'
    if change == 'range': pub['last_sequence'] = '9'
    if change == 'generation': pub['generation'] = '2'
    if change == 'owner': pub['identity']['attempt'] = '2'
    if change == 'clock': pub['source']['clock_domain_id'] = 'other'
    if change == 'decreasing_health': pub['health']['events_seen'] = '11'
    if change.startswith('reuse_path'):
        normal['segment_ordinal'] = pub['generation'] = '3'
        pub['segment']['path'] = messages['normal_ref']['path'] = prev['segment']['path']
        if change == 'reuse_path_new_hash': pub['segment']['sha256'] = messages['normal_ref']['sha256'] = '1'*64
    if change == 'missing_gap_evidence':
        normal['coalesced_events'] = normal['health']['coalesced_events'] = pub['health']['coalesced_events'] = '0'
    if change == 'previous_overlap': prev['last_sequence'] = '4'
    if change == 'previous_generation': prev['generation'] = '3'
    if change == 'extra_initial_context': pub['previous'] = None
    if change.startswith('ref_'):
        key, value = {'ref_media':('media_type','text/plain'), 'ref_version':('schema','qcl-negf.producer-phase-segment.v2'), 'ref_path':('path','../escape.json')}[change]
        pub['segment'][key] = messages['normal_ref'][key] = value
    with pytest.raises(ContractError): publish(api, normal, messages)


def test_initial_publication_rejects_unnecessary_previous_context(api, diagnostic, messages):
    checked = api.validate_phase_publication(messages['previous'], segment=diagnostic, segment_ref=messages['diagnostic_ref'])
    assert checked['previous'] is None
    with pytest.raises(ContractError):
        api.validate_phase_publication(messages['previous'], segment=diagnostic, segment_ref=messages['diagnostic_ref'], previous=messages['publication'])


def test_actual_drop_gap_requires_explicit_incomplete_evidence(api, normal, messages):
    normal['coalesced_events'] = normal['health']['coalesced_events'] = '0'
    for health in (normal['health'], messages['publication']['health']):
        health['coalesced_events'] = '0'; health['dropped']['capacity'] = '1'; incomplete(health, 'capacity')
    assert publish(api, normal, messages)['health']['incomplete']


@pytest.mark.parametrize('change', ['seen', 'dropped', 'reasons', 'sticky'])
def test_previous_health_is_cumulative(api, normal, messages, change):
    old = messages['previous']['health']; new = messages['publication']['health']
    if change == 'seen': old['events_seen'] = '13'
    if change == 'dropped': old['dropped']['capacity'] = '1'; incomplete(old, 'capacity'); incomplete(new, 'capacity')
    if change == 'reasons': incomplete(old, 'prior_reason'); incomplete(new, 'other_reason')
    if change == 'sticky': incomplete(old, 'prior_reason')
    with pytest.raises(ContractError): publish(api, normal, messages)


def test_health_gauges_can_decrease_without_counter_conservation(api, normal, messages):
    old = messages['previous']['health']; old.update(queued_events='999', buffered_bytes='128', inflight_bytes='9', unsealed_events='7')
    assert publish(api, normal, messages)['health']['queued_events'] == '0'


def test_current_binding_and_open_live_phase(api, messages):
    current = messages['current']
    assert api.validate_phase_current(current, publication=messages['publication'], publication_ref=messages['publication_ref'])['closed']
    current.update(publication=None, closed=False, current_phase=dict(stage='scba',phase='iteration',span_id='session-1:99'))
    assert not api.validate_phase_current(current)['health']['incomplete']
    current['closed'] = True; incomplete(current['health'], 'open_span')
    assert api.validate_phase_current(current)['health']['incomplete']


@pytest.mark.parametrize('change', ['missing_context', 'wrong_ref', 'wrong_owner', 'wrong_source', 'health_decrease', 'self_segment', 'self_previous', 'extra_null_context', 'closed_open', 'closed_queued', 'closed_buffered', 'closed_inflight', 'closed_unsealed'])
def test_current_rejects_invalid_context_and_silent_unclosed_tail(api, messages, change):
    value=messages['current']; pub=messages['publication']; reference=messages['publication_ref']
    if change == 'missing_context': pub=None
    if change == 'wrong_ref': reference['sha256']='1'*64
    if change == 'wrong_owner': value['identity']['branch_id']='other'
    if change == 'wrong_source': value['source']['session_id']='other'
    if change == 'health_decrease': value['health']['events_seen']='11'
    if change == 'self_segment': value['publication']['path']=reference['path']=pub['segment']['path']
    if change == 'self_previous': value['publication']['path']=reference['path']=pub['previous']['path']
    if change == 'extra_null_context': value['publication']=None
    if change == 'closed_open': value['current_phase']=dict(stage='',phase='',span_id=None)
    for suffix, field in [('queued','queued_events'),('buffered','buffered_bytes'),('inflight','inflight_bytes'),('unsealed','unsealed_events')]:
        if change == 'closed_'+suffix: value['health'][field]='1'
    with pytest.raises(ContractError): api.validate_phase_current(value, publication=pub, publication_ref=reference)


def test_cursor_prefix_uses_max_range_in_file_order(api, normal, messages):
    assert cursor(api, normal, messages)['last_sequence']=='8'
    messages['cursor'].update(next_row='1',last_sequence='8',complete_at_observation=False)
    assert cursor(api, normal, messages)['next_row']=='1'
    messages['cursor'].update(next_row='0',last_sequence='2')
    assert cursor(api, normal, messages)['last_sequence']=='2'
    messages['cursor'].update(next_row='2',last_sequence='8',complete_at_observation=False)
    assert not cursor(api, normal, messages)['complete_at_observation']


@pytest.mark.parametrize('change', ['past_end', 'old_last_row_upper', 'partial_complete', 'zero_at_first', 'wrong_pub_ref', 'wrong_seg_ref', 'owner', 'source', 'self_path', 'pub_segment_count'])
def test_cursor_rejects_inconsistent_progress_and_binding(api, normal, messages, change):
    value=messages['cursor']
    if change == 'past_end': value['next_row']='3'
    if change == 'old_last_row_upper': value['last_sequence']='6'
    if change == 'partial_complete': value['next_row']='1'
    if change == 'zero_at_first': value.update(next_row='0',last_sequence='4',complete_at_observation=False)
    if change == 'wrong_pub_ref': messages['publication_ref']['sha256']='1'*64
    if change == 'wrong_seg_ref': messages['normal_ref']['sha256']='1'*64
    if change == 'owner': value['identity']['run_id']='other'
    if change == 'source': value['source']['monotonic_anchor_ns']='18'
    if change == 'self_path': value['publication']['path']=messages['publication_ref']['path']=messages['normal_ref']['path']
    if change == 'pub_segment_count': messages['publication']['rows']='9'
    with pytest.raises(ContractError): cursor(api, normal, messages)


def test_offline_schemas_validate_all_manufactured_envelopes(normal, diagnostic, messages):
    for segment in (normal, diagnostic): schema_validator('producer-phase-segment.schema.json').validate(segment)
    validator=schema_validator('producer-phase-source.schema.json')
    for key in ('previous','publication','current','cursor'): validator.validate(messages[key])
    for key in ('previous','publication','current','cursor'):
        value=deepcopy(messages[key]); value['extra']=None
        assert not validator.is_valid(value)


def test_bounded_context_never_follows_previous_or_reads_referenced_files(api, normal, messages, monkeypatch):
    # The previous header pins an unprovided ancestor; this call must not recurse.
    add_unprovided_ancestor(normal, messages)
    messages['previous']['generation']='999999999999999998'
    normal['segment_ordinal']=messages['publication']['generation']='1000000000000000000'
    def forbidden(*args, **kwargs): raise AssertionError('referenced I/O or ancestry recursion')
    original_open = Path.open
    def package_only(path, *args, **kwargs):
        if 'qcl_negf_contracts' in path.parts:
            return original_open(path, *args, **kwargs)
        return forbidden(path, *args, **kwargs)
    monkeypatch.setattr(Path,'open',package_only)
    assert publish(api, normal, messages)['generation']=='1000000000000000000'
    # Cursor/Current need a local current Publication, not its ancestor context.
    assert cursor(api, normal, messages)['complete_at_observation']
    assert api.validate_phase_current(messages['current'],publication=messages['publication'],publication_ref=messages['publication_ref'])['closed']


def test_wire_encoding_round_trip_does_not_round_counts_or_tagged_ints(api, diagnostic):
    checked=api.validate_phase_segment(decode(encode(diagnostic),maximum=100000))
    assert checked['source']['utc_anchor_ns']=='9007199254740993'
    assert checked['rows'][1]['metrics'][1]['value']['decimal']=='9007199254740993'


@pytest.mark.parametrize('place', ['scalar', 'aggregate', 'self_cost'])
def test_number_branch_cannot_exceed_finite_float64(api, diagnostic, normal, place):
    value = diagnostic
    if place == 'scalar': diagnostic['rows'][1]['metrics'][0]['value'] = 10**400
    if place == 'aggregate': value=normal; normal['rows'][0]['metrics'][0]['sum'] = -(10**400)
    if place == 'self_cost': diagnostic['health']['self_cost'][0].update(value=10**400, measurement_status='measured', reason=None)
    with pytest.raises(ContractError): api.validate_phase_segment(value)


def test_finite_float64_endpoints_and_signed_integer_extremes(api, diagnostic):
    metrics=diagnostic['rows'][1]['metrics']
    metrics[0]['value']=1.7976931348623157e308
    metrics[1]['value']['decimal']='-9223372036854775808'
    checked=api.validate_phase_segment(diagnostic)
    assert checked['rows'][1]['metrics'][0]['value']==1.7976931348623157e308
    assert checked['rows'][1]['metrics'][1]['value']['decimal']=='-9223372036854775808'


@pytest.mark.parametrize('kind', ['current', 'cursor', 'publication'])
def test_source_envelopes_keep_required_nulls_and_reject_wrong_versions(api, normal, messages, kind):
    if kind == 'current':
        value=messages['current']
        run=lambda: api.validate_phase_current(value,publication=messages['publication'],publication_ref=messages['publication_ref'])
        field='current_phase'
    elif kind == 'cursor':
        value=messages['cursor']; run=lambda: cursor(api,normal,messages); field='complete_at_observation'
    else:
        value=messages['publication']; run=lambda: publish(api,normal,messages); field='previous'
    original=deepcopy(value)
    value['schema'] += '.future'
    with pytest.raises(ContractError) as caught: run()
    assert caught.value.code=='unsupported_format'
    value.clear(); value.update(original); del value[field]
    with pytest.raises(ContractError) as caught: run()
    assert caught.value.code=='invalid_input'


def test_two_content_limit_does_not_request_previous_segment(api, normal, messages, monkeypatch):
    original=api._publication_content
    inspected=[]
    def inspect(value):
        inspected.append(value['generation'])
        return original(value)
    monkeypatch.setattr(api,'_publication_content',inspect)
    add_unprovided_ancestor(normal, messages)
    assert publish(api,normal,messages)['generation']=='3'
    assert inspected==['3','2']
    inspected.clear()
    assert cursor(api,normal,messages)['last_sequence']=='10'
    assert inspected==['3']
    inspected.clear()
    api.validate_phase_current(messages['current'],publication=messages['publication'],publication_ref=messages['publication_ref'])
    assert inspected==['3']


def test_clock_literal_placement_survives_equal_sequences_and_sums(api, normal):
    # Two manufactured intervals: [9007199254741000,9007201254741000]
    # and [9007202254741000,9007204754741000]: 4.5s sum, 5.5s envelope.
    checked=api.validate_phase_segment(normal)
    assert checked['rows'][0]['time_bounds']==dict(min_start_monotonic_ns='9007199254741000',max_end_monotonic_ns='9007204754741000',measured_calls='2',unavailable_calls='0',reasons=[])
    shifted=deepcopy(normal)
    shifted['rows'][0]['time_bounds'].update(min_start_monotonic_ns='9007209254741000',max_end_monotonic_ns='9007214754741000')
    shifted['rows'][1]['time_bounds'].update(min_start_monotonic_ns='9007212754741000',max_end_monotonic_ns='9007213254741000')
    other=api.validate_phase_segment(shifted)
    assert other['rows'][0]['metrics']==checked['rows'][0]['metrics']
    assert other['first_sequence']==checked['first_sequence']=='4'
    assert other['last_sequence']==checked['last_sequence']=='8'
    assert other['rows'][0]['time_bounds']['min_start_monotonic_ns']=='9007209254741000'
    assert checked['rows'][0]['time_bounds']['min_start_monotonic_ns']=='9007199254741000'


def test_clock_bounds_are_required_without_legacy_fallback(api, normal):
    for row in normal['rows']: del row['time_bounds']
    with pytest.raises(ContractError) as caught: api.validate_phase_segment(normal)
    assert caught.value.code=='invalid_input'


@pytest.mark.parametrize('change', ['missing_key','unknown_key','numeric_start','negative_start','noncanonical_end','overflow_end','duplicate_reason','empty_reason'])
def test_clock_closed_shape_and_exact_counts(api, normal, change):
    clock=normal['rows'][0]['time_bounds']
    if change=='missing_key': del clock['max_end_monotonic_ns']
    if change=='unknown_key': clock['unit']='ns'
    if change=='numeric_start': clock['min_start_monotonic_ns']=9007199254741000
    if change=='negative_start': clock['min_start_monotonic_ns']='-1'
    if change=='noncanonical_end': clock['max_end_monotonic_ns']='01'
    if change=='overflow_end': clock['max_end_monotonic_ns']='18446744073709551616'
    if change=='duplicate_reason': clock['reasons']=['producer_clock_missing','producer_clock_missing']
    if change=='empty_reason': clock['reasons']=['']
    with pytest.raises(ContractError) as caught: api.validate_phase_segment(normal)
    assert caught.value.code=='invalid_input'


@pytest.mark.parametrize('change', ['count','half_null','positive_null','zero_nonnull','reverse','unavailable_no_reason','measured_reason'])
def test_clock_count_null_order_and_reason_relations(api, normal, change):
    clock=normal['rows'][0]['time_bounds']
    if change=='count': clock['measured_calls']='1'
    if change=='half_null': clock['min_start_monotonic_ns']=None
    if change=='positive_null': clock.update(min_start_monotonic_ns=None,max_end_monotonic_ns=None)
    if change=='zero_nonnull': clock.update(measured_calls='0',unavailable_calls='2',reasons=['producer_clock_missing'])
    if change=='reverse': clock['min_start_monotonic_ns']='9007204754741001'
    if change=='unavailable_no_reason': clock.update(measured_calls='1',unavailable_calls='1')
    if change=='measured_reason': clock['reasons']=['producer_clock_invalid']
    with pytest.raises(ContractError) as caught: api.validate_phase_segment(normal)
    assert caught.value.code=='corrupt_result'
    assert str(caught.value).startswith('$.rows[0].time_bounds')


def test_clock_partial_pair_envelope_is_independent_of_cpu_availability(api, normal):
    clock=normal['rows'][0]['time_bounds']
    clock.update(max_end_monotonic_ns='9007201254741000',measured_calls='1',unavailable_calls='1',reasons=['producer_clock_missing'])
    result=api.validate_phase_segment(normal)
    assert result['rows'][0]['time_bounds']['measured_calls']=='1'
    assert result['rows'][0]['metrics'][1]['measured_calls']=='2'
    # Opposite case: unavailable CPU delta, both actual clock pairs remain measured.
    clock.update(max_end_monotonic_ns='9007204754741000',measured_calls='2',unavailable_calls='0',reasons=[])
    normal['rows'][0]['metrics'][1].update(sum=None,measured_calls='0',unavailable_calls='2',reasons=['counter_unavailable'])
    result=api.validate_phase_segment(normal)
    assert result['rows'][0]['time_bounds']['measured_calls']=='2'
    assert result['rows'][0]['metrics'][1]['sum'] is None


@pytest.mark.parametrize('reason', ['producer_clock_missing','producer_clock_invalid','producer_clock_reversed','producer_clock_mismatch','non_finite'])
def test_clock_unavailable_preserves_declared_reasons_without_fake_zero(api, normal, reason):
    normal['rows'][0]['time_bounds'].update(min_start_monotonic_ns=None,max_end_monotonic_ns=None,measured_calls='0',unavailable_calls='2',reasons=[reason])
    result=api.validate_phase_segment(normal)
    assert result['rows'][0]['time_bounds']==dict(min_start_monotonic_ns=None,max_end_monotonic_ns=None,measured_calls='0',unavailable_calls='2',reasons=[reason])
    # Clock coverage is not the CPU measurement status or a callback drop counter.
    assert result['rows'][0]['metrics'][1]['measured_calls']=='2'
    assert result['health']['incomplete'] is False


def test_clock_zero_length_measured_and_cross_batch_overlap_are_legal(api, normal, messages):
    clock=normal['rows'][0]['time_bounds']
    clock.update(min_start_monotonic_ns='0',max_end_monotonic_ns='0')
    normal['rows'][0]['metrics'][0]['sum']=0.0
    assert api.validate_phase_segment(normal)['rows'][0]['time_bounds']['min_start_monotonic_ns']=='0'
    # A current batch's end-carried pair may begin before a previous seal.
    clock.update(min_start_monotonic_ns='9007198254741000',max_end_monotonic_ns='9007204754741000')
    normal['rows'][0]['metrics'][0]['sum']=4.5
    assert publish(api,normal,messages)['first_sequence']=='4'
    assert normal['rows'][1]['time_bounds']['max_end_monotonic_ns']=='9007203254741000'
    assert cursor(api,normal,messages)['last_sequence']=='8'


def test_clock_wire_does_not_admit_hidden_pair_trace_or_change_diagnostic_shape(api, normal, diagnostic):
    normal['rows'][0]['time_bounds']['pairs']=[['1','2']]
    with pytest.raises(ContractError): api.validate_phase_segment(normal)
    assert api.validate_phase_segment(diagnostic)['mode']=='diagnostic'
