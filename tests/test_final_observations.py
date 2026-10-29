"""Stored-output wire checks using literal asymmetric shapes; no solve or HDF I/O."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import struct

import pytest
from jsonschema import Draft202012Validator

from qcl_negf_contracts import load_schema, schema_names, schema_validator, results
from qcl_negf_contracts.messages import ContractError, decode, encode
from test_final_diagnostics import inputs as diagnostic_inputs
from test_results_v2 import ieee, integer, ref, sym
from test_resolved_plan_schema import plan as scientific_plan
from test_generated_types import generator

PACKAGE = Path(__file__).parents[1] / 'src/qcl_negf_contracts'
FIXTURE = Path(__file__).parent / 'fixtures/final-observations/core-public-fields.json'
FLAGS = dict(LO=True, acoustic=True, impurity=True, IFR=True, alloy=False)
# Independent literal table: owner,name,eltype,shape,axes,units,coordinates,weights,nullable.
ARRAYS = [
    ('context','x_scaled','Float64',['5'],['z'],'1',['z_nm'],['wX'],False),
    ('context','wX','Float64',['5'],['z'],'1',['z_nm'],['wX'],False),
    ('context','energy_scaled','Float64',['3'],['E'],'1',['energy_eV'],['wE'],False),
    ('context','wE','Float64',['3'],['E'],'1',['energy_eV'],['wE'],False),
    ('context','momentum_scaled','Float64',['2'],['k'],'1',['k_per_nm'],['wk'],False),
    ('context','wk','Float64',['2'],['k'],'1',['k_per_nm'],['wk'],False),
    ('context','z_nm','Float64',['5'],['z'],'nm',['z_nm'],['wX'],False),
    ('context','energy_eV','Float64',['3'],['E'],'eV',['energy_eV'],['wE'],False),
    ('context','k_per_nm','Float64',['2'],['k'],'nm^-1',['k_per_nm'],['wk'],False),
    ('context','state_index','Int64',['2'],['state'],'1',['state_index'],[None],False),
    ('context','trusted_energy','Bool',['3'],['E'],'1',['energy_eV'],['wE'],False),
    ('views','potential_structure_eV','Float64',['5'],['z'],'eV',['z_nm'],['wX'],False),
    ('views','potential_external_eV','Float64',['5'],['z'],'eV',['z_nm'],['wX'],False),
    ('views','potential_hartree_eV','Float64',['5'],['z'],'eV',['z_nm'],['wX'],False),
    ('views','potential_total_eV','Float64',['5'],['z'],'eV',['z_nm'],['wX'],False),
    ('views','density_per_m3','Float64',['5'],['z'],'m^-3',['z_nm'],['wX'],False),
    ('views','spatial_energy_density_per_eV_m3','Float64',['3','5'],['E','z'],'eV^-1 m^-3',['energy_eV','z_nm'],['wE','wX'],True),
    ('views','spectral_trace_per_eV','Float64',['3','2'],['E','k'],'eV^-1',['energy_eV','k_per_nm'],['wE','wk'],False),
    ('views','occupied_trace_per_eV','Float64',['3','2'],['E','k'],'eV^-1',['energy_eV','k_per_nm'],['wE','wk'],False),
    ('views','localized_levels_eV','Float64',['2'],['state'],'eV',['state_index'],[None],True),
    ('views','effective_levels_eV','Float64',['2'],['state'],'eV',['state_index'],[None],True),
    ('views','localized_wavefunctions_per_sqrt_nm','ComplexF64',['5','2'],['z','state'],'nm^-1/2',['z_nm','state_index'],['wX',None],False),
    ('views','effective_wavefunctions_per_sqrt_nm','ComplexF64',['5','2'],['z','state'],'nm^-1/2',['z_nm','state_index'],['wX',None],True),
    ('views','effective_transform','ComplexF64',['2','2'],['state','state_prime'],'1',['state_index','state_index'],[None,None],True),
    ('views','sheet_density_matrix_per_m2','ComplexF64',['2','2'],['state','state_prime'],'m^-2',['state_index','state_index'],[None,None],False),
    ('views','effective_density_matrix_per_m2','ComplexF64',['2','2'],['state','state_prime'],'m^-2',['state_index','state_index'],[None,None],True),
]


def scalar(number):
    return ieee(struct.pack('>d', number).hex())


def core_value(name):
    """Manufactured structural option values, never a physical validation oracle."""
    node = json.loads((PACKAGE/'core_layout.json').read_text())['graph']['nodes'][name]
    kind = node['kind']
    if kind == 'bool': return False
    if kind == 'symbol': return sym('')
    if kind == 'ieee': return ieee()
    if kind == 'integer': return integer(0, node['type'])
    if kind == 'struct': return dict(type=name, fields={f['name']:core_value(f['type']) for f in node['fields']})
    if kind == 'union': return core_value(node['variants'][0])
    if kind == 'nothing': return None
    raise AssertionError((name, kind))


def nested_plan():
    return dict(name='configured_operating_points', root=dict(kind='level', name='temperature',
        axes=[dict(name='temperature_K', values=[70.0, 90.0])], child=dict(kind='level', name='voltage',
        axes=[dict(name='voltage_per_period_V', values=[0.05, 0.1])], child=dict(kind='leaf', name='poisson_scba'))))


def inputs(kind='scientific_plan_v2'):
    diag, ctx = diagnostic_inputs(); cp=ctx['checkpoint']; state=cp['state']['fields']; scba=state['scba']['fields']
    for n,a in scba['green']['fields'].items():
        if a.get('kind')=='array': a['shape']=['3','2','2','2'] if n in ('Gᴿ','Gˡ','Gᵍ','A') else ['3','2']
    for n in ('published_U','published_n'): state[n]['shape']=['5']
    family=deepcopy(scba['embedding'])
    for a in family['fields'].values(): a['shape']=['3','2','2','2']
    for n in ('embedding','embedding_plus','embedding_minus'): scba[n]=deepcopy(family)
    scba['scattering']={'kind':'dict','entries':[dict(key=sym('electron_electron'),value=deepcopy(family))]}
    state['family_order']=[sym('electron_electron'),sym('embedding_plus'),sym('embedding_minus')]
    diag['dimensions']['basis']='2'
    diag['positivity']['data']['integrals']['spectral_integral']['shape']=['2','2','2']
    diag['positivity']['data']['integrals']['spectral_integral_eigenvalues']['shape']=['2','2']
    diagref=ctx['artifact_ref']
    obsref=dict(ref('analysis/observations.h5','qcl-negf-physics-analysis-v5','d'*64),media_type='application/x-hdf5')
    planref=ref('plans/frozen.json' if kind=='scientific_plan_v2' else 'plans/frozen.yaml',
        'qcl-negf-scientific-plan-v2' if kind=='scientific_plan_v2' else 'qcl-negf.nested-sweep-plan.v1','b'*64)
    if kind=='nested_sweep': planref['media_type']='text/plain'
    modelref=ref('models/actual-point.json','qcl-negf-resolved-configuration-v3','e'*64)
    cpref=ctx['manifest']['checkpoint']
    for r,role in [(planref,'plan'),(modelref,'model')]:ctx['manifest']['artifacts'].append(dict(r,role=role,profile='science',dependencies=[]))
    ctx['manifest']['artifacts'].append(dict(obsref,role='physics.analysis',profile='science',dependencies=[r['path'] for r in (cpref,diagref,planref,modelref)]))
    context=dict(dimensions=dict(Nz='5',NE='3',Nk='2',Nb='2'), domain_revision=integer(0),discretization_id='a'*64,basis_id='b'*64,
        scales={n:scalar(v) for n,v in [('E0_eV',0.1),('L0_m',1e-9),('J0_A_per_m2',2.0)]},
        inputs={n:scalar(v) for n,v in [('F_bias_V_per_m',5e6),('V_period_V',0.05),('T_L_K',70.0),('T_LO_K',70.0),('E_ref_eV',0.0),('N_dop_2D_per_m2',2e14),('f_ion',1.0),('z0_m',0.0),('period_length_m',1e-8)]},
        problem_scattering=dict(type='ScatteringOptions',fields=deepcopy(FLAGS)),enabled_scattering=[],selfenergy_families=['electron_electron'],
        physical_models=core_value('PhysicalModelOptions'),algorithms=deepcopy(state['measurement_context']['fields']['algorithms']),
        energy_shift_discretization='nodal_linear',localization='pzp',boundary_condition='stationary_field_periodic_embedding',
        basis_contract='orthonormal_finite_projected',energy_reference='scaled_E0_plus_E_ref',effective_gauge='k0_ascending_spatial_first_max_real_positive')
    context['inputs']['g_s']=integer(2)
    views=dict(current_density_A_per_m2=ieee('8000000000000000'),sheet_density_per_m2=scalar(2e14))
    for owner,n,eltype,shape,axes,units,coords,weights,_ in ARRAYS:
        target=context if owner=='context' else views
        target[n]=dict(dataset='/final_observations/arrays/'+n,eltype=eltype,shape=shape.copy(),order='F',axes=axes.copy(),units=units,coordinate_fields=coords.copy(),weight_fields=weights.copy())
    def components(f):return {a:deepcopy(f['fields'][b]) for a,b in [('retarded','Σᴿ'),('lesser','Σˡ'),('greater','Σᵍ')]}
    model=dict(schema='qcl-negf-resolved-configuration-v3',contract_set='qcl-negf.results.v2',configuration_hash='a'*64,
        hash_encoding='qcl-negf-canonical-bytes-v1',configuration=dict(scope='stationary_transport_inputs_v1',inputs={
        n:{} for n in ['physical','numerical','scales','solver','kernel_construction','algorithms','physical_models','domain_adaptation']},derived=dict(effective_seed_eV=0.01)))
    model['configuration']['inputs'].update(scattering=deepcopy(FLAGS),production=dict(physics_markers={},verify_fft_roundoff=False))
    plan=scientific_plan() if kind=='scientific_plan_v2' else nested_plan()
    if kind=='scientific_plan_v2':
        plan['executions'][0].update(id='exec',point_ids=['point'])
        plan['points'][0].update(execution_id='exec',effective_inputs=dict(plan['points'][0]['effective_inputs'],model_sha256='a'*64))
    value=dict(schema='qcl-negf.final-observations.v1',contract_set='qcl-negf.results.v2',identity=deepcopy(cp['identity']),invocation=deepcopy(cp['invocation']),
        state_id=cp['state_id'],state_sequence=cp['state_sequence'],checkpoint=deepcopy(cpref),diagnostics=deepcopy(diagref),source_mode='produced',
        binding=dict(identity=deepcopy(state['identity']),terminal_integrity=deepcopy(state['integrity'])),context=context,
        request=dict(kind=kind,plan=planref,model=modelref,temperature_K=scalar(70.0),voltage_per_period_V=scalar(0.05),scattering_requested=deepcopy(FLAGS),
            coordinate_checks={n:dict(status='verified',reason=None,requested=scalar(v),actual=scalar(v)) for n,v in [('temperature',70.0),('voltage',0.05)]}),
        state_bindings=dict(green={a:deepcopy(scba['green']['fields'][b]) for a,b in [('retarded','Gᴿ'),('lesser','Gˡ'),('greater','Gᵍ'),('spectral','A')]},
            scattering=[dict(family='electron_electron',**components(family))],embedding={n:components(scba[f]) for n,f in [('total','embedding'),('plus','embedding_plus'),('minus','embedding_minus')]}),
        views=views,summary=dict(status='invalid',quality='invalid',converged=False,registry_version='literal-registry',iterative_converged=False,
            fixed_hartree_converged=False,physical_gates_passed=False,stationary_candidate_accepted=False,scientific_accepted=None,
            discretization_verified='not_measured',scientific_acceptance_reason='No independent discretization evidence',outer_confirmation_count=integer(0)),restoration=None,issues=[])
    return value,dict(checkpoint=cp,manifest=ctx['manifest'],artifact_ref=obsref,diagnostics=diag,plan=plan,model=model)


def validate(value,ctx):
    function=getattr(results,'validate_final_observations',None)
    assert callable(function),'final observation pure API missing'
    return function(value,**ctx)


def validate_nested(value):
    function=getattr(results,'validate_nested_sweep_plan',None)
    assert callable(function),'existing nested tree pure API missing'
    return function(value)


def missing(value,names,reason='eigensystem_failed',status='error'):
    for n in names:
        value['views'][n]=None;value['issues'].append(dict(target=n,status=status,reason=reason,detail='literal unavailable'))


def restored():
    value,ctx=inputs();parent=deepcopy(ctx['checkpoint']);pm=deepcopy(ctx['manifest'])
    parentref=ref('parents/manifest.json');cpref=ref('parents/checkpoint.json','qcl-negf.checkpoint-declaration.v1','9'*64)
    old_path=pm['checkpoint']['path'];pm['checkpoint']=deepcopy(cpref)
    for row in pm['artifacts']:
        if row['path']==old_path:row.update(cpref)
        row['dependencies']=[cpref['path'] if p==old_path else p for p in row['dependencies']]
    pm['lineage']={'parent_state':None};parent['lineage']={'parent_state':None}
    lineage=dict(identity=deepcopy(parent['identity']),state_id=parent['state_id'],state_sequence=parent['state_sequence'],manifest=parentref)
    for obj in (ctx['checkpoint'],ctx['manifest']):
        obj['identity'].update(attempt='2',branch_id='child-branch');obj['invocation']['source_epoch']='epoch-child';obj['state_id']='child-state';obj['state_sequence']='7';obj['lineage']={'parent_state':deepcopy(lineage)}
    for obj in (value,ctx['diagnostics']):
        for n in ('identity','invocation','state_id','state_sequence'):obj[n]=deepcopy(ctx['checkpoint'][n])
    value['source_mode']='completed_restore';value['summary']['status']='validation_failed'
    context=deepcopy(ctx['checkpoint']['state']['fields']['measurement_context'])
    context['fields'].update(backend=sym('production'),map_kernels_shared_with_solver=True,final_state_alignment=sym('restored_aligned'))
    report=deepcopy(parent['state']['fields']['final_evidence']['fields']['report'])
    value['restoration']=dict(parent_state=lineage,parent_checkpoint=cpref,history=deepcopy(parent['history']),
        original=dict(checkpoint=deepcopy(value['checkpoint']),field='final_evidence',integrity=deepcopy(value['binding']['terminal_integrity'])),
        revalidation=dict(type='RevalidationReceipt',fields=dict(status=sym('measured'),reason=None,detail='',context=context,report=report)),
        independent_oracle=dict(type='IndependentOracleReceipt',fields=dict(status=sym('unsupported'),reason=sym('independent_map_not_qualified'),detail='literal no oracle',context=None,report=None)))
    ctx.update(parent_manifest=pm,parent_checkpoint=parent)
    return value,ctx


@pytest.mark.parametrize('kind',['scientific_plan_v2','nested_sweep'])
def test_complete_asymmetric_views_bind_exact_sources_without_scientific_pass(kind):
    value,ctx=inputs(kind);before=deepcopy((value,ctx));checked=validate(decode(encode(value)),ctx)
    assert checked==value and checked is not value and (value,ctx)==before
    checked['context']['inputs']['g_s']['decimal']='4'
    assert value['context']['inputs']['g_s']['decimal']=='2'
    assert ctx['manifest']['status']['physics']['state']=='not_measured'


def test_nested_validation_returns_detached_existing_tree_without_new_envelope():
    tree=nested_plan();checked=validate_nested(tree);assert checked==tree and checked is not tree
    checked['root']['axes'][0]['values'][0]=0;assert tree['root']['axes'][0]['values'][0]==70.0


@pytest.mark.parametrize('row',ARRAYS,ids=[r[1] for r in ARRAYS])
@pytest.mark.parametrize('field,bad',[('dataset','/final_observations/arrays/alias'),('eltype','UInt8'),('shape',['999']),('axes',['wrong']),('units','wrong'),('order','C'),('coordinate_fields',[None]),('weight_fields',['wrong']),('file',{})])
def test_each_local_descriptor_rejects_loss_or_unbound_representation(row,field,bad):
    value,ctx=inputs();assert validate(value,ctx)==value
    value[row[0]][row[1]][field]=bad
    with pytest.raises(ContractError):validate(value,ctx)


@pytest.mark.parametrize('bits',['0000000000000000','8000000000000000','7ff0000000000000','fff0000000000000','7ff8000000000001','7ff8000000000002','7ff0000000000001'])
def test_raw_ieee_samples_remain_exact_present_observations(bits):
    value,ctx=inputs();value['views']['current_density_A_per_m2']=ieee(bits);value['context']['inputs']['f_ion']=ieee(bits)
    checked=validate(decode(encode(value)),ctx)
    assert checked['views']['current_density_A_per_m2']['bits']==bits
    assert checked['context']['inputs']['f_ion']['bits']==bits


@pytest.mark.parametrize('target',['checkpoint','diagnostics','request.plan','request.model','artifact_ref'])
@pytest.mark.parametrize('field,bad',[('sha256','f'*64),('bytes','41'),('schema','foreign'),('media_type','text/markdown'),('path','other/path')])
def test_all_five_fileref_members_bind_selected_inventory(target,field,bad):
    value,ctx=inputs();assert validate(value,ctx)==value
    obj=ctx if target=='artifact_ref' else value
    for part in target.split('.'):obj=obj[part]
    obj[field]=bad
    with pytest.raises(ContractError):validate(value,ctx)


@pytest.mark.parametrize('field',['identity','invocation','state_id','state_sequence','binding','context','request','state_bindings','views','summary','restoration','issues'])
def test_required_closed_members_cannot_disappear_or_gain_fields(field):
    value,ctx=inputs();del value[field]
    with pytest.raises(ContractError):validate(value,ctx)
    value,ctx=inputs();value['invented']=None
    with pytest.raises(ContractError):validate(value,ctx)


def test_nullable_view_groups_require_exact_issues_and_preserve_missing_vs_zero():
    value,ctx=inputs();names=[r[1] for r in ARRAYS if r[0]=='views' and r[-1]]
    missing(value,names);assert validate(value,ctx)==value
    value['issues'].pop()
    with pytest.raises(ContractError):validate(value,ctx)
    value,ctx=inputs();missing(value,['localized_levels_eV']);assert validate(value,ctx)==value
    value,ctx=inputs();missing(value,['effective_levels_eV'])
    with pytest.raises(ContractError):validate(value,ctx)


@pytest.mark.parametrize('violation',['duplicate','extra','present','unknown_reason','unknown_status'])
def test_issues_do_not_hide_present_data_or_unknown_measurements(violation):
    value,ctx=inputs();missing(value,['spatial_energy_density_per_eV_m3'],'nonfinite_green')
    if violation=='duplicate':value['issues']*=2
    elif violation=='extra':value['issues'][0]['invented']=False
    elif violation=='present':value['issues'][0]['target']='density_per_m3'
    elif violation=='unknown_reason':value['issues'][0]['reason']='invented'
    else:value['issues'][0]['status']='pass'
    with pytest.raises(ContractError):validate(value,ctx)


def test_positivity_failure_machine_fields_and_exact_existing_diagnostic_reason():
    value,ctx=inputs();value['issues']=[dict(target='positivity',status='error',reason='positivity_measurement_failed',detail='literal failure')]
    ctx['diagnostics']['positivity']=dict(status='error',reason='positivity_measurement_failed: literal failure',data=None)
    assert validate(value,ctx)==value
    ctx['diagnostics']['positivity']['reason']='different detail'
    with pytest.raises(ContractError):validate(value,ctx)


@pytest.mark.parametrize('violation',['green','family','embedding','revision','dimension','g_s','IEEE','false_request','true_request','coordinate','model_hash','model_scope','plan_point','plan_model','plan_axes','status','extra_display'])
def test_cross_field_source_bindings_reject_substitution(violation):
    value,ctx=inputs()
    if violation=='green':value['state_bindings']['green']['lesser']['dataset']='/arrays/other'
    elif violation=='family':value['state_bindings']['scattering'][0]['family']='LO'
    elif violation=='embedding':value['state_bindings']['embedding']['minus']['retarded']['file']['bytes']='41'
    elif violation=='revision':value['context']['domain_revision']=integer(1)
    elif violation=='dimension':value['context']['dimensions']['Nz']='4'
    elif violation=='g_s':value['context']['inputs']['g_s']=scalar(2.0)
    elif violation=='IEEE':value['views']['current_density_A_per_m2']=0.0
    elif violation=='false_request':value['request']['scattering_requested']['LO']=False
    elif violation=='true_request':value['context']['problem_scattering']['fields']['alloy']=True
    elif violation=='coordinate':value['request']['coordinate_checks']['temperature']['actual']=scalar(90.0)
    elif violation=='model_hash':ctx['model']['configuration_hash']='c'*64
    elif violation=='model_scope':ctx['model']['configuration']['scope']='snapshot-v1'
    elif violation=='plan_point':ctx['plan']['points'][0]['id']='foreign'
    elif violation=='plan_model':ctx['plan']['points'][0]['effective_inputs']['model_sha256']='c'*64
    elif violation=='plan_axes':ctx['plan']['points'][0]['effective_inputs']['axes_applied']=False
    elif violation=='status':value['summary']['status']='foreign'
    else:value['assessment']={}
    with pytest.raises(ContractError):validate(value,ctx)


def test_unknown_core_status_text_is_exact_bounded_without_truncation():
    value,ctx=inputs();status='Ж'*256;value['summary']['status']=status
    ev=ctx['checkpoint']['state']['fields']['final_evidence']['fields'];ev['original_status']=sym(status)
    assert validate(value,ctx)['summary']['status']==status
    ev['original_status']=sym(status+'Ж');value['summary']['status']=status+'Ж'
    with pytest.raises(ContractError):validate(value,ctx)


def test_voltage_roundtrip_retains_both_unequal_bit_patterns_without_tolerance():
    value,ctx=inputs();value['context']['inputs']['V_period_V']=scalar(0.05000000000000001)
    value['request']['coordinate_checks']['voltage'].update(status='not_verified',reason='field_period_roundtrip',actual=scalar(0.05000000000000001))
    assert validate(value,ctx)==value
    value['request']['coordinate_checks']['voltage']['reason']=None
    with pytest.raises(ContractError):validate(value,ctx)


@pytest.mark.parametrize('bad',['00','0','9223372036854775808',True])
def test_dimensions_are_positive_actual_int64_domain_counts(bad):
    value,ctx=inputs();value['context']['dimensions']['NE']=bad
    with pytest.raises(ContractError):validate(value,ctx)


@pytest.mark.parametrize('violation',['envelope','kind','empty_axis','empty_values','duplicate_axis','duplicate_path','nonfinite','object','depth','name'])
def test_existing_nested_tree_refuses_unsafe_or_ambiguous_decoded_structure(violation):
    tree=nested_plan()
    if violation=='envelope':tree['schema']='new-envelope'
    elif violation=='kind':tree['root']['kind']='foreign'
    elif violation=='empty_axis':tree['root']['axes']=[]
    elif violation=='empty_values':tree['root']['axes'][0]['values']=[]
    elif violation=='duplicate_axis':tree['root']['axes']*=2
    elif violation=='duplicate_path':tree['root']['child']=dict(kind='level',name='temperature',axes=deepcopy(tree['root']['axes']),child=dict(kind='leaf',name='solve'))
    elif violation=='nonfinite':tree['root']['axes'][0]['values']=[float('nan')]
    elif violation=='object':tree['root']['axes'][0]['values']=[object()]
    elif violation=='name':tree['name']='x\n'
    else:
        for _ in range(65):tree['root']=dict(kind='level',name='level',axes=[dict(name='axis',values=[1])],child=tree['root'])
    with pytest.raises(ContractError):validate_nested(tree)


def test_nested_schema_accepts_portable_axis_metadata_without_relabelling_yaml():
    tree=nested_plan();tree['root']['axes'][0]['values']=[None,True,1,1.0,-0.0,'',[],{'nested':[False,{'unit':'eV','value':0.25}]}]
    assert validate_nested(tree)==tree


def test_completed_parent_allows_new_attempt_branch_epoch_and_retains_original():
    value,ctx=restored();before=deepcopy(ctx)
    assert value['identity']['attempt']=='2' and value['restoration']['parent_state']['identity']['attempt']=='1'
    assert value['identity']['branch_id']!=value['restoration']['parent_state']['identity']['branch_id']
    assert validate(value,ctx)==value and ctx==before
    report=value['restoration']['revalidation']['fields'];report.update(status=sym('error'),reason=sym('selected_map_measurement_failed'))
    assert validate(value,ctx)==value
    report['report']['fields']['passed']=True
    with pytest.raises(ContractError):validate(value,ctx)


@pytest.mark.parametrize('violation',['no_parent','parent_scope','parent_state','parent_history','original','parent_integrity','oracle','mode'])
def test_restoration_requires_immediate_verified_parent_and_distinct_receipts(violation):
    value,ctx=restored();assert validate(value,ctx)==value
    if violation=='no_parent':ctx.pop('parent_manifest')
    elif violation=='parent_scope':ctx['parent_checkpoint']['identity']['model_sha256']='f'*64
    elif violation=='parent_state':value['restoration']['parent_state']['state_id']='foreign'
    elif violation=='parent_history':value['restoration']['history']['records']='1'
    elif violation=='original':ctx['parent_checkpoint']['state']['fields']['final_evidence']['fields']['original_status']=sym('foreign')
    elif violation=='parent_integrity':ctx['parent_checkpoint']['state']['fields']['integrity'][0]=integer(3,'UInt8')
    elif violation=='oracle':value['restoration']['independent_oracle']['fields']['status']=sym('measured')
    else:value['source_mode']='produced'
    with pytest.raises(ContractError):validate(value,ctx)


@pytest.mark.parametrize('cycle',[False,True])
def test_selected_closure_accepts_shared_forward_dag_but_rejects_long_backedge(cycle):
    value,ctx=inputs();source=ctx['manifest'];payload=source['artifacts'][0]
    nodes=[dict(payload,path=f'extra/node{i}.h5',dependencies=[]) for i in range(1500)]
    for node,nxt in zip(nodes,nodes[1:]):node['dependencies']=[nxt['path']]
    payload['dependencies']=[nodes[0]['path']];source['artifacts'].extend(reversed(nodes))
    if cycle:nodes[-1]['dependencies']=[nodes[700]['path']]
    if cycle:
        with pytest.raises(ContractError,match='cycl'):validate(value,ctx)
    else:assert validate(value,ctx)==value


def test_direct_dependencies_are_exact_and_plan_model_are_leaves():
    value,ctx=inputs();selected=ctx['manifest']['artifacts'][-1]
    selected['dependencies'].pop()
    with pytest.raises(ContractError):validate(value,ctx)
    value,ctx=inputs();ctx['manifest']['artifacts'][-2]['dependencies']=[value['checkpoint']['path']]
    with pytest.raises(ContractError):validate(value,ctx)


def test_schema_resources_field_receipt_and_generated_aliases_are_additive():
    assert {'final-observations.schema.json','nested-sweep-plan.schema.json'}<=set(schema_names())
    receipt=json.loads(FIXTURE.read_text());assert receipt['core_revision']=='f1fef6755a0744d88511a3843df2e94900a8b9fc'
    assert sum(t['field_count'] for t in receipt['public_types'].values())==95
    schema=load_schema('final-observations.schema.json')
    for typ in ('FinalObservationContext','FinalObservationInputs','FinalObservationScales','StoredFinalObservations','FinalScientificSummary','FinalObservationIssue'):
        definition=schema['$defs'][typ];expected=[x['name'] for x in receipt['public_types'][typ]['fields']]
        assert list(definition['properties'])==expected and definition['required']==expected and definition['additionalProperties'] is False
    for file in ('final-observations.schema.json','nested-sweep-plan.schema.json'):
        Draft202012Validator.check_schema(load_schema(file))
        schema_validator(file).validate(inputs()[0] if file.startswith('final-') else nested_plan())
    module=generator();documents={n:load_schema(n) for n in (*module.DOCUMENTS,'model-help.schema.json')}
    ts=module.ts_export(documents)
    assert 'export type FinalObservations =' in ts and 'export type NestedSweepPlan =' in ts
    aliases={s.split()[2]:hashlib.sha256(s.encode()).hexdigest() for s in ts.splitlines() if s.startswith('export type ')}
    assert len(receipt['existing_alias_sha256'])==188
    assert {n:aliases[n] for n in receipt['existing_alias_sha256']}==receipt['existing_alias_sha256']


@pytest.mark.parametrize('path',[('views','current_density_A_per_m2'),('context','inputs','f_ion')])
def test_raw_nonfinite_json_is_not_an_alternative_to_bit_tags(path):
    value,ctx=inputs();obj=value
    for n in path[:-1]:obj=obj[n]
    obj[path[-1]]=float('nan')
    with pytest.raises(ContractError):validate(value,ctx)


def test_model_portable_metadata_is_not_reinterpreted_as_core_tags():
    value,ctx=inputs();ctx['model']['configuration']['inputs']['physical']={'kind':'integer','type':'metadata'}
    assert validate(value,ctx)==value


def test_scientific_plan_invalid_utf8_reports_contract_error():
    value,ctx=inputs();ctx['plan']['name']='\ud800'
    with pytest.raises(ContractError):validate(value,ctx)


@pytest.mark.parametrize('violation',['payload_ref','payload_frontier','process'])
def test_parent_checkpoint_joins_its_actual_inventory_and_terminal_process(violation):
    value,ctx=restored();assert validate(value,ctx)==value
    source=ctx['parent_manifest']
    if violation=='payload_ref':source['artifacts'][0]['sha256']='f'*64
    elif violation=='payload_frontier':
        row=next(r for r in source['artifacts'] if r['path']==source['checkpoint']['path']);row['dependencies']=[]
    else:source['status']['process']['state']='running'
    with pytest.raises(ContractError):validate(value,ctx)


@pytest.mark.parametrize('status,converged',[('converged',True),('approximate',False)])
def test_completed_current_report_can_differ_from_failed_original(status,converged):
    value,ctx=restored();value['summary'].update(status=status,converged=converged)
    value['restoration']['revalidation']['fields']['report']['fields']['passed']=True
    assert validate(value,ctx)==value
    assert ctx['checkpoint']['state']['fields']['final_evidence']['fields']['report']['fields']['passed'] is False
    assert value['restoration']['parent_checkpoint']['path']!=value['checkpoint']['path']


def test_nested_limiting_temperature_does_not_become_a_new_equilibrium_gate():
    value,ctx=inputs('nested_sweep');ctx['plan']['root']['axes'][0]['values']=[0.0]
    value['request']['temperature_K']=scalar(0.0);value['context']['inputs']['T_L_K']=scalar(0.0)
    value['request']['coordinate_checks']['temperature'].update(requested=scalar(0.0),actual=scalar(0.0))
    assert validate(value,ctx)==value


@pytest.mark.parametrize('count',[-1,-9223372036854775808])
def test_negative_g_s_is_rejected_by_the_accepted_count_bound(count):
    value,ctx=inputs();value['context']['inputs']['g_s']=integer(count)
    with pytest.raises(ContractError,match=r'\$\.context\.inputs\.g_s'):
        validate(value,ctx)


@pytest.mark.parametrize('count',[0,1,2,9223372036854775807])
def test_nonnegative_g_s_preserves_zero_and_the_full_nonnegative_int64_range(count):
    value,ctx=inputs();value['context']['inputs']['g_s']=integer(count)
    assert validate(value,ctx)['context']['inputs']['g_s']==integer(count)


def multi_family_inputs(dictionary_order=('IFR','LO','electron_electron'),
                        core_order=('LO','IFR','electron_electron')):
    """Literal distinct source arrays; Dict order is independent of Core family_order."""
    value,ctx=inputs();state=ctx['checkpoint']['state']['fields'];scba=state['scba']['fields']
    template=scba['embedding'];families={};bindings={}
    for family in core_order:
        source=deepcopy(template);binding={'family':family}
        for name,field in (('retarded','Σᴿ'),('lesser','Σˡ'),('greater','Σᵍ')):
            source['fields'][field]['dataset']='/arrays/'+family+'_'+name
            binding[name]=deepcopy(source['fields'][field])
        families[family]=source;bindings[family]=binding
    scba['scattering']['entries']=[dict(key=sym(name),value=families[name]) for name in dictionary_order]
    state['family_order']=[sym(name) for name in (*core_order,'embedding_plus','embedding_minus')]
    value['context']['selfenergy_families']=list(core_order)
    value['context']['enabled_scattering']=[name for name in core_order if name!='electron_electron']
    value['state_bindings']['scattering']=[bindings[name] for name in core_order]
    return value,ctx


@pytest.mark.parametrize('dictionary_order',[
    ('LO','IFR','electron_electron'),('LO','electron_electron','IFR'),
    ('IFR','LO','electron_electron'),('IFR','electron_electron','LO'),
    ('electron_electron','LO','IFR'),('electron_electron','IFR','LO'),
])
def test_scattering_dictionary_permutations_preserve_actual_core_family_order(dictionary_order):
    value,ctx=multi_family_inputs(dictionary_order)
    original=deepcopy(value)
    assert validate(value,ctx)==original
    assert value['context']['selfenergy_families']==['LO','IFR','electron_electron']
    assert value['context']['enabled_scattering']==['LO','IFR']


def test_scattering_order_authority_is_the_explicit_checkpoint_not_a_hardcoded_sort():
    value,ctx=multi_family_inputs(core_order=('IFR','LO','electron_electron'))
    assert validate(value,ctx)==value
    assert value['state_bindings']['scattering'][0]['family']=='IFR'


def test_all_five_families_and_electron_electron_keep_core_order_with_canonical_dict():
    value,ctx=multi_family_inputs(
        dictionary_order=('IFR','LO','acoustic','alloy','electron_electron','impurity'),
        core_order=('LO','acoustic','impurity','IFR','alloy','electron_electron'))
    for flags in (value['request']['scattering_requested'],value['context']['problem_scattering']['fields'],
                  ctx['model']['configuration']['inputs']['scattering']):flags['alloy']=True
    assert validate(value,ctx)==value
    assert value['context']['enabled_scattering']==['LO','acoustic','impurity','IFR','alloy']


def test_empty_actual_scattering_keeps_requested_flags_without_fabricated_zero_families():
    value,ctx=multi_family_inputs(dictionary_order=(),core_order=())
    assert validate(value,ctx)==value
    assert value['request']['scattering_requested']['LO'] is True
    assert value['state_bindings']['scattering']==[]


@pytest.mark.parametrize('component',['retarded','lesser','greater'])
def test_scattering_join_binds_each_component_to_its_named_source_family(component):
    value,ctx=multi_family_inputs()
    value['state_bindings']['scattering'][0][component]=deepcopy(
        value['state_bindings']['scattering'][1][component])
    with pytest.raises(ContractError,match='scattering'):validate(value,ctx)


@pytest.mark.parametrize('violation',[
    'duplicate_dict','missing_dict','extra_dict','duplicate_order','missing_order','extra_order',
    'wrong_suffix','short_suffix','missing_suffix','family_after_suffix','embedding_in_prefix',
    'context_order','binding_order','enabled_order','enabled_electron_electron','source_file_ref',
])
def test_scattering_join_rejects_ambiguous_sources_and_order_binding_conflicts(violation):
    value,ctx=multi_family_inputs();state=ctx['checkpoint']['state']['fields']
    entries=state['scba']['fields']['scattering']['entries'];order=state['family_order']
    if violation=='duplicate_dict':entries.append(deepcopy(entries[0]))
    elif violation=='missing_dict':entries.pop()
    elif violation=='extra_dict':entries.append(dict(key=sym('acoustic'),value=deepcopy(entries[0]['value'])))
    elif violation=='duplicate_order':order.insert(1,sym('LO'))
    elif violation=='missing_order':order.pop(0)
    elif violation=='extra_order':order.insert(0,sym('acoustic'))
    elif violation=='wrong_suffix':order[-2:]=[sym('embedding_minus'),sym('embedding_plus')]
    elif violation=='short_suffix':order[:]=[sym('embedding_minus')]
    elif violation=='missing_suffix':order[:]=order[:-2]
    elif violation=='family_after_suffix':order.append(sym('LO'))
    elif violation=='embedding_in_prefix':order.insert(0,sym('embedding_plus'))
    elif violation=='context_order':value['context']['selfenergy_families']=['IFR','LO','electron_electron']
    elif violation=='binding_order':value['state_bindings']['scattering'][:2]=value['state_bindings']['scattering'][1::-1]
    elif violation=='enabled_order':value['context']['enabled_scattering']=['IFR','LO']
    elif violation=='enabled_electron_electron':value['context']['enabled_scattering'].append('electron_electron')
    else:value['state_bindings']['scattering'][0]['retarded']['file']['sha256']='f'*64
    with pytest.raises(ContractError):validate(value,ctx)
