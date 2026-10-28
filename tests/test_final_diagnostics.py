"""Pure manufactured final observations; no HDF reads, solve, or validated restart."""
from copy import deepcopy
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from qcl_negf_contracts import load_schema, schema_names, schema_validator
from qcl_negf_contracts import results
from qcl_negf_contracts.messages import ContractError, decode, encode
from test_results_v2 import checkpoint, ieee, integer, manifest, pin, ref, sym

KINDS = ['spectral', 'occupied', 'unoccupied', 'broadening', 'raw_occupied', 'raw_unoccupied']
SCALARS = ['minimum_eigenvalue', 'block_norm', 'floor', 'ratio', 'absolute_defect',
           'relative_defect', 'backward_error', 'hermiticity_defect', 'construction_scale']


def inputs():
    cp = checkpoint()
    state = cp['state']['fields']
    state.update(boundary=sym('final'), continuation=None, status=sym('invalid'),
                 final_evidence={'type': 'FinalEvidenceSnapshot', 'fields': dict(
                     report={'type': 'ConvergenceReport', 'fields': dict(passed=False,
                         metrics={'kind': 'dict', 'entries': []}, messages={'kind': 'array',
                             'eltype': 'String', 'shape': ['1'], 'order': 'F', 'values': ['manufactured failure']})},
                     original_converged=False, original_status=sym('invalid'),
                     observations={'type': 'CoreRecord', 'fields': {'entries': []}})})
    cp.update(history=pin(), witness_targets=[], payloads=cp['payloads'][:1])
    cp['payloads'][0]['schema'] = 'qcl-negf-physics-v5'
    def close_array_refs(node):
        if isinstance(node, dict):
            if node.get('kind') == 'array' and 'file' in node:
                node['file']['schema'] = 'qcl-negf-physics-v5'
            for child in node.values(): close_array_refs(child)
        elif isinstance(node, list):
            for child in node: close_array_refs(child)
    close_array_refs(state)
    cpref = ref('checkpoint/final.json', 'qcl-negf.checkpoint-declaration.v1')
    analysis = {**ref('analysis/final.h5', 'qcl-negf-physics-analysis-v5'),
                'media_type': 'application/x-hdf5'}
    source = manifest()
    for key in ('identity', 'lineage', 'invocation', 'state_id', 'state_sequence',
                'history', 'numerical_binding'):
        source[key] = deepcopy(cp[key])
    source.update(closed=True, checkpoint=cpref)
    source['status']['process'].update(state='failed', exit_code=1, reason='manufactured failure')
    source['artifacts'] = [dict(cp['payloads'][0], role='physics.full', profile='full-state', dependencies=[]),
        dict(cpref, role='recovery', profile='full-state', dependencies=[cp['payloads'][0]['path']]),
        dict(analysis, role='physics.analysis', profile='science', dependencies=[cpref['path']])]
    def array(name, shape, eltype, axes, units):
        return dict(dataset='/final_diagnostics/arrays/'+name, eltype=eltype,
                    shape=shape, order='F', axes=axes, units=units)
    integrals = dict(
        spectral_integral=array('spectral_integral', ['2', '1', '1'], 'ComplexF64', ['k', 'a', 'b'], '1'),
        spectral_integral_eigenvalues=array('spectral_integral_eigenvalues', ['2', '1'], 'Float64', ['k', 'state'], '1'),
        spectral_trace_cumulative=array('spectral_trace_cumulative', ['3', '2'], 'Float64', ['E', 'k'], '1'),
        negative_energy_integral_scaled=array('negative_energy_integral_scaled', ['6', '2'], 'Float64', ['matrix_kind', 'k'],
            'scaled solver units; broadening carries energy squared'),
        negative_block_count=[integer(0) for _ in KINDS],
        beyond_backward_error_block_count=[integer(0) for _ in KINDS],
        invalid_block_count=[integer(0) for _ in KINDS], total_blocks_per_kind=integer(6),
        negative_phase_space_weight_per_m2=[ieee() for _ in range(5)])
    positivity = dict(metric_version=integer(1), matrix_kinds=KINDS.copy(),
        witnesses=[dict(status='measured', matrix_kind=kind, energy_index=integer(1),
            momentum_index=integer(2), **{name: ieee() for name in SCALARS}) for kind in KINDS],
        strict_ratio_limit=ieee('3fb999999999999a'), strict_absolute_limits_scaled=[ieee() for _ in KINDS],
        strict_threshold_satisfied=[False]*6, scan_order='momentum_energy', integrals=integrals)
    value = dict(schema='qcl-negf.final-diagnostics.v1', contract_set='qcl-negf.results.v2',
        identity=deepcopy(cp['identity']), invocation=deepcopy(cp['invocation']),
        state_id=cp['state_id'], state_sequence=cp['state_sequence'], checkpoint=deepcopy(cpref),
        dimensions=dict(energy='3', momentum='2', basis='1'), solution_metrics=dict(
            summary_metrics=[dict(name='r_D', value=ieee('7ff8000000000001'))],
            strict_limits=[dict(name='r_D', value=ieee('3fb999999999999a'))], approximate_limits=None),
        positivity=dict(status='measured', reason=None, data=positivity))
    return value, dict(checkpoint=cp, manifest=source, artifact_ref=analysis)


