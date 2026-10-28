"""New result boundaries; literals are manufactured, never saved solver data."""
from copy import deepcopy
import importlib
import importlib.util
import json
from pathlib import Path

import pytest

from qcl_negf_contracts import schema_validator
from qcl_negf_contracts.messages import ContractError, decode, encode


def test_new_result_api_exists():
    assert importlib.util.find_spec('qcl_negf_contracts.results') is not None, 'new result API missing'


@pytest.fixture
def api():
    assert importlib.util.find_spec('qcl_negf_contracts.results') is not None, 'new result API missing'
    return importlib.import_module('qcl_negf_contracts.results')


def identity(attempt='1'):
    return dict(run_id='run', execution_id='exec', point_id='point', attempt=attempt,
                branch_id='branch', model_sha256='a'*64, plan_sha256='b'*64)


def ref(path='manifest.json', schema='qcl-negf.result-manifest.v1', digest='c'*64):
    return dict(path=path, bytes='40', sha256=digest, media_type='application/json', schema=schema)


def pin():
    return dict(head=None, entries='0', records='0', scba_rows='0', outer_rows='0',
                witness_updates='0', last_record='0')


def unavailable():
    return dict(state='not_measured', reason='not_requested', evidence=None)


def manifest():
    return dict(schema='qcl-negf.result-manifest.v1', contract_set='qcl-negf.results.v2',
                identity=identity(), lineage={'parent_state': None}, invocation={'source_epoch': 'epoch1'},
                provenance=dict(format='qcl-negf.git-graph.v1', revision='a'*40,
                                components=[dict(path='components/QCLNEGF.jl', revision='b'*40,
                                                 url='https://github.com/Afonenko-QCL-NEGF/QCLNEGF.jl')]),
                numerical_binding=None, state_id='state', state_sequence='1', generation='1', closed=False,
                status=dict(process=dict(state='succeeded', exit_code=0, reason=None),
                            convergence=unavailable(), physics=unavailable(),
                            discretization=unavailable(), experimental=unavailable()),
                artifacts=[], history=pin(), checkpoint=None)


def sym(value):
    return {'kind': 'symbol', 'value': value}


def integer(value, kind='Int64'):
    return {'kind': 'integer', 'type': kind, 'decimal': str(value)}


def ieee(bits='0000000000000000'):
    return {'kind': 'ieee', 'type': 'f64', 'bits': bits}


def scba_row():
    # Literal public SCBAIteration: scalar evidence only, no solver construction.
    floats = ('r_D r_A r_K r_Σ r_λ λ r_PSD r_caus r_roundoff r_Jchange r_population '
              'J raw_charge target_charge normalized_charge lambda_change').split()
    return {'type': 'SCBAIteration', 'fields': dict(ν=integer(1),
            **{name: ieee() for name in floats}, witness=None, physical_markers=None)}


def history():
    return dict(type='ScientificHistorySnapshot', fields=dict(
        action=sym('append'), stage=sym('scba'), domain_revision=integer(0),
        discretization_id='grid', basis_id='basis', outer_iteration=integer(1),
        inner_iteration=integer(1), sequence=integer(7), converged=False, status=sym('running'),
        quality=sym('unresolved'), strict_streak=integer(0), diagnostic_streak=integer(0),
        units=[], missing_reasons=[], row=scba_row()))


def row_key():
    return {name: deepcopy(history()['fields'][name]) for name in
            ('domain_revision', 'discretization_id', 'basis_id', 'stage',
             'outer_iteration', 'inner_iteration')}


def record():
    return dict(schema='qcl-negf.scientific-record.v1', contract_set='qcl-negf.results.v2',
                identity=identity(), invocation={'source_epoch': 'epoch1'}, stream_ordinal='1',
                row_key=row_key(), target=None, core=history())


