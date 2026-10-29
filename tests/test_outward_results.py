"""Manufactured outward refs/context joins; no producer, file, HDF or physics proof."""
from copy import deepcopy
import hashlib
import importlib
import importlib.util
import json
from pathlib import Path

import pytest

from qcl_negf_contracts import load_schema, schema_names, schema_validator
from qcl_negf_contracts.messages import ContractError, decode, encode
from test_final_observations import inputs as final_inputs, restored

FIXTURE = Path(__file__).parent / 'fixtures/outward-result/messages.json'


@pytest.fixture
def m():
    return json.loads(FIXTURE.read_text())


def api():
    assert importlib.util.find_spec('qcl_negf_contracts.outward') is not None, 'outward pure module missing'
    return importlib.import_module('qcl_negf_contracts.outward')


def check(value):
    return api().validate_outward_result(value)


def native(kind='scientific_plan_v2', parent=False):
    observations, context = restored() if parent else final_inputs(kind)
    manifest = context['manifest']
    for name in ('convergence', 'physics'):
        manifest['status'][name] = dict(state='recorded', reason=None, evidence=deepcopy(context['artifact_ref']))
    reference = dict(path='manifests/selected.json', bytes=str(len(encode(manifest))),
        sha256=hashlib.sha256(encode(manifest)).hexdigest(), media_type='application/json', schema=manifest['schema'])
    source = dict(schema='qcl-negf.native-point-source.v1', kind='final', artifact_root='.',
        relation='current_point_attempt', selected_state={**{name:deepcopy(manifest[name]) for name in
            ('identity', 'state_id', 'state_sequence')}, 'manifest':reference},
        diagnostics=deepcopy(observations['diagnostics']), observations=deepcopy(context['artifact_ref']), reason=None)
    return source, {name:context[name] for name in ('manifest', 'checkpoint', 'diagnostics', 'plan', 'model')}, observations


def bind(source, context, observations=None, **extra):
    return api().validate_outward_native_source(source, manifest_ref=source['selected_state']['manifest'],
        observations=observations, **context, **extra)


def test_public_schema_and_two_pure_ports_are_available():
    assert 'outward-result.schema.json' in schema_names(), 'versioned outward schema missing'
    assert callable(getattr(api(), 'validate_outward_result', None))
    assert callable(getattr(api(), 'validate_outward_native_source', None))


@pytest.mark.parametrize('key', ['source','absent','series','current','configured','configured_status'])
def test_literal_versions_preserve_refs_raw_units_and_nonpassing_classification(m, key):
    value=m[key]; before=deepcopy(value); checked=check(decode(encode(value)))
    assert checked == before and checked is not value and value == before
    if key == 'series':
        assert checked['points'][0]['observables']['scientific_assessment']['scientific_accepted'] is False
        assert checked['points'][0]['data']['literal_scalar_extension'] == 'kept'
    if key == 'current':
        assert [(x['value'], x['unit']) for x in checked['metrics']] == [(0,''), ('exact',''), (False,'')]


@pytest.mark.parametrize('collection', ['points','attempt_history'])
@pytest.mark.parametrize('change', ['unknown_object','phase_extra','phase_string','partial_final','legacy_alias'])
def test_both_point_collections_enforce_same_closed_named_carriers(m, collection, change):
    value=m['series']; row=value[collection][0]
    if change == 'unknown_object': row['data']['unknown_extension']=deepcopy(row['data']['native_source'])
    elif change == 'phase_extra': row['data']['phase_source']['pass']=True
    elif change == 'phase_string': row['data']['phase_source']=json.dumps(row['data']['phase_source'])
    elif change == 'partial_final': row['data']['native_source']['observations']=None
    else: row['data']['result_commit']='manifests/m1.json'
    with pytest.raises(ContractError): check(value)


def test_v3_shape_and_legacy_progress_validator_are_not_relaxed(m):
    old=m['series']; old['schema']='qcl-negf-series-result-v3'
    for collection in ('points','attempt_history'):
        old[collection][0]['data']={'result_commit':'archive/exec/point/final/commit.json'}
    schema_validator('scientific-worker-result.schema.json').validate(old)
    old['points'][0]['data']['phase_source']=m['phase']
    assert not schema_validator('scientific-worker-result.schema.json').is_valid(old)
    with pytest.raises(ContractError): check(old)


@pytest.mark.parametrize('status,reason', [('disabled','telemetry_disabled'),('unavailable','writer_busy')])
def test_disabled_and_busy_phase_are_explicit_without_erasing_science(m, status, reason):
    value=m['current']; value['phase_source']=dict(status=status,session_id=None,current_path=None,reason=reason)
    got=check(value)
    assert got['native_source']['selected_state'] == m['source']['selected_state']
    assert got['phase_source']['reason'] == reason


