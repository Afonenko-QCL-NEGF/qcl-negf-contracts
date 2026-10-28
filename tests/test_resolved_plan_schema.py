"""Canonical P03 metadata structure, independently from Runner semantic fingerprints."""
from copy import deepcopy
import json
from pathlib import Path

import pytest

from qcl_negf_contracts import schema_names, schema_validator
from qcl_negf_contracts.messages import ContractError, decode, encode

METADATA = Path(__file__).parent / 'fixtures/resolved-plan/metadata.json'


def plan():
    metadata=json.loads(METADATA.read_text())
    snapshot=metadata['snapshot']
    return dict(schema='qcl-negf-scientific-plan-v2',model_revision='transport-contract-v2',
        resolved_snapshot_schema='qcl-negf-resolved-configuration-v1',root_definition_id='study',
        root_kind='study',name='Manufactured schema metadata',fingerprint='a'*64,
        scientific_fingerprint='b'*64,maximum_solver_runs=1,computation_count=1,inclusions=[],
        executions=[dict(id='execution',definition_id='study',variant_id='variant',method_id='method',
            label='',point_ids=['point'],resolved_configuration=deepcopy(snapshot['raw_configuration']),
            provenance={},policies={},estimated_peak_bytes=256,purpose='diagnostic',repetition=1,
            operation='stationary',effective_inputs=dict(seed={},energy_shift='none',energy_nodes=3,
                energy_min_eV=-1.0,energy_max_eV=1.0),output=metadata['output'],
            resolved_snapshot=snapshot,resource_estimate=metadata['receipt'])],
        points=[dict(id='point',execution_id='execution',temperature_K=70.0,voltage_per_period_V=0.05,
            branch='forward',order=1,predecessor_id=None,initialization='cold',effective_inputs=dict(
                temperature_K=70.0,voltage_per_period_V=0.05,configuration_hash='c'*64,
                hash_encoding='qcl-negf-canonical-bytes-v1',axes_applied=True,model_sha256='d'*64))],
        resources=dict(maximum_active_executions=1,estimated_peak_bytes=256,minimum_output_bytes=0),
        nodes=[],campaign=None,science_archive_preflight=None)


def test_new_plan_schema_accepts_resolved_metadata_without_equating_point_and_template_models():
    value=plan()
    assert value['points'][0]['effective_inputs']['model_sha256'] != value['executions'][0]['resolved_snapshot']['model_binding']['sha256']
    schema_validator('scientific-plan.schema.json').validate(decode(encode(value)))


def test_resource_schema_accepts_both_exact_receipt_variants():
    receipt=plan()['executions'][0]['resource_estimate']
    schema_validator('resource-estimate.schema.json').validate(receipt)
    value=plan(); value['executions'][0].update(operation='operator_algebra',estimated_peak_bytes=0,
        resource_estimate=dict(schema='qcl-negf-resource-estimate-v1',status='not_applicable',
                              decision_kind='planning_estimate',estimated_numerical_peak_bytes=None))
    schema_validator('scientific-plan.schema.json').validate(value)


@pytest.mark.parametrize('path', [('resolved_snapshot_schema',),('executions',0,'resolved_snapshot'),
    ('executions',0,'resource_estimate'),('points',0,'effective_inputs','model_sha256')])
def test_new_plan_members_are_required(path):
    value=plan(); parent=value
    for part in path[:-1]: parent=parent[part]
    del parent[path[-1]]
    assert not schema_validator('scientific-plan.schema.json').is_valid(value)


@pytest.mark.parametrize('path', [(),('executions',0),('points',0,'effective_inputs'),
    ('executions',0,'resolved_snapshot'),('executions',0,'resolved_snapshot','sections'),
    ('executions',0,'resolved_snapshot','sections','physical'),
    ('executions',0,'resolved_snapshot','derived'),('executions',0,'resolved_snapshot','derived','effective_seed'),
    ('executions',0,'resolved_snapshot','model_binding'),('executions',0,'resource_estimate'),
    ('executions',0,'resource_estimate','initial'),('executions',0,'resource_estimate','basis')])
def test_closed_metadata_rejects_unknown_members(path):
    value=plan(); parent=value
    for part in path: parent=parent[part]
    parent['unknown']=None
    assert not schema_validator('scientific-plan.schema.json').is_valid(value)


@pytest.mark.parametrize('field', ['runtime_overhead_bytes','allocator_overhead_bytes','measured_rss_bytes',
                                  'admitted_memory_bytes','total_memory_request_bytes'])
def test_unknown_receipt_costs_require_explicit_null_instead_of_missing_or_zero(field):
    for missing in (False,True):
        value=plan(); receipt=value['executions'][0]['resource_estimate']
        if missing: del receipt[field]
        else: receipt[field]=0
        assert not schema_validator('scientific-plan.schema.json').is_valid(value)


@pytest.mark.parametrize('field,value', [('worker_capacity',True),('worker_capacity',0),
    ('worker_capacity','2'),('initial_energy_nodes',2),('declared_maximum_energy_nodes',False),
    ('retained_resident_bytes',-1),('estimated_numerical_peak_bytes',2**63)])
def test_receipt_native_integer_types_and_ranges(field,value):
    receipt=deepcopy(plan()['executions'][0]['resource_estimate']);receipt[field]=value
    assert not schema_validator('resource-estimate.schema.json').is_valid(receipt)


def test_snapshot_finite_metadata_preserves_owning_projection_without_parameter_field_map():
    value=plan(); snapshot=value['executions'][0]['resolved_snapshot']
    snapshot['sections']['physical']['used']={'nullable':None,'quantity':{'value':1.5,'unit':'eV'},
                                            'metadata':[False,1,0.25,'sample',{'nested':None}]}
    schema_validator('scientific-plan.schema.json').validate(value)
    for bad in (float('nan'),float('inf'),-float('inf')):
        snapshot['sections']['physical']['used']['quantity']['value']=bad
        with pytest.raises(ContractError): encode(value)


def test_snapshot_rejects_truncated_section_or_seed_receipt():
    for path in [('sections','physical'),('derived','effective_seed','working_eta_eV')]:
        value=plan(); parent=value['executions'][0]['resolved_snapshot']
        for part in path[:-1]:parent=parent[part]
        del parent[path[-1]]
        assert not schema_validator('scientific-plan.schema.json').is_valid(value)


def test_snapshot_assignment_history_requires_a_string_array():
    value=plan()
    value['executions'][0]['resolved_snapshot']['sections']['physical']['input_assigning_histories']={
        'physical.temperature':'source-string-is-not-an-ordered-history'}
    assert not schema_validator('scientific-plan.schema.json').is_valid(value)


def test_wrong_marker_hash_sources_and_receipt_variants_are_rejected():
    validator=schema_validator('scientific-plan.schema.json')
    for path,bad in [(('resolved_snapshot_schema',),'legacy'),
        (('executions',0,'resolved_snapshot','model_binding','sha256'),'A'*64),
        (('executions',0,'resolved_snapshot','default_rule_sources'),{}),
        (('executions',0,'resolved_snapshot','sections','physical','origin'),'guessed_default'),
        (('executions',0,'resolved_snapshot','derived','effective_seed','clamped'),0),
        (('executions',0,'resource_estimate','unknown'),['native_grant']),
        (('executions',0,'resource_estimate','status'),'measured')]:
        value=plan(); parent=value
        for part in path[:-1]:parent=parent[part]
        parent[path[-1]]=bad
        assert not validator.is_valid(value),path


def test_new_schema_resources_are_public_offline_resources():
    assert {'resolved-configuration.schema.json','resource-estimate.schema.json'} <= set(schema_names())