def page(previous=None):
    value = dict(schema='qcl-negf.scientific-catalog.v1', contract_set='qcl-negf.results.v2',
                identity=identity(), invocation={'source_epoch': 'epoch1'}, generation='1', entries='1',
                previous=previous,
                artifacts=[dict(**ref('history/one.h5', 'qcl-negf-scientific-history-v5'),
                                role='science.history', profile='science', dependencies=[])],
                range={'first_record': '1', 'last_record': '1'},
                totals=dict(records='1', scba_rows='1', outer_rows='0', witness_updates='0', last_record='1'))
    value['artifacts'][0]['media_type'] = 'application/x-hdf5'
    return value


def test_old_native_schema_is_unsupported_in_new_catalog(api):
    value = page(); value['artifacts'][0]['media_type'] = 'application/x-hdf5'
    value['artifacts'][0]['schema'] = 'qcl-negf-scientific-history-v4'
    with pytest.raises(ContractError) as caught:
        api.validate_catalog_page(value)
    assert caught.value.code == 'unsupported_format'


def test_scientific_catalog_does_not_count_a_model_as_history(api):
    value=page()
    value['artifacts'][0].update(role='model',media_type='application/json',schema='qcl-negf-resolved-configuration-v3')
    with pytest.raises(ContractError,match='science.history'):
        api.validate_catalog_page(value)
    assert not schema_validator('scientific-catalog.schema.json').is_valid(value)


def test_new_format_is_strict_and_old_is_unsupported(api):
    healthy = manifest()
    checked = api.validate_manifest(healthy)
    assert checked == healthy and checked is not healthy
    for altered, code in ((dict(healthy, surprise=1), 'invalid_input'),
                          (dict(healthy, contract_set='qcl-negf.results.v1'), 'unsupported_format'),
                          (dict(healthy, schema='qcl-negf.result-manifest.v9'), 'unsupported_format')):
        with pytest.raises(ContractError) as caught:
            api.validate_manifest(altered)
        assert caught.value.code == code
    del healthy['checkpoint']
    with pytest.raises(ContractError, match='checkpoint'):
        api.validate_manifest(healthy)


@pytest.mark.parametrize('bad', [True, -1, '00', '+1', '1.0', '18446744073709551616'])
def test_counts_are_canonical_u64_without_bool_or_rounding(api, bad):
    value = manifest(); value['generation'] = bad
    with pytest.raises(ContractError):
        api.validate_manifest(value)


def test_provenance_change_does_not_change_scientific_binding(api):
    a = manifest(); b = deepcopy(a)
    b['provenance']['revision'] = 'd'*40
    b['provenance']['components'].append(dict(path='components/qcl-negf-portal', revision='e'*40,
                                            url='https://github.com/Afonenko-QCL-NEGF/qcl-negf-portal'))
    assert api.validate_manifest(a)['identity'] == api.validate_manifest(b)['identity']


def test_process_success_does_not_create_scientific_pass(api):
    value = manifest()
    checked = api.validate_manifest(value)
    assert checked['status']['process']['state'] == 'succeeded'
    assert checked['status']['physics'] == {'state': 'not_measured', 'reason': 'not_requested', 'evidence': None}
    for mutation in ({'state': 'pass', 'reason': None, 'evidence': None},
                     {'state': 'recorded', 'reason': None, 'evidence': None}):
        value['status']['physics'] = mutation
        with pytest.raises(ContractError):
            api.validate_manifest(value)


def test_pointer_cursor_and_checkpoint_relations(api):
    source = manifest()
    pointer = dict(schema='qcl-negf.result-pointer.v1', contract_set='qcl-negf.results.v2',
                   identity=identity(), generation='1', manifest=ref())
    assert api.validate_pointer(pointer) == pointer
    cursor = dict(schema='qcl-negf.result-cursor.v1', contract_set='qcl-negf.results.v2',
                  identity=identity(), invocation={'source_epoch': 'epoch1'}, manifest=ref(),
                  history=pin(), leaf=None, row_offset='0', last_record='0')
    assert api.validate_cursor(cursor, manifest=source, manifest_ref=ref()) == cursor
    for key, value in (('history', dict(pin(), scba_rows='1')), ('identity', identity('2')),
                       ('invocation', {'source_epoch': 'other'}), ('last_record', '1')):
        with pytest.raises(ContractError):
            api.validate_cursor(dict(cursor, **{key: value}), manifest=source, manifest_ref=ref())