def validate(value, context):
    function = getattr(results, 'validate_final_diagnostics', None)
    assert callable(function), 'pure final diagnostics API missing'
    return function(value, **context)


def test_stored_final_observations_are_detached_and_do_not_promote_failed_science():
    value, context = inputs()
    before = deepcopy(context)
    checked = validate(decode(encode(value)), context)
    assert checked == value and checked is not value
    checked['positivity']['data']['witnesses'][0]['ratio']['bits'] = 'fff0000000000000'
    assert value['positivity']['data']['witnesses'][0]['ratio']['bits'] == '0000000000000000'
    assert context == before
    assert context['checkpoint']['state']['fields']['final_evidence']['fields']['report']['fields']['passed'] is False
    assert context['manifest']['status']['physics']['state'] == 'not_measured'


def test_final_diagnostics_schema_is_an_offline_resource_and_exports_actual_public_fields():
    assert 'final-diagnostics.schema.json' in schema_names(), 'new schema resource missing'
    value, _ = inputs()
    schema_validator('final-diagnostics.schema.json').validate(value)
    fields = json.loads((Path(__file__).parent/'fixtures/final-diagnostics/core-public-fields.json').read_text())
    schema = load_schema('final-diagnostics.schema.json')
    Draft202012Validator.check_schema(schema)
    for name, declarations in fields['types'].items():
        definition = schema['$defs'][name]
        expected = [row['name'] for row in declarations]
        assert set(definition['properties']) == set(expected)
        assert set(definition['required']) == set(expected)
        assert definition['additionalProperties'] is False


@pytest.mark.parametrize('bits', ['0000000000000000', '8000000000000000', '7ff0000000000000',
    'fff0000000000000', '7ff8000000000001', '7ff8000000000002', '7ff0000000000001'])
def test_all_ieee_bits_survive_without_finite_or_null(bits):
    value, context = inputs()
    p = value['positivity']['data']
    p['witnesses'][0].update(status='error', matrix_kind='none', energy_index=integer(0), momentum_index=integer(0))
    for name in SCALARS:
        p['witnesses'][0][name] = ieee(bits)
    p['strict_ratio_limit'] = ieee(bits)
    p['strict_absolute_limits_scaled'][0] = ieee(bits)
    p['integrals']['negative_phase_space_weight_per_m2'][0] = ieee(bits)
    value['solution_metrics']['strict_limits'][0]['value'] = ieee(bits)
    checked = validate(decode(encode(value)), context)
    assert checked['positivity']['data']['witnesses'][0]['minimum_eigenvalue']['bits'] == bits
    assert checked['positivity']['data']['integrals']['negative_phase_space_weight_per_m2'][0]['bits'] == bits
    assert checked['solution_metrics']['strict_limits'][0]['value']['bits'] == bits


