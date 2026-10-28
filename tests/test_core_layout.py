"""The schema's mandatory fields come from reflected public Core declarations."""
from copy import deepcopy
from pathlib import Path
import hashlib
import json
from urllib.parse import quote

import pytest

from qcl_negf_contracts import load_schema, schema_validator

PACKAGE = Path(__file__).parents[1] / 'src/qcl_negf_contracts'
FIXTURES = Path(__file__).parent / 'fixtures/results-v2'


def core_type_uri(name):
    token = name.replace('~', '~0').replace('/', '~1')
    return '#/$defs/'+quote(token, safe='')


def test_actual_core_layout_resource_exists():
    assert (PACKAGE / 'core_layout.json').is_file(), 'actual reflected Core layout missing'


def test_constructor_only_producer_values_validate_without_solver():
    assert (FIXTURES / 'core-producer.json').is_file(), 'constructors-only producer fixture missing'
    values = json.loads((FIXTURES / 'core-producer.json').read_text())
    assert values['scope'] == 'constructors_only_not_validated_restart'
    schema = load_schema('core-state.schema.json')
    validator = schema_validator('core-state.schema.json')
    for value in values['values']:
        validator.evolve(schema={'$ref': core_type_uri(value['type']), '$defs': schema['$defs']}).validate(value)
    assert values['ieee_bits'] == ['0000000000000000', '8000000000000000', '7ff0000000000000',
                                  'fff0000000000000', '7ff8000000000001', '7ff8000000000002']


@pytest.mark.parametrize('value', [{'kind':'symbol','value':''}, {'kind':'symbol','value':'x'}, ''])
def test_core_scalar_preserves_public_symbol_and_string_values(value):
    validator=schema_validator('core-state.schema.json')
    validator.validate({'type':'CoreScalar','fields':{'value':value}})


@pytest.mark.parametrize('value', [{'kind':'symbol','value':None}, {'kind':'symbol','value':0},
                                  {'kind':'string','value':''}, {'kind':'symbol'}])
def test_core_scalar_rejects_malformed_symbol_tags(value):
    assert not schema_validator('core-state.schema.json').is_valid(
        {'type':'CoreScalar','fields':{'value':value}})


def test_actual_constructor_fixture_distinguishes_empty_symbol_and_string():
    values=json.loads((FIXTURES/'core-producer.json').read_text())['values']
    scalars=[value['fields']['value'] for value in values if value['type']=='CoreScalar']
    assert scalars == [{'kind':'symbol','value':''}, {'kind':'symbol','value':'x'}, '']


def test_reflected_fields_match_independent_final_layout_receipt():
    layout = json.loads((PACKAGE / 'core_layout.json').read_text())
    text = (FIXTURES / 'core-fields.txt').read_text()
    owner = None
    expected = {}
    for line in text.splitlines():
        if line and not line.startswith(' ') and not line.startswith('Julia '):
            owner = line; expected[owner] = []
        elif line.startswith('  ') and owner:
            expected[owner].append(line.strip().split('::')[0])
    for name, fields in expected.items():
        actual = layout['graph']['nodes'][name]
        assert [field['name'] for field in actual['fields']] == fields


def test_generated_fields_are_required_including_nullable_members():
    layout = json.loads((PACKAGE / 'core_layout.json').read_text())
    schema = load_schema('core-state.schema.json')
    for name, node in layout['graph']['nodes'].items():
        if node['kind'] == 'struct':
            fields = [field['name'] for field in node['fields']]
            definition = schema['$defs'][name]['properties']['fields']
            assert definition['required'] == fields
            assert definition['additionalProperties'] is False
    values = json.loads((FIXTURES / 'core-producer.json').read_text())
    validator = schema_validator('core-state.schema.json')
    for value in values['values']:
        for name in value['fields']:
            changed = deepcopy(value); del changed['fields'][name]
            assert not validator.is_valid(changed), (value['type'], name)