def test_catalog_pin_binds_exact_prefix_and_attempt(api):
    first = page()
    assert api.validate_catalog_page(first) == first
    previous = dict(head=ref('catalog/one.json', 'qcl-negf.scientific-catalog.v1'), entries='1', **first['totals'])
    second = page(previous)
    second.update(generation='2', entries='2', range={'first_record': '2', 'last_record': '3'},
                  totals=dict(records='3', scba_rows='2', outer_rows='0', witness_updates='1', last_record='3'))
    second['artifacts'][0]['path'] = 'history/two.h5'
    assert api.validate_catalog_page(second, previous=previous,previous_page=first,previous_ref=previous['head']) == second
    for mutate in (dict(second, entries='3'), dict(second, previous=None),
                   dict(second, totals=dict(second['totals'], records='4')),
                   dict(second, range={'first_record': '1', 'last_record': '3'})):
        with pytest.raises(ContractError):
            api.validate_catalog_page(mutate, previous=previous,previous_page=first,previous_ref=previous['head'])
    duplicate = page(); duplicate['artifacts'] *= 2
    with pytest.raises(ContractError):
        api.validate_catalog_page(duplicate)


def test_scientific_row_key_and_delivery_ordinal_have_distinct_scopes(api):
    value = record()
    assert api.validate_scientific_record(value) == value
    value['core']['fields']['sequence'] = integer(900)
    assert api.validate_scientific_record(value)['stream_ordinal'] == '1'
    value['row_key']['basis_id'] = 'other'
    with pytest.raises(ContractError, match='row_key'):
        api.validate_scientific_record(value)


def test_witness_target_same_leaf_has_no_circular_hash(api):
    value = record(); value['stream_ordinal'] = '2'
    value['core']['fields']['action'] = sym('witness_update')
    target = dict(scope='same_leaf', source_identity=identity(), source_epoch='epoch1',
                  append_ordinal='1', leaf=None, row_offset='0', anchor_state=None, anchor_history=None)
    value['target'] = target
    assert api.validate_scientific_record(value) == value
    for changed in (dict(target, leaf=ref('self.h5')), dict(target, append_ordinal='2'),
                    dict(target, source_epoch='old'), dict(target, anchor_history=pin())):
        with pytest.raises(ContractError):
            api.validate_scientific_record(dict(value, target=changed))


def test_witness_target_requires_parent_context(api):
    value = record(); value['stream_ordinal'] = '2'
    value['core']['fields']['action'] = sym('witness_update')
    value['target'] = dict(scope='parent_checkpoint', source_identity=identity(), source_epoch='epoch1',
        append_ordinal='1', leaf=ref('old.h5'), row_offset='0',
        anchor_state=dict(identity=identity(), state_id='s', state_sequence='1', manifest=ref()),
        anchor_history=pin())
    with pytest.raises(ContractError, match='parent_checkpoint'):
        api.validate_scientific_record(value)


def test_unknown_native_fields_and_nonfinite_json_fail_before_science(api):
    value = record(); value['core']['fields']['invented'] = None
    with pytest.raises(ContractError, match='invented'):
        api.validate_scientific_record(value)
    with pytest.raises(ContractError):
        decode(b'{"value":NaN}')
    for bits in ('0000000000000000', '8000000000000000', '7ff0000000000000',
                 'fff0000000000000', '7ff8000000000001', '7ff8000000000002'):
        value = record(); value['core']['fields']['row']['fields']['r_D'] = ieee(bits)
        assert api.validate_scientific_record(decode(encode(value))) == value