@pytest.mark.parametrize('status', ['error', 'not_measured'])
def test_unavailable_measurement_retains_reason_without_fake_data(status):
    value, context = inputs()
    value['positivity'] = dict(status=status, reason='explicit manufactured cause', data=None)
    assert validate(value, context)['positivity'] == value['positivity']
    for reason, data in [(None, None), ('', None), ('cause', inputs()[0]['positivity']['data'])]:
        changed = deepcopy(value); changed['positivity'].update(reason=reason, data=data)
        with pytest.raises(ContractError): validate(changed, context)


@pytest.mark.parametrize('field', ['identity', 'invocation', 'state_id', 'state_sequence', 'checkpoint'])
def test_declaration_cannot_cross_stitch_selected_final_source(field):
    value, context = inputs()
    assert validate(value, context) == value
    if field == 'identity': value[field]['branch_id'] = 'other'
    elif field == 'invocation': value[field]['source_epoch'] = 'other'
    elif field == 'checkpoint': value[field]['sha256'] = 'e'*64
    else: value[field] = '2' if field == 'state_sequence' else 'other'
    with pytest.raises(ContractError): validate(value, context)


@pytest.mark.parametrize('violation', ['artifact_hash', 'artifact_size', 'artifact_path', 'artifact_schema',
    'absent_artifact', 'wrong_dependency', 'extra_dependency', 'wrong_profile', 'open', 'running_process', 'scba', 'domain_final',
    'missing_final_evidence', 'binding', 'checkpoint_hash', 'checkpoint_epoch', 'checkpoint_state',
    'payload_inventory_hash', 'checkpoint_dependency', 'payload_cycle', 'extra_ref'])
def test_selected_refs_and_terminal_checkpoint_joins_are_not_path_only(violation):
    value, context = inputs()
    assert validate(value, context) == value
    source = context['manifest']; row = source['artifacts'][-1]
    if violation == 'artifact_hash': context['artifact_ref']['sha256'] = 'f'*64
    elif violation == 'artifact_size': context['artifact_ref']['bytes'] = '41'
    elif violation == 'artifact_path': context['artifact_ref']['path'] = 'elsewhere.h5'
    elif violation == 'artifact_schema': context['artifact_ref']['schema'] = 'qcl-negf-optical-v5'
    elif violation == 'absent_artifact': source['artifacts'].pop()
    elif violation == 'wrong_dependency': row['dependencies'] = [source['artifacts'][0]['path']]
    elif violation == 'extra_dependency': row['dependencies'].append(source['artifacts'][0]['path'])
    elif violation == 'wrong_profile': row['profile'] = 'full-state'
    elif violation == 'open': source['closed'] = False
    elif violation == 'running_process': source['status']['process']['state'] = 'running'
    elif violation in ('scba', 'domain_final'): context['checkpoint']['state']['fields']['boundary'] = sym(violation)
    elif violation == 'missing_final_evidence': context['checkpoint']['state']['fields']['final_evidence'] = None
    elif violation == 'binding': source['numerical_binding']['execution']['fields']['core_code'] = 'other'
    elif violation == 'checkpoint_hash': source['checkpoint']['sha256'] = 'e'*64
    elif violation == 'checkpoint_epoch': context['checkpoint']['invocation']['source_epoch'] = 'other'
    elif violation == 'checkpoint_state': context['checkpoint']['state_id'] = 'other'
    elif violation == 'payload_inventory_hash': source['artifacts'][0]['sha256'] = 'e'*64
    elif violation == 'checkpoint_dependency': source['artifacts'][1]['dependencies'] = []
    elif violation == 'payload_cycle':
        context['checkpoint']['payloads'].append(deepcopy(context['artifact_ref']))
        source['artifacts'][1]['dependencies'].append(context['artifact_ref']['path'])
    else: context['artifact_ref']['surprise'] = True
    with pytest.raises(ContractError): validate(value, context)


@pytest.mark.parametrize('name,shape', [('spectral_integral', ['2', '1', '2']),
    ('spectral_integral_eigenvalues', ['1', '2']), ('spectral_trace_cumulative', ['2', '3']),
    ('negative_energy_integral_scaled', ['5', '2'])])