def test_every_reflected_struct_rejects_each_missing_field():
    graph = json.loads((PACKAGE/'core_layout.json').read_text())['graph']['nodes']
    schema = load_schema('core-state.schema.json')
    validator = schema_validator('core-state.schema.json')
    def sample(name):
        node=graph[name]; kind=node['kind']
        if kind in ('nothing','dynamic'): return None
        if kind == 'bool': return False
        if kind == 'string': return 'manufactured'
        if kind == 'symbol': return {'kind':'symbol','value':'manufactured'}
        if kind == 'integer': return {'kind':'integer','type':node['type'],'decimal':'0'}
        if kind == 'ieee': return {'kind':'ieee','type':node['type'],'bits':'0'*node['digits']}
        if kind == 'complex': return {'kind':'complex','real':sample(node['component']),'imag':sample(node['component'])}
        if kind == 'quantity': return {'kind':'quantity','unit':node['unit'],'value':sample(node['value'])}
        if kind == 'union': return sample(node['variants'][0])
        if kind == 'tuple': return [sample(item) for item in node.get('elements',[])]
        if kind == 'dict': return {'kind':'dict','entries':[]}
        if kind == 'array':
            value=dict(kind='array',eltype=node['eltype'],shape=['0']*node['rank'],order='F')
            if node['storage']=='items': value['values']=[]
            else: value.update(file=dict(path='manufactured.h5',bytes='0',sha256='0'*64,
                 media_type='application/x-hdf5',schema='qcl-negf-checkpoint-v5'),dataset='/empty')
            return value
        if kind == 'struct': return {'type':name,'fields':{field['name']:sample(field['type']) for field in node['fields']}}
        raise AssertionError(kind)
    for name,node in graph.items():
        if node['kind'] != 'struct': continue
        local=validator.evolve(schema={'$ref':core_type_uri(name),'$defs':schema['$defs']})
        value=sample(name)
        assert local.is_valid(value), name
        for field in node['fields']:
            changed=deepcopy(value); del changed['fields'][field['name']]
            assert not local.is_valid(changed), (name,field['name'])


def test_layout_digest_excludes_source_composition_provenance():
    layout = json.loads((PACKAGE / 'core_layout.json').read_text())
    def digest(value):
        return hashlib.sha256(json.dumps(value['graph'], ensure_ascii=False, sort_keys=True,
                                        separators=(',', ':')).encode()).hexdigest()
    assert digest(layout) == layout['layout_sha256']
    changed = deepcopy(layout); changed['producer']['core_revision'] = 'f'*40
    assert digest(changed) == layout['layout_sha256']
    changed['graph']['nodes']['SolverProgress']['fields'].append({'name': 'new', 'type': 'Int64'})
    assert digest(changed) != layout['layout_sha256']


def test_core_schema_meta_and_all_offline_references_are_portable():
    from jsonschema import Draft202012Validator
    schema=load_schema('core-state.schema.json')
    # The same ordinary check runs with the system optional URI checker, without override.
    Draft202012Validator.check_schema(schema)
    def references(value):
        if isinstance(value,dict):
            for key,item in value.items():
                if key=='$ref':yield item
                else:yield from references(item)
        elif isinstance(value,list):
            for item in value:yield from references(item)
    validator=schema_validator('core-state.schema.json')
    for target in references(schema):
        assert validator._resolver.lookup(target).contents is not None


def test_core_array_logical_key_tag_and_reference_spelling_are_distinct_layers():
    schema=load_schema('core-state.schema.json')
    assert 'CoreArray{ComplexF64}' in schema['$defs']
    assert schema['$defs']['CoreArray{ComplexF64}']['properties']['type']=={'const':'CoreArray{ComplexF64}'}
    assert {'$ref':'#/$defs/CoreArray%7BComplexF64%7D'} in schema['$defs']['CoreDatum']['anyOf']