def test_new_schema_bundle_is_independent_of_python_semantic_helpers(api):
    healthy = manifest()
    schema_validator('result-manifest.schema.json').validate(healthy)
    healthy['unknown'] = 1
    assert not schema_validator('result-manifest.schema.json').is_valid(healthy)


def catalog_pair():
    first=page()
    previous=dict(head=ref('catalog/one.json','qcl-negf.scientific-catalog.v1'),entries='1',**first['totals'])
    second=page(previous)
    second.update(generation='3',entries='2',range=dict(first_record='2',last_record='2'),
                  totals=dict(records='2',scba_rows='2',outer_rows='0',witness_updates='0',last_record='2'))
    second['artifacts'][0]['path']='history/two.h5'
    return first,previous,second


@pytest.mark.parametrize('different_hash', [False,True])
def test_catalog_rejects_adjacent_leaf_replay_and_path_rebinding(api, different_hash):
    first,previous,second=catalog_pair()
    context=dict(previous=previous,previous_page=first,previous_ref=previous['head'])
    assert api.validate_catalog_page(second,**context) == second
    changed=deepcopy(second); changed['artifacts'][0]=deepcopy(first['artifacts'][0])
    if different_hash: changed['artifacts'][0]['sha256']='f'*64
    with pytest.raises(ContractError,match='reuses immutable leaf path'):
        api.validate_catalog_page(changed,**context)


def test_catalog_adjacent_uniqueness_checks_only_two_supplied_contents(api, monkeypatch):
    first,previous,second=catalog_pair(); count=10**18
    before=deepcopy(previous)
    before.update(entries=str(count-1),records=str(count-1),scba_rows=str(count-1),last_record=str(count-1))
    large=deepcopy(second)
    large.update(previous=before,entries=str(count),range=dict(first_record=str(count),last_record=str(count)),
                 totals=dict(records=str(count),scba_rows=str(count),outer_rows='0',witness_updates='0',last_record=str(count)))
    pin=dict(head=ref('catalog/large.json','qcl-negf.scientific-catalog.v1'),entries=str(count),**large['totals'])
    following=deepcopy(second)
    following['artifacts'][0]['path']='history/fresh-after-large.h5'
    following.update(previous=pin,generation='999',entries=str(count+1),
                     range=dict(first_record=str(count+1),last_record=str(count+1)),
                     totals=dict(records=str(count+1),scba_rows=str(count+1),outer_rows='0',
                                 witness_updates='0',last_record=str(count+1)))
    calls=[]; original=api._catalog_content
    def counted(value):
        calls.append(value)
        return original(value)
    monkeypatch.setattr(api,'_catalog_content',counted)
    assert api.validate_catalog_page(following,previous=pin,previous_page=large,previous_ref=pin['head']) == following
    assert calls == [following,large]


@pytest.mark.parametrize('changed_field', ['owner','epoch','generation','reference','pin_totals','extra_reference'])
def test_catalog_context_rejects_cross_stitch_with_same_previous_pin(api, changed_field):
    first,previous,second=catalog_pair()
    context=dict(previous=previous,previous_page=first,previous_ref=previous['head'])
    assert api.validate_catalog_page(second,**context) == second
    second=deepcopy(second); context=deepcopy(context)
    if changed_field == 'owner': second['identity']['point_id']='other'
    elif changed_field == 'epoch': second['invocation']['source_epoch']='other'
    elif changed_field == 'generation': context['previous_page']['generation']='3'
    elif changed_field == 'reference': context['previous_ref']['sha256']='f'*64
    elif changed_field == 'pin_totals':
        context['previous_page']['range']['last_record']='2'
        context['previous_page']['totals'].update(records='2',scba_rows='2',last_record='2')
    else: context['previous_ref']['extra']=None
    with pytest.raises(ContractError): api.validate_catalog_page(second,**context)