def test_each_integral_shape_is_bound_to_actual_checkpoint_axes(name, shape):
    value, context = inputs()
    assert validate(value, context) == value
    value['positivity']['data']['integrals'][name]['shape'] = shape
    with pytest.raises(ContractError): validate(value, context)


@pytest.mark.parametrize('violation', ['dimensions', 'source_A_shape', 'source_GR_shape', 'total', 'negative',
    'beyond', 'invalid', 'count_range', 'wrong_width', 'coordinate', 'measured_zero', 'kind', 'kind_order',
    'scan_order', 'light', 'error_flag', 'duplicate_metric', 'unsorted_metric', 'null_scalar', 'ieee_number',
    'ieee_upper', 'ieee_short', 'extra_witness', 'missing_witness', 'short_counts', 'phase_six',
    'array_alias', 'array_file', 'array_axis', 'array_unit', 'array_dtype', 'array_order', 'extra_manifest_hash'])
def test_raw_field_and_local_array_contract_rejects_loss_or_ambiguity(violation):
    value, context = inputs(); p = value['positivity']['data']; i = p['integrals']; w = p['witnesses'][0]
    assert validate(value, context) == value
    if violation == 'dimensions': value['dimensions']['energy'] = '4'
    elif violation.startswith('source_'):
        field = 'A' if violation == 'source_A_shape' else 'Gᴿ'
        context['checkpoint']['state']['fields']['scba']['fields']['green']['fields'][field]['shape'] = ['4', '2', '1', '1']
    elif violation == 'total': i['total_blocks_per_kind'] = integer(7)
    elif violation == 'negative': i['negative_block_count'][0] = integer(-1)
    elif violation == 'beyond': i['beyond_backward_error_block_count'][0] = integer(1)
    elif violation == 'invalid': i['invalid_block_count'][0] = integer(7)
    elif violation == 'count_range': i['total_blocks_per_kind'] = integer(2**63)
    elif violation == 'wrong_width': w['energy_index'] = integer(1, 'UInt8')
    elif violation == 'coordinate': w['energy_index'] = integer(4)
    elif violation == 'measured_zero': w['energy_index'] = integer(0)
    elif violation == 'kind': w['matrix_kind'] = 'occupied'
    elif violation == 'kind_order': p['matrix_kinds'][0:2] = ['occupied', 'spectral']
    elif violation == 'scan_order': p['scan_order'] = 'energy_momentum'
    elif violation == 'light': p['integrals'] = None
    elif violation == 'error_flag': w['status'] = 'error'; p['strict_threshold_satisfied'][0] = True
    elif violation == 'duplicate_metric': value['solution_metrics']['summary_metrics'] *= 2
    elif violation == 'unsorted_metric': value['solution_metrics']['summary_metrics'] += [dict(name='a', value=ieee())]
    elif violation == 'null_scalar': w['floor'] = None
    elif violation == 'ieee_number': w['ratio'] = 0.0
    elif violation == 'ieee_upper': w['ratio'] = ieee('7FF0000000000000')
    elif violation == 'ieee_short': w['ratio'] = ieee('0')
    elif violation == 'extra_witness': w['inferred_pass'] = True
    elif violation == 'missing_witness': del w['construction_scale']
    elif violation == 'short_counts': i['invalid_block_count'].pop()
    elif violation == 'phase_six': i['negative_phase_space_weight_per_m2'].append(ieee())
    elif violation == 'array_alias': i['spectral_integral']['dataset'] = i['spectral_trace_cumulative']['dataset']
    elif violation == 'array_file': i['spectral_integral']['file'] = context['artifact_ref']
    elif violation == 'array_axis': i['spectral_integral']['axes'] = ['a', 'b', 'k']
    elif violation == 'array_unit': i['negative_energy_integral_scaled']['units'] = '1'
    elif violation == 'array_dtype': i['spectral_integral']['eltype'] = 'Float64'
    elif violation == 'array_order': i['spectral_integral']['order'] = 'C'
    else: value['manifest_sha256'] = 'a'*64
    with pytest.raises(ContractError): validate(value, context)