@pytest.mark.parametrize('field,bad', [('status','busy'),('reason',''),('reason','not_published'),('session_id',None),('current_path','../phase.json'),('current_path','/phase.json')])
def test_phase_locator_is_closed_and_never_a_scientific_fileref(m, field, bad):
    value=m['current']; value['phase_source'][field]=bad
    with pytest.raises(ContractError): check(value)


@pytest.mark.parametrize('kind', ['checkpoint','absent'])
def test_honest_nonfinal_source_has_no_partial_analysis_claim(m, kind):
    value=m['source']; value.update(kind=kind,diagnostics=None,observations=None,reason='final_not_published')
    if kind == 'absent': value.update(relation=None,selected_state=None)
    assert check(value)['reason'] == 'final_not_published'
    value['reason']=None
    with pytest.raises(ContractError): check(value)


@pytest.mark.parametrize('target', ['selected_state.manifest','diagnostics','observations'])
@pytest.mark.parametrize('field,bad', [('bytes',1),('bytes','01'),('bytes','18446744073709551616'),('sha256','ABC'),('media_type','text/plain'),('schema','legacy'),('path','../escape')])
def test_exact_native_reference_atoms_and_schema_media_do_not_alias(m, target, field, bad):
    value=m['source']; selected=value
    for part in target.split('.'): selected=selected[part]
    selected[field]=bad
    with pytest.raises(ContractError): check(value)


@pytest.mark.parametrize('root', ['', '/tmp/native', '../native','a/../native','a//native','a\\native'])
def test_native_root_is_explicit_canonical_owner_relative_locator(m, root):
    m['source']['artifact_root']=root
    with pytest.raises(ContractError): check(m['source'])


@pytest.mark.parametrize('attempt', [True,1.0,'1',0,18446744073709551616])
def test_point_counter_types_do_not_invent_native_or_transport_identity(m, attempt):
    m['current']['attempt']=attempt
    with pytest.raises(ContractError): check(m['current'])


@pytest.mark.parametrize('which', ['point','execution','attempt','retained_equal','retained_future','retained_reason'])
def test_current_and_retained_source_relations_have_exact_point_counter_scope(m, which):
    value=m['current']; source=value['native_source']
    if which == 'point': source['selected_state']['identity']['point_id']='foreign'
    elif which == 'execution': source['selected_state']['identity']['execution_id']='foreign'
    elif which == 'attempt': source['selected_state']['identity']['attempt']='2'
    else:
        source.update(relation='retained_source',reason='last_committed_before_pause')
        if which == 'retained_future': source['selected_state']['identity']['attempt']='2'
        elif which == 'retained_reason': value['attempt']=2; source['reason']=None
    with pytest.raises(ContractError): check(value)


def test_retained_original_state_does_not_become_child_attempt(m):
    value=m['current']; value['attempt']=3
    value['native_source'].update(relation='retained_source',reason='last_committed_before_pause')
    assert check(value)['native_source']['selected_state']['identity']['attempt'] == '1'
    assert value['attempt'] == 3


@pytest.mark.parametrize('change', ['duplicate','nonchronological','current_differs','unknown_execution','wrong_count','stationary_legacy'])
def test_series_selection_and_history_never_infer_order_or_drop_native_rows(m, change):
    value=m['series']
    if change == 'duplicate': value['attempt_history'].append(deepcopy(value['attempt_history'][0]))
    elif change == 'nonchronological':
        older=deepcopy(value['attempt_history'][0]); older['attempt']=2
        older['data']['native_source']['selected_state']['identity']['attempt']='2'
        value['attempt_history'].insert(0,older)
    elif change == 'current_differs': value['attempt_history'][0]['quality']='unconverged'
    elif change == 'unknown_execution': value['points'][0]['execution_id']='foreign'
    elif change == 'wrong_count': value['available_point_count']=0
    else:
        value['attempt_history']=[];value['points'][0]['data']['native_source']=m['absent']
        value['points'][0]['data']['result_commit']='archive/exec/point/final/commit.json'
    with pytest.raises(ContractError): check(value)


@pytest.mark.parametrize('change', ['run','pending_measured','result_status','metric_null','metric_no_reason','nonfinite'])
def test_configured_current_and_metric_structures_preserve_actual_port_semantics(m, change):
    value=m['configured']
    if change == 'run': value['run_id']='foreign'
    elif change == 'pending_measured': value=m['configured_status'];value['native_source']=m['source']
    elif change == 'result_status': value['status']='succeeded'
    elif change == 'metric_null': value=m['current'];value['metrics'][0]['value']=None
    elif change == 'metric_no_reason': value=m['current'];value['metrics'][0]['measurement_status']='error'
    else: value=m['current'];value['updated_unix']=float('inf')
    with pytest.raises(ContractError): check(value)