def test_catalog_context_is_required_and_only_one_preceding_page_is_needed(api):
    first,previous,second=catalog_pair()
    with pytest.raises(ContractError): api.validate_catalog_page(second,previous=previous)
    second_pin=dict(head=ref('catalog/two.json','qcl-negf.scientific-catalog.v1'),entries='2',**second['totals'])
    third=page(second_pin)
    third.update(generation='8',entries='3',range=dict(first_record='3',last_record='3'),
                 totals=dict(records='3',scba_rows='3',outer_rows='0',witness_updates='0',last_record='3'))
    third['artifacts'][0]['path']='history/three.h5'
    # second has its own nonnull previous, but no first page context is supplied or traversed.
    assert api.validate_catalog_page(third,previous=second_pin,previous_page=second,
                                     previous_ref=second_pin['head']) == third


def cursor_context():
    source=manifest(); source['history']=committed_pin()
    catalog=page(); leaf={key:catalog['artifacts'][0][key] for key in ref()}
    cursor=dict(schema='qcl-negf.result-cursor.v1',contract_set='qcl-negf.results.v2',
                identity=identity(),invocation={'source_epoch':'epoch1'},manifest=ref(),
                history=deepcopy(source['history']),leaf=leaf,row_offset='0',last_record='1')
    context=dict(manifest=source,manifest_ref=ref(),catalog_page=dict(
        reference=deepcopy(source['history']['head']),document=catalog))
    return cursor,context


@pytest.mark.parametrize('changed_field', ['manifest_hash','manifest_path','owner','epoch',
                                          'generation','leaf','range','head_totals','extra_context','page_hash'])
def test_cursor_context_binds_ref_and_containing_page(api, changed_field):
    cursor,context=cursor_context()
    assert api.validate_cursor(cursor,**context) == cursor
    cursor=deepcopy(cursor); context=deepcopy(context)
    document=context['catalog_page']['document']
    if changed_field == 'manifest_hash': cursor['manifest']['sha256']='f'*64
    elif changed_field == 'manifest_path': cursor['manifest']['path']='sibling.json'
    elif changed_field == 'owner': document['identity']['point_id']='other'
    elif changed_field == 'epoch': document['invocation']['source_epoch']='other'
    elif changed_field == 'generation': document['generation']='2'
    elif changed_field == 'leaf': document['artifacts'][0]['sha256']='f'*64
    elif changed_field == 'range': cursor['last_record']='0'
    elif changed_field == 'head_totals':
        document['range']['last_record']='2'
        document['totals'].update(records='2',scba_rows='2',last_record='2')
    elif changed_field == 'extra_context': context['catalog_page']['extra']=None
    else: context['catalog_page']['reference']['sha256']='f'*64
    with pytest.raises(ContractError): api.validate_cursor(cursor,**context)


def test_cursor_nonempty_leaf_requires_direct_page_context(api):
    cursor,context=cursor_context(); del context['catalog_page']
    with pytest.raises(ContractError): api.validate_cursor(cursor,**context)


def test_cursor_can_use_one_verified_older_page_without_ancestor_traversal(api):
    first,previous,second=catalog_pair()
    cursor,context=cursor_context()
    source=context['manifest']; source['generation']='3'
    source['history']=dict(head=ref('catalog/two.json','qcl-negf.scientific-catalog.v1'),
                           entries='2',**second['totals'])
    cursor['history']=deepcopy(source['history'])
    assert api.validate_cursor(cursor,**context) == cursor


def test_empty_cursor_rejects_unused_containing_page_context(api):
    cursor,context=cursor_context()
    cursor.update(history=pin(),leaf=None,row_offset='0',last_record='0')
    context['manifest']['history']=pin()
    context['catalog_page']={'extra':None}
    with pytest.raises(ContractError,match='catalog_page'): api.validate_cursor(cursor,**context)


