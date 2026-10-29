"""Generated DTO/schema export must refuse drift and unknown schema constructs."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).parents[1]
TOOL = ROOT / 'tools/generate_types.py'


def test_native_generation_tool_exists():
    assert TOOL.is_file(), 'schema/TS generator missing'


def generator():
    spec = importlib.util.spec_from_file_location('qcl_generate_types', TOOL)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


def test_generated_exports_are_current_without_bootstrap():
    result = subprocess.run([sys.executable, str(TOOL), '--check'], capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr


def test_layout_change_changes_required_fields_and_fails_closed():
    module = generator()
    layout = json.loads((ROOT / 'src/qcl_negf_contracts/core_layout.json').read_text())
    original = module.core_schema(layout)
    layout['graph']['nodes']['SolverProgress']['fields'].append({'name':'added_receipt','type':'Int64'})
    updated = module.core_schema(layout)
    assert 'added_receipt' not in original['$defs']['SolverProgress']['properties']['fields']['required']
    assert 'added_receipt' in updated['$defs']['SolverProgress']['properties']['fields']['required']
    layout['graph']['nodes']['Int64']['kind'] = 'arbitrary_function'
    with pytest.raises(ValueError, match='Int64'):
        module.core_schema(layout)


def test_ts_generator_refuses_unknown_schema_keyword():
    module = generator()
    with pytest.raises(ValueError, match='unevaluatedProperties'):
        module.ts_type({'type':'object','unevaluatedProperties':False}, 'test', {})


# Independent literal oracles for URI-fragment encoding AFTER Pointer token escaping.
URI_CASES = [
    ('CoreArray{ComplexF64}', '#/$defs/CoreArray%7BComplexF64%7D', 'Core_CoreArray_ComplexF64_'),
    ('UnicodeЖ', '#/$defs/Unicode%D0%96', 'Core_Unicode_'),
    ('slash/name', '#/$defs/slash~1name', 'Core_slash_name'),
    ('slash~1name', '#/$defs/slash~01name', 'Core_slash_1name'),
    ('tilde~name', '#/$defs/tilde~0name', 'Core_tilde_name'),
    ('tilde~0name', '#/$defs/tilde~00name', 'Core_tilde_0name'),
    ('percent%name', '#/$defs/percent%25name', 'Core_percent_name'),
    ('literal%7B', '#/$defs/literal%257B', 'Core_literal_7B'),
    ('literal{', '#/$defs/literal%7B', 'Core_literal_'),
    ('literal%257B', '#/$defs/literal%25257B', 'Core_literal_257B'),
    ('space key', '#/$defs/space%20key', 'Core_space_key'),
    ('hash#query?', '#/$defs/hash%23query?', 'Core_hash_query_'),
    ('plus+name', '#/$defs/plus+name', 'Core_plus_name'),
]


@pytest.mark.parametrize('logical,uri,alias', URI_CASES)
def test_reference_transport_preserves_logical_pointer_token(logical, uri, alias):
    assert generator().ref(logical) == {'$ref': uri}


def manufactured_documents(module, monkeypatch, definitions, target=None):
    monkeypatch.setattr(module, 'DOCUMENTS', ('core-state.schema.json', 'result-manifest.schema.json'))
    core = {'$schema':'https://json-schema.org/draft/2020-12/schema', '$defs':definitions}
    manifest = {'$schema':core['$schema'], '$ref':('core-state.schema.json'+target if target.startswith('#') else target)} if target else {
        '$schema':core['$schema'], 'type':'object', 'properties':{}, 'required':[], 'additionalProperties':False}
    return {'core-state.schema.json':core, 'result-manifest.schema.json':manifest,
            'model-help.schema.json':{'$schema':core['$schema'], 'type':'null'}}


def test_ts_and_standard_offline_resolver_agree_for_two_ordered_layers(monkeypatch):
    from jsonschema import Draft202012Validator
    from referencing import Registry, Resource
    module=generator()
    definitions={name:{'const':f'sentinel-{i}'} for i,(name,_,_) in enumerate(URI_CASES)}
    docs=manufactured_documents(module,monkeypatch,definitions)
    manifest=docs['result-manifest.schema.json']
    for i,(_,uri,_) in enumerate(URI_CASES):
        manifest['properties'][f'field{i}']={'$ref':'core-state.schema.json'+uri}
    # Equivalent URI spellings must share one logical target/alias, without decoding %7B twice.
    manifest['properties']['same_percent']={'$ref':'core-state.schema.json#/%24defs%2Fliteral%257B'}
    manifest['properties']['same_braces']={'$ref':'core-state.schema.json#/%24defs/CoreArray%7bComplexF64%7d'}
    manifest['required']=list(manifest['properties'])
    exported=module.ts_export(docs)
    for i,(_,_,alias) in enumerate(URI_CASES):
        assert f'export type {alias} = "sentinel-{i}";' in exported.splitlines()
        assert f'"field{i}": {alias}' in exported
    assert exported.count('export type Core_literal_7B =')==1
    assert '"same_percent": Core_literal_7B' in exported
    assert '"same_braces": Core_CoreArray_ComplexF64_' in exported
    base='https://qcl-negf.invalid/schema/'
    registry=Registry()
    for name,doc in docs.items():
        registry=registry.with_resource(base+name,Resource.from_contents(doc))
    for i,(_,uri,_) in enumerate(URI_CASES):
        assert registry.resolver(base+'core-state.schema.json').lookup(uri).contents=={'const':f'sentinel-{i}'}
        assert registry.resolver(base+'result-manifest.schema.json').lookup('core-state.schema.json'+uri).contents=={'const':f'sentinel-{i}'}
    expected={f'field{i}':f'sentinel-{i}' for i in range(len(URI_CASES))}
    expected.update(same_percent='sentinel-7',same_braces='sentinel-0')
    validator=Draft202012Validator(manifest,registry=registry,_resolver=registry.resolver(base+'result-manifest.schema.json'))
    validator.validate(expected)
    wrong=dict(expected,same_percent='sentinel-8')  # literal %7B is NOT the literal brace key
    assert not validator.is_valid(wrong)


def test_ts_export_handles_encoded_actual_core_references_without_alias_drift():
    from urllib.parse import quote
    module=generator()
    docs={name:json.loads((ROOT/'src/qcl_negf_contracts/schemas'/name).read_text()) for name in (*module.DOCUMENTS,'model-help.schema.json')}
    # Baseline raw braces become a valid transport schema; old traversal fails on %7B.
    def encode_refs(value):
        if isinstance(value,dict):
            for key,item in value.items():
                if key=='$ref':
                    file,sep,fragment=item.partition('#')
                    if sep and ('{' in fragment or '}' in fragment):
                        value[key]=file+'#'+quote(fragment,safe="/?:@!$&'()*+,;=")
                else:encode_refs(item)
        elif isinstance(value,list):
            for item in value:encode_refs(item)
    encode_refs(docs['core-state.schema.json'])
    expected=[line for line in (ROOT/'src/qcl_negf_contracts/generated/contracts.ts').read_text().splitlines() if line.startswith('export type ')]
    actual=[line for line in module.ts_export(docs).splitlines() if line.startswith('export type ')]
    assert actual==expected


@pytest.mark.parametrize('key,target', [
    ('raw%', '#/$defs/raw%'),
    ('raw%GG', '#/$defs/raw%GG'),
    ('bad~2', '#/$defs/bad~2'),
    ('raw{T}', '#/$defs/raw{T}'),
    ('Ж', '#/$defs/Ж'),
    ('x', '#/$defs/%FF'),
    ('x', '#named_anchor'),
    ('x', '#%2F%24defs%2Fx'),
    ('x', '#/$defs/missing'),
    ('x', 'https://external.invalid/remote.schema.json#/$defs/x'),
    ('x', '../remote.schema.json#/$defs/x'),
])
def test_generator_fails_closed_for_invalid_or_unprovided_targets(monkeypatch,key,target):
    module=generator()
    docs=manufactured_documents(module,monkeypatch,{key:{'const':'only'}},target)
    with pytest.raises((ValueError,KeyError)):
        module.ts_export(docs)


def test_generator_keeps_alias_collision_gate_after_pointer_decode(monkeypatch):
    module=generator()
    docs=manufactured_documents(module,monkeypatch,{'collision/name':{'const':1},'collision_name':{'const':2}})
    with pytest.raises(ValueError,match='alias collision'):
        module.ts_export(docs)


def test_technical_envelope_exports_are_deep_readonly_and_science_stays_unchanged():
    module = generator()
    documents = {name: json.loads((ROOT/'src/qcl_negf_contracts/schemas'/name).read_text()) for name in module.DOCUMENTS}
    documents['model-help.schema.json'] = json.loads((ROOT/'src/qcl_negf_contracts/schemas/model-help.schema.json').read_text())
    exported = module.ts_export(documents)
    for name in ('TelemetryEnvelope','TelemetryCommit','TelemetryPointer','TelemetrySummary','TelemetrySourceBinding','TelemetryBinding'):
        assert 'export type '+name+' = Telemetry_Readonly<' in exported, name+' missing or mutable'