def test_structural_optical_edge_is_optional_and_keeps_stationary_selection(m):
    value=m['configured'];source=value['result']['native_source']; publication=deepcopy(source['selected_state'])
    publication['manifest'].update(path='manifests/optical.json',sha256='f'*64)
    attachment=dict(source_state=deepcopy(source['selected_state']),publication_state=publication,
        artifact=dict(path='analysis/optical.h5',bytes='404',sha256='0'*64,media_type='application/x-hdf5',schema='qcl-negf-optical-v5'))
    value['result'].update(optical_attachment=attachment,postprocessing={'optical':{'status':'completed','error':None}})
    got=check(value)
    assert got['result']['native_source'] == source
    assert got['result']['optical_attachment']['source_state']['manifest']['path'] == 'manifests/m1.json'
    assert got['result']['optical_attachment']['publication_state']['manifest']['path'] == 'manifests/optical.json'
    # This is only structural, not a fabricated optical codec/native acceptance.


@pytest.mark.parametrize('change', ['completed_without_attachment','failed_with_attachment','wrong_source','old_optical','same_publication','extra'])
def test_optical_lifecycle_never_replaces_source_or_accepts_legacy_receipt(m, change):
    value=m['configured'];data=value['result'];s=data['native_source']['selected_state'];p=deepcopy(s)
    p['manifest'].update(path='manifests/optical.json',sha256='f'*64)
    data['optical_attachment']=dict(source_state=deepcopy(s),publication_state=p,
        artifact=dict(path='analysis/optical.h5',bytes='404',sha256='0'*64,media_type='application/x-hdf5',schema='qcl-negf-optical-v5'))
    data['postprocessing']['optical']['status']='completed'
    if change == 'completed_without_attachment': data['optical_attachment']=None
    elif change == 'failed_with_attachment': data['postprocessing']['optical'].update(status='failed',error='original failure')
    elif change == 'wrong_source': data['optical_attachment']['source_state']['state_id']='foreign'
    elif change == 'old_optical': data['optical_attachment']['artifact']['schema']='qcl-negf-optical-v4'
    elif change == 'same_publication': data['optical_attachment']['publication_state']=deepcopy(s)
    else: data['optical_attachment']['commit_sha256']='a'*64
    with pytest.raises(ContractError): check(value)


@pytest.mark.parametrize('kind', ['scientific_plan_v2','nested_sweep'])
def test_full_final_join_reuses_real_scientific_validators_without_recomputing_pass(kind):
    source,context,observations=native(kind)
    checked=bind(source,context,observations)
    assert checked['observations']['path'] == 'analysis/observations.h5'
    assert observations['summary']['scientific_accepted'] is None
    assert observations['summary']['status'] == 'invalid'
    assert context['checkpoint']['state']['fields']['final_evidence']['fields']['report']['fields']['passed'] is False
    checked['selected_state']['identity']['attempt']='7'
    assert source['selected_state']['identity']['attempt'] == '1'


@pytest.mark.parametrize('target', ['manifest_ref','selected_state','diagnostics','observations','status','plan','checkpoint','dependency_order','cycle'])
def test_full_source_join_rejects_coherent_but_unbound_refs_context_and_closure(target):
    source,context,observations=native()
    if target == 'manifest_ref':
        wrong=deepcopy(source['selected_state']['manifest']);wrong['bytes']='999'
        with pytest.raises(ContractError):
            api().validate_outward_native_source(source,manifest_ref=wrong,observations=observations,**context)
        return
    if target == 'selected_state': source['selected_state']['state_sequence']='9'
    elif target == 'diagnostics': source['diagnostics']['sha256']='f'*64
    elif target == 'observations': source['observations']['bytes']='999'
    elif target == 'status': context['manifest']['status']['physics']['evidence']=deepcopy(source['diagnostics'])
    elif target == 'plan': observations['request']['plan']['sha256']='f'*64
    elif target == 'checkpoint': observations['checkpoint']['sha256']='f'*64
    elif target == 'dependency_order': context['manifest']['artifacts'][-1]['dependencies'].reverse()
    else: context['manifest']['artifacts'][0]['dependencies']=[source['observations']['path']]
    with pytest.raises(ContractError): bind(source,context,observations)