@pytest.mark.parametrize('changed_field', ['anchor_hash','anchor_path','parent_state','parent_ref','missing_context'])
def test_parent_context_binds_actual_child_lineage_and_manifest_ref(api, changed_field):
    parent=checkpoint(); update=record(); update['identity']=identity('2')
    update['invocation']['source_epoch']='epoch2'; update['core']['fields']['action']=sym('witness_update')
    update['target']=dict(scope='parent_checkpoint',**deepcopy(parent['witness_targets'][0]['locator']),
                          anchor_state=state_ref(parent),anchor_history=deepcopy(parent['history']))
    context=dict(parent_checkpoint=parent,parent_state=state_ref(parent),parent_manifest_ref=ref('parent-manifest.json'))
    assert api.validate_scientific_record(update,**context) == update
    changed=deepcopy(update); context=deepcopy(context)
    if changed_field == 'anchor_hash': changed['target']['anchor_state']['manifest']['sha256']='f'*64
    elif changed_field == 'anchor_path': changed['target']['anchor_state']['manifest']['path']='sibling.json'
    elif changed_field == 'parent_state': context['parent_state']['state_id']='sibling'
    elif changed_field == 'parent_ref': context['parent_manifest_ref']['sha256']='f'*64
    else: del context['parent_state']
    with pytest.raises(ContractError): api.validate_scientific_record(changed,**context)


def checkpoint(attempt='1', parent=None):
    # Constructor-only golden is deliberately not a scientifically validated restart.
    folder = Path(__file__).parent / 'fixtures/results-v2'
    producer = json.loads((folder/'core-producer.json').read_text())
    values = {value['type']: deepcopy(value) for value in producer['values']}
    state = values['ExactSolverState']; fields = state['fields']; scba = fields['scba']['fields']
    fields['boundary'] = sym('scba_accepted')
    fields['continuation'] = {'type':'SCBAContinuation','fields':dict(
        decision={'type':'SCBAStopDecision','fields':dict(terminal=False,converged=False,
            status=sym('running'),quality=sym('unresolved'),reason='manufactured')},
        candidate={'type':'FixedPointAuditCandidate','fields':dict(scattering=scba['scattering'],
            embedding=scba['embedding'],plus=scba['embedding_plus'],minus=scba['embedding_minus'],roundoff=ieee())},
        next_previous_current=ieee(),next_previous_populations=fields['published_n'],
        seed_mu_scaled=None,seed_number_ratio=None,witness_retention=[integer(1),integer(1),integer(1)])}
    array_ref = fields['published_U']['file']
    leaf = {**ref('history/original.h5','qcl-negf-scientific-history-v5'),'media_type':'application/x-hdf5'}
    locator = dict(source_identity=identity(),source_epoch='epoch1',append_ordinal='1',leaf=leaf,row_offset='0')
    package = Path(__file__).parents[1]/'src/qcl_negf_contracts'
    layout = json.loads((package/'core_layout.json').read_text())
    return dict(schema='qcl-negf.checkpoint-declaration.v1',contract_set='qcl-negf.results.v2',
        identity=identity(attempt),lineage={'parent_state':parent},invocation={'source_epoch':'epoch'+attempt},
        state_id='state'+attempt,state_sequence='1',core_layout_sha256=layout['layout_sha256'],
        numerical_binding=dict(identity=deepcopy(fields['identity']),execution=values['ExactExecutionIdentity']),
        history=committed_pin() if attempt == '1' else pin(),state=state,payloads=[array_ref,leaf],
        witness_targets=[{'row_key':row_key(),'locator':locator}])


def state_ref(value):
    return dict(identity=value['identity'],state_id=value['state_id'],state_sequence=value['state_sequence'],
                manifest=ref('parent-manifest.json'))


def parent_context(value):
    return dict(parent_checkpoint=value,parent_state=state_ref(value),
                parent_manifest_ref=ref('parent-manifest.json'))


def committed_pin(cutoff='1'):
    return dict(head=ref('catalog/one.json','qcl-negf.scientific-catalog.v1'),
                entries='1',records=cutoff,scba_rows=cutoff,outer_rows='0',
                witness_updates='0',last_record=cutoff)