@pytest.mark.parametrize('bad', ['00', '+1', '1.0', True, '0', '9223372036854775808'])
def test_dimensions_preserve_positive_actual_int64_domain(bad):
    value, context = inputs()
    assert validate(value, context) == value
    value['dimensions']['energy'] = bad
    with pytest.raises(ContractError): validate(value, context)


def test_optional_limits_and_error_witness_defaults_do_not_require_scientific_pass():
    value, context = inputs(); p = value['positivity']['data']
    value['solution_metrics']['approximate_limits'] = []
    p['witnesses'][0].update(status='error', matrix_kind='none', energy_index=integer(0), momentum_index=integer(0))
    p['witnesses'][0]['hermiticity_defect'] = ieee()  # actual legacy default, not measured zero
    p['witnesses'][0]['ratio'] = ieee('7ff0000000000000')
    p['integrals']['invalid_block_count'][0] = integer(6)
    assert validate(value, context) == value


def test_nonfinite_json_is_not_an_alternative_to_ieee_tags():
    value, context = inputs(); value['solution_metrics']['summary_metrics'][0]['value'] = float('nan')
    with pytest.raises(ContractError): validate(value, context)


@pytest.mark.parametrize('backedge', ['analysis', 'checkpoint', 'self', 'transitive_analysis'])
def test_selected_dependency_closure_rejects_reachable_cycles(backedge):
    value, context = inputs()
    assert validate(value, context) == value
    source = context['manifest']; payload = source['artifacts'][0]
    if backedge == 'analysis': payload['dependencies'] = [context['artifact_ref']['path']]
    elif backedge == 'checkpoint': payload['dependencies'] = [value['checkpoint']['path']]
    elif backedge == 'self': payload['dependencies'] = [payload['path']]
    else:
        extra = dict(deepcopy(payload), path='extra/transitive.h5', dependencies=[context['artifact_ref']['path']])
        source['artifacts'].append(extra); payload['dependencies'] = [extra['path']]
    with pytest.raises(ContractError, match='cycl'):
        validate(value, context)


def test_selected_closure_accepts_forward_branching_and_shared_leaf_dag():
    value, context = inputs(); source = context['manifest']; payload = source['artifacts'][0]
    # Deliberately non-topological inventory order; two branches share one descendant.
    shared = dict(deepcopy(payload), path='extra/shared.h5', dependencies=[])
    left = dict(deepcopy(payload), path='extra/left.h5', dependencies=[shared['path']])
    right = dict(deepcopy(payload), path='extra/right.h5', dependencies=[shared['path'], left['path']])
    source['artifacts'].extend([right, shared, left])
    payload['dependencies'] = [left['path'], right['path']]
    before = deepcopy(context)
    assert validate(value, context) == value and context == before


@pytest.mark.parametrize('close_cycle', [False, True])
def test_selected_closure_handles_long_flat_metadata_chain_without_recursion(close_cycle):
    value, context = inputs(); source = context['manifest']; payload = source['artifacts'][0]
    nodes = [dict(deepcopy(payload), path=f'extra/chain-{index}.h5', dependencies=[]) for index in range(1500)]
    payload['dependencies'] = [nodes[0]['path']]
    for node, following in zip(nodes, nodes[1:]): node['dependencies'] = [following['path']]
    source['artifacts'].extend(reversed(nodes))
    if close_cycle: nodes[-1]['dependencies'] = [nodes[700]['path']]
    assert len(encode(source)) < 8*1024*1024  # within the existing caller JSON byte budget
    if close_cycle:
        with pytest.raises(ContractError, match='cycl'): validate(value, context)
    else:
        assert validate(value, context) == value


def test_new_boundary_checks_only_selected_reachable_closure():
    value, context = inputs(); source = context['manifest']; payload = source['artifacts'][0]
    unrelated = dict(deepcopy(payload), path='unrelated/self.h5', dependencies=['unrelated/self.h5'])
    source['artifacts'].append(unrelated)
    # Generic published manifest validation is unchanged; this artifact is not selected/reachable.
    assert results.validate_manifest(source) == source
    assert validate(value, context) == value