def test_completed_child_requires_original_parent_state_and_history_cutoff():
    observations,context=restored()
    for name in ('convergence','physics'):
        context['manifest']['status'][name]=dict(state='recorded',reason=None,evidence=deepcopy(context['artifact_ref']))
    source=dict(schema='qcl-negf.native-point-source.v1',kind='final',artifact_root='.',relation='current_point_attempt',reason=None,
        selected_state={**{k:deepcopy(context['manifest'][k]) for k in ('identity','state_id','state_sequence')},
            'manifest':dict(path='manifests/child.json',bytes='50',sha256='f'*64,media_type='application/json',schema='qcl-negf.result-manifest.v1')},
        diagnostics=deepcopy(observations['diagnostics']),observations=context.pop('artifact_ref'))
    assert bind(source,context,observations)['selected_state']['identity']['attempt'] == '2'
    parent=context.pop('parent_checkpoint')
    with pytest.raises(ContractError):bind(source,context,observations)
    context['parent_checkpoint']=parent;parent['history']['records']='1'
    with pytest.raises(ContractError):bind(source,context,observations)


def test_checkpoint_join_accepts_no_analysis_but_never_manufactures_final_context():
    source,context,observations=native()
    source.update(kind='checkpoint',diagnostics=None,observations=None,reason='final_not_published')
    for key in ('diagnostics','plan','model'): context.pop(key)
    assert bind(source,context)['kind'] == 'checkpoint'
    source.update(kind='final',diagnostics=observations['diagnostics'],observations=dict(path='missing.h5',bytes='0',sha256='a'*64,media_type='application/x-hdf5',schema='qcl-negf-physics-analysis-v5'),reason=None)
    with pytest.raises(ContractError):bind(source,context)


def test_explicit_input_budget_refusal_precedes_decoding_and_old_registry_is_explicit(m):
    raw=encode(m['series'])
    with pytest.raises(ContractError):decode(raw,maximum=len(raw)-1)
    assert check(decode(raw,maximum=len(raw)))['schema']=='qcl-negf-series-result-v4'
    registry=load_schema('results-contract-set.json')
    assert registry['series']=='qcl-negf-series-result-v4'
    assert registry['series_read_versions']==['qcl-negf-series-result-v3','qcl-negf-series-result-v4']
    assert registry['previous_contracts_supported'] is False


@pytest.mark.parametrize('schema', [{}, [], None, 1, True, 'qcl-negf-series-result-v3'])
def test_malformed_or_unrecognised_version_is_a_contract_error(m, schema):
    m['source']['schema']=schema
    with pytest.raises(ContractError):check(m['source'])


def test_malformed_missing_final_document_is_not_a_python_key_error():
    source,context,_=native()
    with pytest.raises(ContractError):bind(source,context,{})


def test_optional_failure_keeps_stationary_source_and_original_error(m):
    value=m['configured']; data=value['result']
    data['postprocessing']['optical'].update(status='failed',error='literal optical persistence failed')
    data['warnings']=[{'code':'OPTIONAL_OPTICS_FAILED','message':'literal optical persistence failed'}]
    got=check(value)
    assert got['result']['native_source']['observations']['path']=='analysis/observations.h5'
    assert got['result']['postprocessing']['optical']['error']=='literal optical persistence failed'
    assert got['status']=='incomplete'


@pytest.mark.parametrize('change', ['status_ordinal','adapter_generation','warning_type'])
def test_configured_counter_and_optional_failure_types_never_slip_through_json_integer(m, change):
    value=m['configured_status']
    if change == 'status_ordinal': value['ordinal']=1.0
    elif change == 'adapter_generation':
        value['latest_checkpoint']=dict(generation=1.0,attempt=1,kind='native_adapter',iteration=None,sha256='a'*64)
    else:
        value=m['configured'];value['result']['postprocessing']['optical'].update(status='failed',error='literal')
        value['result']['warnings']=17
    with pytest.raises(ContractError):check(value)


def test_configured_nested_portable_metadata_is_finite_detached_json(m):
    value=m['configured']; literal={'nested':[None,False,0,'',{'literal':'kept'}]}
    value['coordinates']['extra_axis']=deepcopy(literal)
    value['result']['raw_metadata']=deepcopy(literal)
    got=check(value)
    assert got['coordinates']['extra_axis']=={'nested':[None,False,0,'',{'literal':'kept'}]}
    got['result']['raw_metadata']['nested'][-1]['literal']='changed'
    assert value['result']['raw_metadata']['nested'][-1]['literal']=='kept'


@pytest.mark.parametrize('bad', [float('nan'),float('inf'),b'opaque',{'bad':object()},{1:'nonstring_key'}])
def test_nested_portable_metadata_does_not_admit_nonjson_or_nonfinite(m, bad):
    m['configured']['result']['raw_metadata']={'nested':[bad]}
    with pytest.raises(ContractError):check(m['configured'])