@pytest.mark.parametrize('violation', ['empty_pin', 'beyond_cutoff'])
def test_current_epoch_target_is_within_checkpoint_committed_pin(api, violation):
    healthy=checkpoint(); healthy['history']=committed_pin()
    assert api.validate_checkpoint_declaration(healthy) == healthy
    changed=deepcopy(healthy)
    if violation == 'empty_pin': changed['history']=pin()
    else: changed['witness_targets'][0]['locator']['append_ordinal']='2'
    with pytest.raises(ContractError,match='committed history cutoff'):
        api.validate_checkpoint_declaration(changed)


def test_carried_original_ordinal_keeps_ancestor_epoch_scope_across_two_resumes(api):
    a=checkpoint(); a['history']=committed_pin('9')
    a['witness_targets'][0]['locator']['append_ordinal']='9'
    assert api.validate_checkpoint_declaration(a) == a
    b=checkpoint('2',state_ref(a)); b['history']=pin()
    b['witness_targets']=deepcopy(a['witness_targets'])
    assert api.validate_checkpoint_declaration(b) == b
    update=record(); update['identity']=identity('3'); update['invocation']['source_epoch']='epoch3'
    update['core']['fields']['action']=sym('witness_update')
    update['target']=dict(scope='parent_checkpoint',**deepcopy(b['witness_targets'][0]['locator']),
                          anchor_state=state_ref(b),anchor_history=deepcopy(b['history']))
    assert api.validate_scientific_record(update,**parent_context(b)) == update
    changed=deepcopy(update); changed['target']['source_epoch']='epoch2'
    with pytest.raises(ContractError,match='original append locator'):
        api.validate_scientific_record(changed,**parent_context(b))


def test_witness_target_survives_two_resumes_without_prefix_scan(api):
    a = checkpoint(); assert api.validate_checkpoint_declaration(a) == a
    b = checkpoint('2',state_ref(a)); assert api.validate_checkpoint_declaration(b) == b
    update = record(); update['identity'] = identity('3'); update['invocation']['source_epoch'] = 'epoch3'
    update['core']['fields']['action'] = sym('witness_update')
    update['target'] = dict(scope='parent_checkpoint',**b['witness_targets'][0]['locator'],
                            anchor_state=state_ref(b),anchor_history=b['history'])
    # Only the immediate checked parent and direct original leaf declaration are supplied.
    assert api.validate_scientific_record(update,**parent_context(b)) == update
    for key, bad in (('anchor_history',dict(pin(),records='1')),('source_epoch','epoch2'),
                     ('row_offset','1'),('append_ordinal','2'),('leaf',dict(update['target']['leaf'],sha256='e'*64))):
        changed=deepcopy(update); changed['target'][key]=bad
        with pytest.raises(ContractError):
            api.validate_scientific_record(changed,**parent_context(b))
    changed=deepcopy(update); changed['target']['anchor_state']['state_id']='sibling'
    with pytest.raises(ContractError):
        api.validate_scientific_record(changed,**parent_context(b))


def test_witness_target_set_follows_core_receipt(api):
    value=checkpoint()
    value['state']['fields']['continuation']['fields']['witness_retention']=[integer(4),integer(1),integer(1)]
    assert len(api.validate_checkpoint_declaration(value)['witness_targets']) == 1
    changed=deepcopy(value); changed['witness_targets'] *= 2
    with pytest.raises(ContractError,match='retention receipt'):
        api.validate_checkpoint_declaration(changed)
    for boundary in ('outer_accepted','domain_final','final'):
        changed=deepcopy(value); changed['state']['fields']['boundary']=sym(boundary)
        with pytest.raises(ContractError,match='retention receipt'):
            api.validate_checkpoint_declaration(changed)
        changed['witness_targets']=[]
        assert api.validate_checkpoint_declaration(changed)['state']['fields']['scba']['fields']['history'] == value['state']['fields']['scba']['fields']['history']
    changed=deepcopy(value); changed['state']['fields']['continuation']['fields']['decision']['fields']['terminal']=True
    changed['witness_targets']=[]
    assert api.validate_checkpoint_declaration(changed)['witness_targets'] == []


