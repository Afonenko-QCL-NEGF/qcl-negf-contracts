"""Manufactured exact transport/state pins; no solver/filesystem provenance inference."""
from copy import deepcopy
import hashlib
import importlib
import json
import math
from pathlib import Path

import pytest
from qcl_negf_contracts.messages import ContractError
from qcl_negf_contracts.artifacts import validate_commit

FIXTURES = Path(__file__).parent / 'fixtures'

@pytest.fixture
def m():
    return json.loads((FIXTURES / 'telemetry-envelope/messages.json').read_text())

@pytest.fixture
def api():
    return importlib.import_module('qcl_negf_contracts.telemetry')

def test_new_technical_boundary_is_available(api):
    for kind in ('summary', 'source_binding', 'commit', 'pointer', 'binding'):
        assert callable(getattr(api, 'validate_telemetry_'+kind, None)), 'separate technical validator missing'

def check_commit(api, m, **extra):
    return api.validate_telemetry_commit(m['commit'], summary=m['summary'], summary_ref=m['summary_ref'], **extra)

def proof_args(m):
    return {k: m[k] for k in ('expected_state','expected_transport','manifest','manifest_ref','source_transport','canonical_plan_ref','expected_producer_provenance')}

def binding_args(m):
    return {**proof_args(m), **{k:m[k] for k in ('commit','commit_ref','summary','summary_ref','source_binding','source_binding_ref')}}

def test_exact_closed_binding_preserves_original_attempt_and_cpu(api,m):
    assert api.validate_telemetry_source_binding(m['source_binding'], **proof_args(m))['selected_state']['identity']['attempt']=='2'
    got=api.validate_telemetry_binding(m['binding'], **binding_args(m))
    assert got['transport']['selection']['attempt']==3
    assert got['commit']['raw_utf8'].endswith('\n')
    cpu=api.validate_telemetry_summary(m['summary'])['cpu_coverage']['allocations'][0]
    assert (cpu['cpu_seconds'],cpu['allocated_cpu_seconds'],cpu['fraction_of_observed_capacity'])==(3.0,4.0,0.75)
    check_commit(api,m)
    api.validate_telemetry_pointer(m['pointer'],commit=m['commit'],commit_ref=m['commit_ref'])
    got['selected_state']['identity']['attempt']='7'
    assert m['binding']['selected_state']['identity']['attempt']=='2'
    with pytest.raises(ContractError):validate_commit(m['commit'])

@pytest.mark.parametrize('field,value', [('generation',1),('generation','01'),('closed',1),('extra',None),('published_unix',float('inf'))])
def test_commit_rejects_bad_shape_and_nonfinite(api,m,field,value):
    m['commit'][field]=value
    with pytest.raises(ContractError):check_commit(api,m)

@pytest.mark.parametrize('which', ['state','transport','source_transport','plan','provenance','invocation','relation','converted'])
def test_binding_never_infers_aliases_or_mapping(api,m,which):
    proof=m['source_binding']
    if which=='state':proof['selected_state']['identity']['attempt']='3'
    elif which=='transport':proof['enclosing_transport']['selection']['plan_fingerprint']='b'*64
    elif which=='source_transport':proof['source_transport']['selection']['attempt']=3
    elif which=='plan':proof['canonical_plan']['sha256']='b'*64
    elif which=='provenance':proof['producer_provenance']['revision']='c'*40
    elif which=='invocation':proof['invocation']['source_epoch']='guessed-epoch'
    elif which=='relation':proof['relation']='produced'
    else:proof['plan_relation']='converted'
    with pytest.raises(ContractError):api.validate_telemetry_source_binding(proof,**proof_args(m))

@pytest.mark.parametrize('which',['raw','bytes','hash','fullref','newer','summary','state','receipt','open'])
def test_fixed_embedded_binding_rejects_substitution(api,m,which):
    b=m['binding']
    if which=='raw':b['commit']['raw_utf8']+=' '
    elif which=='bytes':b['summary']['ref']['bytes']='1'
    elif which=='hash':b['commit']['ref']['sha256']='b'*64
    elif which=='fullref':b['summary']['ref']['path']='other/summary.json'
    elif which=='newer':m['commit']['session']['source']['session_id']='newer'
    elif which=='summary':m['summary']['generation']='2'
    elif which=='state':b['selected_state']['state_id']='other-state'
    elif which=='receipt':m['source_binding_ref']['path']='other/source-binding.json'
    else:m['commit']['closed']=False
    with pytest.raises(ContractError):api.validate_telemetry_binding(b,**binding_args(m))

@pytest.mark.parametrize('which',['ratio','cpu_null','missing_capacity','unknown_zero','forecast','closed_tail','drops','gap','unit_type'])
def test_summary_unknowns_and_typed_relations_fail_closed(api,m,which):
    s=m['summary'];a=s['cpu_coverage']['allocations'][0]
    if which=='ratio':a['fraction_of_allocated_cpu']=0.5
    elif which=='cpu_null':a['cpu_seconds']=None
    elif which=='missing_capacity':a['allocated_cpu_seconds']=None
    elif which=='unknown_zero':s['observer_self_cost']['read_seconds']['value']=0
    elif which=='forecast':s['observer_self_cost']['arrow_io_forecast_bytes']['status']='measured'
    elif which=='closed_tail':s['durability']['uncommitted_resource_batch_at_risk']=True
    elif which=='drops':s['totals']['collector_dropped_rows']='1'
    elif which=='gap':s['coverage']['gaps']=[dict(source_key=None,clock_domain_id='clock',kind='detail_page_rotation',first_monotonic_ns='2',last_monotonic_ns='1',reason='uncovered')]
    else:s['max_observed_rss_bytes']=9007199254740993
    with pytest.raises(ContractError):api.validate_telemetry_summary(s)