def test_checkpoint_rejects_missing_payload_and_mismatched_core_binding(api):
    for key in ('payloads','witness_targets'):
        value=checkpoint(); value[key]=[]
        with pytest.raises(ContractError): api.validate_checkpoint_declaration(value)
    value=checkpoint(); value['numerical_binding']['identity']['fields']['contract_version']=integer(2,'UInt16')
    with pytest.raises(ContractError,match='identity'):
        api.validate_checkpoint_declaration(value)


def test_signed_width_bits_and_dataset_locators_are_not_coerced(api):
    for bad in (integer(2**63),integer(-2**63-1),integer('-0')):
        value=record(); value['core']['fields']['sequence']=bad
        with pytest.raises(ContractError): api.validate_scientific_record(value)
    value=record(); value['core']['fields']['row']['fields']['r_D']={'kind':'ieee','type':'f64','bits':'7ff800000000000'}
    with pytest.raises(ContractError): api.validate_scientific_record(value)
    value=checkpoint(); value['state']['fields']['published_U']['dataset']='/../escape'
    with pytest.raises(ContractError,match='dataset'):
        api.validate_checkpoint_declaration(value)


def test_integer_width_and_typed_evidence_values_roundtrip_exactly():
    validator=schema_validator('core-state.schema.json')
    for scalar in (integer(-2**63),integer(2**63-1),integer(9007199254740993),
                   True,'same-text',sym('same-text'),
                   {'kind':'complex','real':ieee('8000000000000000'),'imag':ieee('7ff8000000000001')}):
        value={'type':'CoreScalar','fields':{'value':scalar}}
        validator.validate(value)
        assert decode(encode(value)) == value


def test_invalid_artifact_path_reports_exact_json_location(api):
    value=page(); value['artifacts'][0]['path']='../outside.h5'
    with pytest.raises(ContractError,match=r'\$\.artifacts\[0\]\.path'):
        api.validate_catalog_page(value)


def test_units_missing_reasons_and_original_fresh_oracle_remain_distinct(api):
    folder=Path(__file__).parent/'fixtures/results-v2'
    values={item['type']:item for item in json.loads((folder/'core-producer.json').read_text())['values']}
    snapshot=values['ScientificHistorySnapshot']
    fields=snapshot['fields']
    units={item['fields']['first']['value']:item['fields']['second'] for item in fields['units']}
    reasons={item['fields']['first']['value']:item['fields']['second']['value'] for item in fields['missing_reasons']}
    assert units['J']=='A/m^2'
    assert reasons['r_Jchange']=='no_previous_iteration'
    assert fields['row']['fields']['r_Jchange']==ieee('7ff8000000000001')
    value=record(); value['core']=snapshot
    assert api.validate_scientific_record(value)['core']==snapshot
    evidence=values['CompletedStateEvidence']['fields']
    assert evidence['original']['fields']['report']['fields']['passed'] is False
    assert evidence['revalidation']['fields']['status']==sym('error')
    assert evidence['independent_oracle']['fields']['status']==sym('not_measured')


def test_unknown_layout_is_unsupported_before_restore(api):
    value=checkpoint(); value['core_layout_sha256']='f'*64
    with pytest.raises(ContractError) as caught:
        api.validate_checkpoint_declaration(value)
    assert caught.value.code == 'unsupported_format'


def test_old_payload_is_unsupported_even_if_all_file_refs_agree(api):
    value=checkpoint()
    def replace(item):
        if isinstance(item,dict):
            if item.get('schema')=='qcl-negf-checkpoint-v5': item['schema']='qcl-negf-checkpoint-v4'
            for child in item.values(): replace(child)
        elif isinstance(item,list):
            for child in item: replace(child)
    replace(value)
    with pytest.raises(ContractError) as caught:
        api.validate_checkpoint_declaration(value)
    assert caught.value.code == 'unsupported_format'