def phase_case(m,stop=1):
    segment=json.loads((FIXTURES/'phase-telemetry/normal-segment.json').read_text())
    p=json.loads((FIXTURES/'phase-telemetry/source-messages.json').read_text())
    cursor=deepcopy(p['cursor']);cursor.update(next_row=str(stop),last_sequence='8',complete_at_observation=stop==2)
    source_key=hashlib.sha256(json.dumps(dict(identity=segment['identity'],source=segment['source']),sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()
    entry=dict(source_key=source_key,identity=segment['identity'],source=segment['source'],cursor=cursor,route_epoch='0',binding=dict(status='unbound',state=None,invocation=None,evidence=None,reason='producer_mapping_missing'),producer_health=segment['health'],source_closed=None,health_reason=None)
    ar=dict(source_key=source_key,publication=p['publication_ref'],segment=p['normal_ref'],retained_publication=dict(p['publication_ref'],path='performance/raw/pub.json'),retained_segment=dict(p['normal_ref'],path='performance/raw/seg.json'),mode='normal',first_row='0',stop_row=str(stop),cursor=cursor)
    m['commit']['source_cursors']=[entry];m['summary']['source_cursors']=[deepcopy(entry)];m['commit']['accepted_ranges']=[ar]
    m['summary']['totals'].update(accepted_source_rows=str(stop),accepted_aggregate_calls=str(2 if stop==1 else 3),coalesced_source_events='0' if stop==1 else '6')
    m['summary']['producer_phase_aggregates']=[dict(source_key=source_key,identity=segment['identity'],source=segment['source'],representation='normal_aggregate',aggregate=deepcopy(row)) for row in segment['rows'][:stop]]
    return dict(publication=p['publication'],publication_ref=p['publication_ref'],segment=segment,segment_ref=p['normal_ref'])

def test_normal_partial_prefix_keeps_exact_integer_and_no_fake_spans(api,m):
    ctx=phase_case(m)
    got=check_commit(api,m,phase_contexts=[ctx])
    assert got['accepted_ranges'][0]['stop_row']=='1'
    assert got['source_cursors'][0]['cursor']['last_sequence']=='8'
    s=api.validate_telemetry_summary(m['summary']); a=s['producer_phase_aggregates'][0]['aggregate']
    assert a['metrics'][0]['sum']==4.5 and a['call_count']=='2'
    assert a['metrics'][2]['sum']['decimal']=='9007199254740993'
    assert s['span_aggregates']==[]
    phase_case(m,2);check_commit(api,m,phase_contexts=[ctx])

@pytest.mark.parametrize('which',['overlap','ahead','unaccepted','source','unit','ref','binding','extra_context'])
def test_phase_ranges_reject_unaccepted_raw_suffix_and_foreign_context(api,m,which):
    ctx=phase_case(m);ar=m['commit']['accepted_ranges'][0]
    if which=='overlap':m['commit']['accepted_ranges'].append(deepcopy(ar))
    elif which=='ahead':ar['stop_row']='2'
    elif which=='unaccepted':m['summary']['totals']['accepted_source_rows']='2'
    elif which=='source':ar['source_key']='0'*64
    elif which=='unit':m['summary']['producer_phase_aggregates'][0]['aggregate']['metrics'][0]['unit']='B'
    elif which=='ref':ar['retained_segment']['sha256']='0'*64
    elif which=='binding':m['commit']['source_cursors'][0]['binding']['status']='bound'
    else:ctxs=[ctx,deepcopy(ctx)]
    with pytest.raises(ContractError):check_commit(api,m,phase_contexts=ctxs if which=='extra_context' else [ctx])

def test_partial_metric_overflow_and_negative_zero_remain_explicit(api,m):
    phase_case(m);a=m['summary']['producer_phase_aggregates'][0]['aggregate'];metric=a['metrics'][1]
    metric.update(sum=None,measured_calls='1',unavailable_calls='1',reasons=['counter_overflow','not_measured'])
    a['metrics'][0]['sum']=-0.0
    checked=api.validate_telemetry_summary(m['summary']);assert math.copysign(1,checked['producer_phase_aggregates'][0]['aggregate']['metrics'][0]['sum'])==-1
    metric['reasons']=[]
    with pytest.raises(ContractError):api.validate_telemetry_summary(m['summary'])

def next_page(m):
    previous=deepcopy(m['commit']); ps=deepcopy(m['summary'])
    baseline=dict(commit=m['commit_ref'],summary=m['summary_ref'])
    for v in (m['commit'],m['summary']):
        v['generation']='2';v['baseline']=deepcopy(baseline);v['session']['source']['session_id']='collector2';v['session']['source']['clock_domain_id']='collector:2'
    m['commit']['previous']=m['commit_ref'];m['summary']['rows']=dict(spans='0',resources='0',control_events='0');m['summary']['cpu_coverage']['allocations']=[]
    m['summary']['coverage'].update(incomplete=True,reasons=['endpoint_reset_detail_page_rotation'],gaps=[dict(source_key=None,clock_domain_id=None,kind='detail_page_rotation',first_monotonic_ns=None,last_monotonic_ns=None,reason='conservative_endpoint_reset_uncovered')])
    return dict(previous=previous,previous_ref=m['commit_ref'],previous_summary=ps,previous_summary_ref=m['summary_ref'])

def test_rotation_carries_measured_totals_once_and_declares_actual_cause(api,m):
    ctx=next_page(m);check_commit(api,m,**ctx)
    assert m['summary']['cpu_totals']['cpu_seconds']['value']==3.0
    assert m['summary']['coverage']['gaps'][0]['kind']=='detail_page_rotation'
    m['summary']['totals']['rows']['resources']='4'
    with pytest.raises(ContractError):check_commit(api,m,**ctx)

@pytest.mark.parametrize('which',['no_parent','changed_transport','open_parent','clock_same','extra_resume','baseline'])
def test_rotation_rejects_unproved_parent_and_foreign_page(api,m,which):
    ctx=next_page(m)
    if which=='no_parent':ctx['previous_ref']=None
    elif which=='changed_transport':m['commit']['transport']['selection']['attempt']=7
    elif which=='open_parent':ctx['previous']['closed']=False;ctx['previous_summary']['closed']=False;ctx['previous_summary']['durability']['uncommitted_resource_batch_at_risk']=True
    elif which=='clock_same':m['commit']['session']['source']['session_id']='collector1';m['summary']['session']['source']['session_id']='collector1'
    elif which=='extra_resume':ctx['resume_contexts']=[dict(commit=ctx['previous'],commit_ref=ctx['previous_ref'],summary=ctx['previous_summary'],summary_ref=ctx['previous_summary_ref'])]
    else:m['commit']['baseline']['summary']['sha256']='0'*64
    with pytest.raises(ContractError):check_commit(api,m,**ctx)


def test_missing_capacity_preserves_measured_cpu_and_known_zero(api,m):
    a=m['summary']['cpu_coverage']['allocations'][0]
    a.update(allocated_cpu_seconds=None,observed_capacity_cpu_seconds=None,capacity_unavailable_reason='actual allocation width unavailable',fraction_of_allocated_cpu=None,fraction_of_observed_capacity=None)
    for field in ('allocated_cpu_seconds','observed_capacity_cpu_seconds'):
        m['summary']['cpu_totals'][field].update(value=None,status='not_measured',reason='actual allocation width unavailable')
    got=api.validate_telemetry_summary(m['summary'])['cpu_coverage']['allocations'][0]
    assert got['cpu_seconds']==3.0 and got['fraction_of_allocated_cpu'] is None
    a.update(cpu_seconds=0.0,mean_busy_logical_cpus=0.0)
    m['summary']['cpu_totals']['cpu_seconds']['value']=0.0
    assert api.validate_telemetry_summary(m['summary'])['cpu_coverage']['allocations'][0]['cpu_seconds']==0.0


def test_cumulative_phase_summary_cannot_drop_or_double_count_accepted_calls(api,m):
    phase_case(m);previous=deepcopy(m['commit']);ps=deepcopy(m['summary']);previous['closed']=False;ps['closed']=False;ps['durability']['uncommitted_resource_batch_at_risk']=True
    m['commit'].update(previous=m['commit_ref'],generation='2');m['summary']['generation']='2';m['commit']['accepted_ranges']=[]
    m['summary']['producer_phase_aggregates'][0]['aggregate']['call_count']='4'
    m['summary']['producer_phase_aggregates'][0]['aggregate']['time_bounds']['measured_calls']='4'
    for metric in m['summary']['producer_phase_aggregates'][0]['aggregate']['metrics']:metric['measured_calls']='4'
    with pytest.raises(ContractError):check_commit(api,m,previous=previous,previous_ref=m['commit_ref'],previous_summary=ps,previous_summary_ref=m['summary_ref'])


def test_pure_pointer_rejects_self_reference_and_foreign_reference_schema(api,m):
    m['commit']['previous']=deepcopy(m['commit_ref'])
    with pytest.raises(ContractError):api.validate_telemetry_pointer(m['pointer'],commit=m['commit'],commit_ref=m['commit_ref'])
    m['commit']['previous']=None;m['commit']['summary']['schema']='qcl-negf.result-manifest.v1'
    with pytest.raises(ContractError) as error:check_commit(api,m)
    assert error.value.code=='unsupported_format'


def test_numeric_summary_cannot_claim_unaccepted_phase_key(api,m):
    phase_case(m)
    m['summary']['producer_phase_aggregates'][0]['aggregate']['phase']='invented'
    with pytest.raises(ContractError):check_commit(api,m)


def test_page_bounds_apply_to_one_page_and_resume_context_is_exact(api,m):
    ctx=phase_case(m);check_commit(api,m,phase_contexts=[ctx])
    ancestor=deepcopy(m['commit']);ancestor_summary=deepcopy(m['summary'])
    # After unrelated later pages, exact old source snapshot remains selectable.
    other=deepcopy(m);other['commit']['source_cursors']=[];other['summary']['source_cursors']=[];other['commit']['accepted_ranges']=[];other['summary']['producer_phase_aggregates']=[]
    prior=next_page(other);other['commit']['generation']='20';other['summary']['generation']='20'
    other['commit']['source_cursors']=deepcopy(m['commit']['source_cursors']);other['summary']['source_cursors']=deepcopy(m['summary']['source_cursors'])
    prior['previous']['generation']='19';prior['previous_summary']['generation']='19'
    resume=dict(commit=ancestor,commit_ref=m['commit_ref'],summary=ancestor_summary,summary_ref=m['summary_ref'])
    check_commit(api,other,**prior,resume_contexts=[resume])
    other['commit']['source_cursors'][0]['cursor']['next_row']='0'
    with pytest.raises(ContractError):check_commit(api,other,**prior,resume_contexts=[resume])


def transition(m, old_stop):
    old=phase_case(m,old_stop)
    # A fully consumed old prefix may still have incomplete-at-observation flag.
    for v in (m['commit'],m['summary']):v['source_cursors'][0]['cursor']['complete_at_observation']=False
    previous=deepcopy(m['commit']);ps=deepcopy(m['summary']);previous['closed']=False;ps['closed']=False;ps['durability']['uncommitted_resource_batch_at_risk']=True
    segment=deepcopy(old['segment']);segment['segment_ordinal']='4';segment['first_sequence']='10';segment['last_sequence']='14'
    for row in segment['rows']:
        row['first_sequence']=str(int(row['first_sequence'])+6);row['last_sequence']=str(int(row['last_sequence'])+6)
    sr=dict(old['segment_ref'],path='phase/segment-4.json',sha256='e'*64)
    publication=deepcopy(old['publication']);publication.update(generation='4',previous=old['publication_ref'],segment=sr,first_sequence='10',last_sequence='14')
    pr=dict(old['publication_ref'],path='phase/publication-4.json',sha256='f'*64)
    cursor=deepcopy(m['commit']['source_cursors'][0]['cursor']);cursor.update(publication=pr,segment=sr,next_row='1',last_sequence='14',complete_at_observation=False)
    for v in (m['commit'],m['summary']):v['source_cursors'][0]['cursor']=deepcopy(cursor)
    m['commit'].update(generation='2',previous=m['commit_ref']);m['summary']['generation']='2'
    ar=m['commit']['accepted_ranges'][0];ar.update(publication=pr,segment=sr,retained_publication=dict(pr,path='performance/raw/pub4.json'),retained_segment=dict(sr,path='performance/raw/seg4.json'),first_row='0',stop_row='1',cursor=cursor)
    m['summary']['totals']['accepted_source_rows']=str(old_stop+1);m['summary']['totals']['accepted_aggregate_calls']=str((2 if old_stop==1 else 3)+2)
    # Summary remains cumulative for accepted keys. Both iteration rows have calls2.
    a=m['summary']['producer_phase_aggregates'][0]['aggregate'];a['call_count']='4';a['last_sequence']='14';a['time_bounds']['measured_calls']='4'
    for metric in a['metrics']:
        metric['measured_calls']='4'
        if isinstance(metric['sum'],dict):metric['sum']['decimal']=str(int(metric['sum']['decimal'])*2)
        else:metric['sum']*=2
    new=dict(publication=publication,publication_ref=pr,segment=segment,segment_ref=sr)
    return dict(previous=previous,previous_ref=m['commit_ref'],previous_summary=ps,previous_summary_ref=m['summary_ref']), old,new


def test_transition_requires_full_physical_old_prefix_not_max_ordinal(api,m):
    prior,old,new=transition(m,1)
    with pytest.raises(ContractError):check_commit(api,m,**prior,phase_contexts=[old,new])


def test_transition_accepts_full_old_prefix_despite_false_completion_without_recount(api,m):
    prior,old,new=transition(m,2)
    check_commit(api,m,**prior,phase_contexts=[old,new])
    assert m['summary']['totals']['coalesced_source_events']=='6'
    assert m['summary']['totals']['accepted_source_rows']=='3'
    assert m['summary']['totals']['accepted_aggregate_calls']=='5'


@pytest.mark.parametrize('which',['missing','ref','identity'])
def test_transition_rejects_missing_or_foreign_old_proof(api,m,which):
    prior,old,new=transition(m,2)
    if which=='ref':old['segment_ref']['sha256']='0'*64
    elif which=='identity':old['segment']['identity']['branch_id']='foreign'
    with pytest.raises(ContractError):check_commit(api,m,**prior,phase_contexts=[new] if which=='missing' else [old,new])


def test_published_normal_units_are_preserved_without_conversion(api,m):
    ctx=phase_case(m)
    for owner in (ctx['segment']['rows'][0],m['summary']['producer_phase_aggregates'][0]['aggregate']):
        owner['metrics'][2]['unit']='bytes';owner['metrics'][4]['unit']=''
    got=check_commit(api,m,phase_contexts=[ctx])
    assert got['accepted_ranges'][0]['mode']=='normal'
    a=api.validate_telemetry_summary(m['summary'])['producer_phase_aggregates'][0]['aggregate']
    assert (a['metrics'][2]['unit'],a['metrics'][4]['unit'])==('bytes','')


def test_diagnostic_original_end_projection_keeps_real_clocks_and_raw_context(api,m):
    segment=json.loads((FIXTURES/'phase-telemetry/diagnostic-segment.json').read_text());p=json.loads((FIXTURES/'phase-telemetry/source-messages.json').read_text())
    end=segment['rows'][1]
    end['metrics'] += [dict(name=name,value=dict(kind='integer',type='Int64',decimal=value),unit='ns',measurement_status='measured',reason=None) for name,value in [('start_monotonic_ns','10'),('end_monotonic_ns','20'),('producer_monotonic_ns','20')]]
    publication=deepcopy(p['publication']);publication.update(generation='1',previous=None,segment=p['diagnostic_ref'],first_sequence='1',last_sequence='2',rows='2',health=segment['health'])
    pr=dict(p['publication_ref'],path='phase/publication-diag.json')
    cursor=dict(schema='qcl-negf.producer-phase-cursor.v1',contract_set='qcl-negf.results.v2',identity=segment['identity'],source=segment['source'],publication=pr,segment=p['diagnostic_ref'],next_row='2',last_sequence='2',complete_at_observation=True)
    sk=hashlib.sha256(json.dumps(dict(identity=segment['identity'],source=segment['source']),sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()
    entry=dict(source_key=sk,identity=segment['identity'],source=segment['source'],cursor=cursor,route_epoch='0',binding=dict(status='unbound',state=None,invocation=None,evidence=None,reason='mapping_missing'),producer_health=segment['health'],source_closed=None,health_reason=None)
    for v in (m['commit'],m['summary']):v['source_cursors']=[deepcopy(entry)]
    m['commit']['accepted_ranges']=[dict(source_key=sk,publication=pr,segment=p['diagnostic_ref'],retained_publication=dict(pr,path='performance/pubdiag.json'),retained_segment=dict(p['diagnostic_ref'],path='performance/diag.json'),mode='diagnostic',first_row='0',stop_row='2',cursor=cursor)]
    m['summary']['totals'].update(accepted_source_rows='2',accepted_diagnostic_events='2')
    m['summary']['producer_phase_aggregates']=[dict(source_key=sk,identity=segment['identity'],source=segment['source'],representation='diagnostic_end_projection',aggregate=dict(kind='aggregate',stage='scba',phase='iteration',status='running',task_width=None,counter_scope='process_inclusive_delta_on_end',first_sequence='2',last_sequence='2',first_core_sequence='11',last_core_sequence='11',call_count='1',metrics=[dict(name='process_cpu_seconds',unit='s',sum=3.0,measured_calls='1',unavailable_calls='0',reasons=[]),dict(name='allocated_bytes',unit='B',sum=dict(kind='integer',type='Int64',decimal='9007199254740993'),measured_calls='1',unavailable_calls='0',reasons=[])],time_bounds=dict(min_start_monotonic_ns='10',max_end_monotonic_ns='20',measured_calls='1',unavailable_calls='0',reasons=[])))]
    check_commit(api,m,phase_contexts=[dict(publication=publication,publication_ref=pr,segment=segment,segment_ref=p['diagnostic_ref'])])
    assert end['metrics'][3]['value'] is True and end['span_id']=='session-1:1'


@pytest.mark.parametrize('which',['unit','native_type'])
def test_mismatched_metric_profiles_never_sum_or_convert(api,m,which):
    prior,old,new=transition(m,2)
    actual=new['segment']['rows'][0]['metrics'][2]
    target=m['summary']['producer_phase_aggregates'][0]['aggregate']['metrics'][2]
    if which=='unit':actual['unit']='bytes';target['unit']='bytes'
    else:
        actual['sum']=9007199254740992.0;target['sum']=18014398509481984.0
    with pytest.raises(ContractError):check_commit(api,m,**prior,phase_contexts=[old,new])


def test_unbound_live_source_and_summary_only_omission_are_honest(api,m):
    ctx=phase_case(m);ar=m['commit']['accepted_ranges'][0]
    ar['retained_publication']=None;ar['retained_segment']=None
    m['summary']['retention'].update(mode='summary_only',omitted_source_rows='1',incomplete=True,reasons=['detail_policy'],omissions=[dict(source_key=ar['source_key'],segment=ar['segment'],first_row='0',stop_row='1',reason='summary_only_policy')])
    assert check_commit(api,m,phase_contexts=[ctx])['source_cursors'][0]['binding']['state'] is None
    assert m['summary']['totals']['accepted_source_rows']=='1'
    m['summary']['retention']['omissions'][0]['stop_row']='2'
    with pytest.raises(ContractError):check_commit(api,m,phase_contexts=[ctx])


def test_binding_duplicate_json_keys_and_shared_object_bound_are_rejected(api,m):
    row=m['binding']['summary'];raw=row['raw_utf8'];duplicate=raw.replace('"closed": true','"closed": true, "closed": true')
    row['raw_utf8']=duplicate;row['ref']['bytes']=str(len(duplicate.encode()));row['ref']['sha256']=hashlib.sha256(duplicate.encode()).hexdigest();m['summary_ref']=deepcopy(row['ref'])
    with pytest.raises(ContractError):api.validate_telemetry_binding(m['binding'],**binding_args(m))


def reembed(m):
    for key, refkey in [('summary','summary_ref'),('commit','commit_ref')]:
        if key=='commit':m['commit']['summary']=deepcopy(m['summary_ref'])
        raw=json.dumps(m[key],ensure_ascii=False,indent=1,allow_nan=False)+'\n'
        ref=dict(m[refkey],bytes=str(len(raw.encode())),sha256=hashlib.sha256(raw.encode()).hexdigest())
        m[refkey]=ref;m['binding'][key]=dict(ref=deepcopy(ref),raw_utf8=raw)


def test_retained_three_roots_share_one_actual_object_budget(api,m):
    phase_case(m)
    rows=[deepcopy(m['commit']['source_cursors'][0])]
    rows[0]['producer_health']['self_cost']=[dict(name='cost'+str(i),value=None,unit='',measurement_status='not_measured',reason='fixture_unknown') for i in range(32)]
    for i in range(1,16):
        row=deepcopy(rows[0]);row['source']['session_id']='producer'+str(i);row['cursor']['source']=deepcopy(row['source'])
        row['source_key']=hashlib.sha256(json.dumps(dict(identity=row['identity'],source=row['source']),sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest();rows.append(row)
    for v in (m['commit'],m['summary']):v['source_cursors']=deepcopy(rows)
    reembed(m)
    with pytest.raises(ContractError,match='object cap'):api.validate_telemetry_binding(m['binding'],**binding_args(m))


@pytest.mark.parametrize('which',['native_integer','float','integral_json_number'])
def test_aggregate_overflow_keeps_measured_call_counts_and_null_reason(api,m,which):
    prior,old,new=transition(m,2)
    pos=2 if which=='native_integer' else 1
    if which=='native_integer':
        a=dict(kind='integer',type='Int64',decimal='9223372036854775807');b=dict(kind='integer',type='Int64',decimal='1')
    else:a=b=1e308 if which=='float' else 10**308
    prior['previous_summary']['producer_phase_aggregates'][0]['aggregate']['metrics'][pos]['sum']=a
    new['segment']['rows'][0]['metrics'][pos]['sum']=b
    expected=m['summary']['producer_phase_aggregates'][0]['aggregate']['metrics'][pos]
    expected.update(sum=None,reasons=['counter_overflow'])
    check_commit(api,m,**prior,phase_contexts=[old,new])
    assert expected['measured_calls']=='4' and expected['unavailable_calls']=='0'


@pytest.mark.parametrize('field,value', [('cpu_seconds',999.0),('allocated_cpu_seconds',999.0),('observed_capacity_cpu_seconds',999.0),('valid_intervals','999'),('missing_samples','999'),('discontinuous_intervals','999'),('covered_wall_seconds',999.0)])
@pytest.mark.parametrize('entry',['summary','commit','binding'])
def test_cpu_rollup_genesis_matches_supplied_allocation_totals(api,m,field,value,entry):
    if field.endswith('cpu_seconds') or field=='cpu_seconds':m['summary']['cpu_totals'][field]['value']=value
    else:m['summary']['cpu_totals'][field]=value
    reembed(m)
    with pytest.raises(ContractError):
        if entry=='summary':api.validate_telemetry_summary(m['summary'])
        elif entry=='commit':check_commit(api,m)
        else:api.validate_telemetry_binding(m['binding'],**binding_args(m))


def cpu_page(m, *, same=False):
    """One literal additional CPU3/capacity4 interval, independently pinned metadata."""
    if same:
        m['commit']['closed']=False;m['summary']['closed']=False;m['summary']['durability']['uncommitted_resource_batch_at_risk']=True
        reembed(m)
    previous=dict(previous=deepcopy(m['commit']),previous_ref=deepcopy(m['commit_ref']),previous_summary=deepcopy(m['summary']),previous_summary_ref=deepcopy(m['summary_ref']))
    generation=str(int(m['commit']['generation'])+1)
    for obj in (m['commit'],m['summary']):obj.update(generation=generation,closed=True)
    m['summary']['durability']['uncommitted_resource_batch_at_risk']=False;m['commit']['previous']=deepcopy(previous['previous_ref'])
    if not same:
        for obj in (m['commit'],m['summary']):
            obj['session']['source'].update(session_id='cpu-page'+generation,clock_domain_id='cpu-clock'+generation)
            obj['baseline']=dict(commit=deepcopy(previous['previous_ref']),summary=deepcopy(previous['previous_summary_ref']))
        m['summary']['coverage'].update(incomplete=True,reasons=['endpoint_reset_uncovered'],gaps=[dict(source_key=None,clock_domain_id=None,kind='detail_page_rotation',first_monotonic_ns=None,last_monotonic_ns=None,reason='endpoint_reset_uncovered')])
    else:
        a=m['summary']['cpu_coverage']['allocations'][0]
        a.update(samples='3',valid_intervals='2',covered_wall_seconds=4.0,cpu_seconds=6.0,allocated_cpu_seconds=8.0,observed_capacity_cpu_seconds=8.0,fine_resolution_wall_seconds=4.0,last_sample_monotonic_ns='4000000000',observed_window_seconds=4.0)
        m['summary']['rows']['resources']='3'
    m['summary']['totals']['rows']['resources']='3' if same else '4'
    m['summary']['cpu_totals'].update(valid_intervals='2',covered_wall_seconds=4.0)
    for field,value in [('cpu_seconds',6.0),('allocated_cpu_seconds',8.0),('observed_capacity_cpu_seconds',8.0)]:m['summary']['cpu_totals'][field]['value']=value
    m['commit_ref']['path']='performance/commit-'+generation+'.json';m['summary_ref']['path']='performance/summary-'+generation+'.json';reembed(m)
    return previous


@pytest.mark.parametrize('same',[False,True])
def test_cpu_rollup_healthy_rotation_or_same_session_counts_interval_once(api,m,same):
    previous=cpu_page(m,same=same)
    assert check_commit(api,m,**previous)['generation']=='2'
    assert m['summary']['cpu_totals']['cpu_seconds']['value']==6.0


@pytest.mark.parametrize('field,value',[('cpu_seconds',999.0),('allocated_cpu_seconds',999.0),('observed_capacity_cpu_seconds',999.0),('valid_intervals','999'),('covered_wall_seconds',999.0)])
@pytest.mark.parametrize('same',[False,True])
def test_cpu_rollup_rejects_fabricated_rotation_or_same_session_totals(api,m,same,field,value):
    previous=cpu_page(m,same=same)
    if field.endswith('cpu_seconds') or field=='cpu_seconds':m['summary']['cpu_totals'][field]['value']=value
    else:m['summary']['cpu_totals'][field]=value
    with pytest.raises(ContractError):check_commit(api,m,**previous)


def test_cpu_rollup_same_session_after_baseline_uses_local_delta(api,m):
    cpu_page(m)
    previous=cpu_page(m,same=True)
    # Previous cumulative CPU6 includes old page3 and current page3;
    # current local CPU6 adds only3, so cumulative9, not12.
    m['summary']['totals']['rows']['resources']='5'
    m['summary']['cpu_totals'].update(valid_intervals='3',covered_wall_seconds=6.0)
    for field,value in [('cpu_seconds',9.0),('allocated_cpu_seconds',12.0),('observed_capacity_cpu_seconds',12.0)]:m['summary']['cpu_totals'][field]['value']=value
    check_commit(api,m,**previous)
    m['summary']['cpu_totals']['cpu_seconds']['value']=12.0
    with pytest.raises(ContractError):check_commit(api,m,**previous)


def test_cpu_rollup_missing_capacity_and_known_zero_are_distinct(api,m):
    a=m['summary']['cpu_coverage']['allocations'][0]
    a.update(cpu_seconds=0.0,mean_busy_logical_cpus=0.0,allocated_cpu_seconds=None,observed_capacity_cpu_seconds=None,capacity_unavailable_reason='allocation_width_unavailable',fraction_of_allocated_cpu=None,fraction_of_observed_capacity=None)
    m['summary']['cpu_totals']['cpu_seconds']['value']=0.0
    for field in ('allocated_cpu_seconds','observed_capacity_cpu_seconds'):m['summary']['cpu_totals'][field].update(value=None,status='not_measured',reason='allocation_width_unavailable')
    got=api.validate_telemetry_summary(m['summary'])['cpu_totals']
    assert got['cpu_seconds']['value']==0.0 and got['allocated_cpu_seconds']['value'] is None
    m['summary']['cpu_totals']['cpu_seconds'].update(value=None,status='not_measured',reason='invented_unknown')
    with pytest.raises(ContractError):api.validate_telemetry_summary(m['summary'])


def test_cpu_rollup_overflow_is_null_with_reason_and_measured_intervals(api,m):
    a=m['summary']['cpu_coverage']['allocations'][0]
    a.update(cpu_seconds=1e308,mean_busy_logical_cpus=5e307,fraction_of_allocated_cpu=2.5e307,fraction_of_observed_capacity=2.5e307)
    b=deepcopy(a);b['allocation_id']='second-allocation';m['summary']['cpu_coverage']['allocations'].append(b)
    m['summary']['cpu_totals'].update(valid_intervals='2',covered_wall_seconds=4.0)
    m['summary']['cpu_totals']['cpu_seconds'].update(value=None,status='error',reason='counter_overflow')
    for field in ('allocated_cpu_seconds','observed_capacity_cpu_seconds'):m['summary']['cpu_totals'][field]['value']=8.0
    assert api.validate_telemetry_summary(m['summary'])['cpu_totals']['valid_intervals']=='2'
    m['summary']['cpu_totals']['cpu_seconds'].update(value=1e308,status='measured',reason=None)
    with pytest.raises(ContractError):api.validate_telemetry_summary(m['summary'])


def test_cpu_rollup_missing_capacity_across_rotation_remains_unknown(api,m):
    previous=cpu_page(m)
    a=m['summary']['cpu_coverage']['allocations'][0]
    a.update(allocated_cpu_seconds=None,observed_capacity_cpu_seconds=None,capacity_unavailable_reason='current_width_unavailable',fraction_of_allocated_cpu=None,fraction_of_observed_capacity=None)
    for field in ('allocated_cpu_seconds','observed_capacity_cpu_seconds'):m['summary']['cpu_totals'][field].update(value=None,status='not_measured',reason='current_width_unavailable')
    check_commit(api,m,**previous)
    assert m['summary']['cpu_totals']['cpu_seconds']['value']==6.0
    m['summary']['cpu_totals']['allocated_cpu_seconds'].update(value=8.0,status='measured',reason=None)
    with pytest.raises(ContractError):check_commit(api,m,**previous)


def test_cpu_rollup_empty_detail_does_not_manufacture_zero_capacity(api,m):
    # Retained baseline may exist without any stable measured intervals.
    m['summary']['baseline']=dict(commit=m['commit_ref'],summary=m['summary_ref'])
    m['summary']['cpu_coverage']['allocations']=[]
    m['summary']['cpu_totals'].update(valid_intervals='0',covered_wall_seconds=0.0)
    for field in ('cpu_seconds','allocated_cpu_seconds','observed_capacity_cpu_seconds'):m['summary']['cpu_totals'][field].update(value=None,status='not_measured',reason='no_stable_interval')
    api.validate_telemetry_summary(m['summary'])
    m['summary']['cpu_totals']['allocated_cpu_seconds'].update(value=0.0,status='measured',reason=None)
    with pytest.raises(ContractError):api.validate_telemetry_summary(m['summary'])


def test_cpu_rollup_zero_valid_allocation_has_no_measured_wall(api,m):
    a=m['summary']['cpu_coverage']['allocations'][0]
    a.update(valid_intervals='0',cpu_seconds=None,allocated_cpu_seconds=None,observed_capacity_cpu_seconds=None,cpu_unavailable_reason='no_stable_interval',mean_busy_logical_cpus=None,fraction_of_allocated_cpu=None,fraction_of_observed_capacity=None)
    for field in ('cpu_seconds','allocated_cpu_seconds','observed_capacity_cpu_seconds'):m['summary']['cpu_totals'][field].update(value=None,status='not_measured',reason='no_stable_interval')
    m['summary']['cpu_totals']['valid_intervals']='0'
    with pytest.raises(ContractError):api.validate_telemetry_summary(m['summary'])


def test_cpu_rollup_known_new_capacity_cannot_fill_unknown_baseline(api,m):
    a=m['summary']['cpu_coverage']['allocations'][0]
    a.update(allocated_cpu_seconds=None,observed_capacity_cpu_seconds=None,capacity_unavailable_reason='old_width_unavailable',fraction_of_allocated_cpu=None,fraction_of_observed_capacity=None)
    for field in ('allocated_cpu_seconds','observed_capacity_cpu_seconds'):m['summary']['cpu_totals'][field].update(value=None,status='not_measured',reason='old_width_unavailable')
    reembed(m);previous=cpu_page(m)
    a=m['summary']['cpu_coverage']['allocations'][0]
    a.update(allocated_cpu_seconds=4.0,observed_capacity_cpu_seconds=4.0,capacity_unavailable_reason=None,fraction_of_allocated_cpu=0.75,fraction_of_observed_capacity=0.75)
    for field in ('allocated_cpu_seconds','observed_capacity_cpu_seconds'):m['summary']['cpu_totals'][field].update(value=None,status='not_measured',reason='old_width_unavailable')
    check_commit(api,m,**previous)
    m['summary']['cpu_totals']['observed_capacity_cpu_seconds'].update(value=8.0,status='measured',reason=None)
    with pytest.raises(ContractError):check_commit(api,m,**previous)


@pytest.mark.parametrize('field',['cpu_seconds','allocated_cpu_seconds','observed_capacity_cpu_seconds'])
def test_cpu_rollup_same_session_known_quantity_cannot_decrease(api,m,field):
    previous=cpu_page(m,same=True)
    a=m['summary']['cpu_coverage']['allocations'][0]
    a[field]=2.0;m['summary']['cpu_totals'][field]['value']=2.0
    a['mean_busy_logical_cpus']=a['cpu_seconds']/a['covered_wall_seconds']
    a['fraction_of_allocated_cpu']=a['cpu_seconds']/a['allocated_cpu_seconds']
    a['fraction_of_observed_capacity']=a['cpu_seconds']/a['observed_capacity_cpu_seconds']
    reembed(m)
    with pytest.raises(ContractError):check_commit(api,m,**previous)


def test_cpu_rollup_local_negative_delta_rejected_when_global_float_rounds_equal(api,m):
    a=m['summary']['cpu_coverage']['allocations'][0]
    a.update(cpu_seconds=1e30,mean_busy_logical_cpus=5e29,fraction_of_allocated_cpu=2.5e29,fraction_of_observed_capacity=2.5e29)
    m['summary']['cpu_totals']['cpu_seconds']['value']=1e30;reembed(m)
    first=cpu_page(m)
    a=m['summary']['cpu_coverage']['allocations'][0]
    a.update(cpu_seconds=3.0,mean_busy_logical_cpus=1.5,fraction_of_allocated_cpu=0.75,fraction_of_observed_capacity=0.75)
    m['summary']['cpu_totals']['cpu_seconds']['value']=1e30
    check_commit(api,m,**first);reembed(m)
    previous=cpu_page(m,same=True)
    a=m['summary']['cpu_coverage']['allocations'][0]
    a.update(cpu_seconds=2.0,mean_busy_logical_cpus=0.5,fraction_of_allocated_cpu=0.25,fraction_of_observed_capacity=0.25)
    m['summary']['totals']['rows']['resources']='5'
    m['summary']['cpu_totals'].update(valid_intervals='3',covered_wall_seconds=6.0)
    m['summary']['cpu_totals']['cpu_seconds']['value']=1e30
    for field in ('allocated_cpu_seconds','observed_capacity_cpu_seconds'):m['summary']['cpu_totals'][field]['value']=12.0
    # Float64 global1e30 cannot expose the local -1. Local3→2 still must fail.
    with pytest.raises(ContractError,match='local'):check_commit(api,m,**previous)


def test_cpu_rollup_same_session_measured_zero_interval_remains_measured(api,m):
    a=m['summary']['cpu_coverage']['allocations'][0]
    a.update(cpu_seconds=0.0,mean_busy_logical_cpus=0.0,fraction_of_allocated_cpu=0.0,fraction_of_observed_capacity=0.0)
    m['summary']['cpu_totals']['cpu_seconds']['value']=0.0;reembed(m)
    previous=cpu_page(m,same=True)
    a=m['summary']['cpu_coverage']['allocations'][0]
    a.update(cpu_seconds=0.0,mean_busy_logical_cpus=0.0,fraction_of_allocated_cpu=0.0,fraction_of_observed_capacity=0.0)
    m['summary']['cpu_totals']['cpu_seconds']['value']=0.0
    check_commit(api,m,**previous)
    assert m['summary']['cpu_totals']['cpu_seconds']['status']=='measured'


def test_cpu_rollup_same_session_measured_to_overflow_is_not_negative_delta(api,m):
    previous=cpu_page(m,same=True)
    a=m['summary']['cpu_coverage']['allocations'][0]
    a.update(cpu_seconds=1e308,mean_busy_logical_cpus=2.5e307,fraction_of_allocated_cpu=1.25e307,fraction_of_observed_capacity=1.25e307)
    b=deepcopy(a);b.update(allocation_id='second-allocation',samples='2',valid_intervals='1',covered_wall_seconds=2.0,cpu_seconds=1e308,allocated_cpu_seconds=4.0,observed_capacity_cpu_seconds=4.0,fine_resolution_wall_seconds=2.0,last_sample_monotonic_ns='2000000000',observed_window_seconds=2.0,mean_busy_logical_cpus=5e307,fraction_of_allocated_cpu=2.5e307,fraction_of_observed_capacity=2.5e307)
    m['summary']['cpu_coverage']['allocations'].append(b)
    m['summary']['rows']['resources']='5';m['summary']['totals']['rows']['resources']='5'
    m['summary']['cpu_totals'].update(valid_intervals='3',covered_wall_seconds=6.0)
    for field in ('allocated_cpu_seconds','observed_capacity_cpu_seconds'):m['summary']['cpu_totals'][field]['value']=12.0
    m['summary']['cpu_totals']['cpu_seconds'].update(value=None,status='error',reason='counter_overflow')
    check_commit(api,m,**previous)
    assert m['summary']['cpu_totals']['cpu_seconds']['value'] is None


def test_cpu_rollup_rotation_may_reset_local_to_measured_zero_without_global_loss(api,m):
    previous=cpu_page(m)
    a=m['summary']['cpu_coverage']['allocations'][0]
    a.update(cpu_seconds=0.0,mean_busy_logical_cpus=0.0,fraction_of_allocated_cpu=0.0,fraction_of_observed_capacity=0.0)
    m['summary']['cpu_totals']['cpu_seconds']['value']=3.0
    check_commit(api,m,**previous)
    assert m['summary']['cpu_totals']['cpu_seconds']['value']==3.0
    assert a['cpu_seconds']==0.0
