"""Generate the narrow public Core schema and TypeScript resources, without dependencies.

Core field names/types are read exclusively from the runtime-reflected graph. This tool
does not serialize Julia state or decide numerical/scientific validity.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / 'src/qcl_negf_contracts'
ROW_FIELDS = ('domain_revision', 'discretization_id', 'basis_id', 'stage',
              'outer_iteration', 'inner_iteration')
DOCUMENTS = ('result-common.schema.json', 'core-state.schema.json', 'result-manifest.schema.json',
             'result-pointer.schema.json', 'scientific-catalog.schema.json', 'result-cursor.schema.json',
             'checkpoint-declaration.schema.json', 'scientific-record.schema.json',
             'producer-phase-segment.schema.json', 'producer-phase-source.schema.json',
             'final-diagnostics.schema.json')


def obj(properties):
    return dict(type='object', properties=properties, required=list(properties), additionalProperties=False)


def ref(name):
    return {'$ref': '#/$defs/' + name.replace('~', '~0').replace('/', '~1')}


def unsigned_pattern(maximum, *, zero=True):
    """Canonical decimal range using only regular-expression syntax shared by JS/Python."""
    bound = str(maximum)
    alternatives = ['0'] if zero else []
    if len(bound) > 1:
        alternatives.append('[1-9][0-9]{0,'+str(len(bound)-2)+'}')
    for index, char in enumerate(bound):
        lower = 1 if index == 0 else 0
        upper = int(char)-1
        if upper >= lower:
            digit = str(lower) if lower == upper else f'[{lower}-{upper}]'
            alternatives.append(bound[:index]+digit+'[0-9]{'+str(len(bound)-index-1)+'}')
    alternatives.append(bound)
    return '(?:'+'|'.join(alternatives)+')'


def core_schema(layout):
    definitions = {}
    for name, node in layout['graph']['nodes'].items():
        kind = node['kind']
        if kind == 'nothing':
            value = {'type': 'null'}
        elif kind in ('bool', 'string'):
            value = {'type': 'boolean' if kind == 'bool' else 'string'}
        elif kind == 'symbol':
            value = obj(dict(kind={'const': 'symbol'}, value={'type': 'string'}))
        elif kind == 'integer':
            bits = node['bits']
            positive = unsigned_pattern((1 << (bits-1 if node['signed'] else bits))-1)
            negative = '|-'+unsigned_pattern(1 << (bits-1), zero=False) if node['signed'] else ''
            pattern = '^('+positive+negative+r')(?![\s\S])'
            value = obj(dict(kind={'const': 'integer'}, type={'const': node['type']},
                             decimal={'type': 'string', 'pattern': pattern, 'maxLength': 21}))
        elif kind == 'ieee':
            value = obj(dict(kind={'const': 'ieee'}, type={'const': node['type']}, bits={
                'type': 'string', 'pattern': '^[0-9a-f]{'+str(node['digits'])+r'}(?![\s\S])'}))
        elif kind == 'complex':
            value = obj(dict(kind={'const': 'complex'}, real=ref(node['component']), imag=ref(node['component'])))
        elif kind == 'quantity':
            value = obj(dict(kind={'const': 'quantity'}, unit={'const': node['unit']}, value=ref(node['value'])))
        elif kind == 'union':
            value = {'anyOf': [ref(item) for item in node['variants']]}
        elif kind == 'struct':
            value = obj(dict(type={'const': name}, fields=obj({field['name']: ref(field['type']) for field in node['fields']})))
        elif kind == 'tuple':
            if 'elements' in node:
                value = dict(type='array', prefixItems=[ref(item) for item in node['elements']],
                             items=False, minItems=len(node['elements']), maxItems=len(node['elements']))
            else:
                value = dict(type='array', items=ref(node['element']))
        elif kind == 'dict':
            value = obj(dict(kind={'const': 'dict'}, entries={'type': 'array', 'items': obj(
                dict(key=ref(node['key']), value=ref(node['value'])))}))
        elif kind == 'array':
            fields = dict(kind={'const': 'array'}, eltype={'const': node['eltype']},
                          shape=dict(type='array', items={'$ref': 'result-common.schema.json#/$defs/Count'},
                                     minItems=node['rank'], maxItems=node['rank']), order={'const': 'F'})
            if node['storage'] == 'dataset':
                fields.update(file={'$ref': 'result-common.schema.json#/$defs/FileRef'},
                              dataset={'type': 'string', 'minLength': 2, 'pattern': '^/'})
            else:
                fields['values'] = dict(type='array', items=ref(node['element']))
            value = obj(fields)
        elif kind == 'dynamic':
            if node['scope'] != 'SCBAResult.restart_contract':
                raise ValueError(f'Unqualified dynamic Core value: {name}')
            value = ref('RestartValue')
        else:
            raise ValueError(f'Unsupported Core type {name}: {kind}')
        definitions[name] = value

    # A scoped value grammar for the existing untyped restart_contract island, not arbitrary objects.
    definitions['RestartValue'] = {'anyOf': [ref(item) for item in
        ('Nothing', 'Bool', 'String', 'Int64', 'Float64', 'Symbol')] + [obj(dict(
            kind={'const': 'dict'}, entries=dict(type='array', items=obj(dict(
                key=ref('String'), value=ref('RestartValue'))))))]}
    fields = {field['name']: field['type'] for field in layout['graph']['nodes']['ScientificHistorySnapshot']['fields']}
    definitions['ScientificRowKey'] = obj({name: ref(fields[name]) for name in ROW_FIELDS})
    return {'$schema': 'https://json-schema.org/draft/2020-12/schema',
            'title': 'Generated public Core payloads; structural validation only',
            'anyOf': [ref(name) for name in layout['graph']['roots']], '$defs': definitions}


_KEYWORDS = frozenset({'$schema', '$id', '$defs', '$ref', 'title', 'description', 'default',
    'type', 'properties', 'required', 'additionalProperties', 'const', 'enum', 'oneOf', 'anyOf',
    'allOf', 'items', 'prefixItems', 'minItems', 'maxItems', 'uniqueItems', 'pattern', 'minLength',
    'maxLength', 'minimum', 'maximum', 'exclusiveMinimum', 'exclusiveMaximum', 'format'})


def quoted(value):
    return json.dumps(value, ensure_ascii=False, separators=(',', ':'))


def ts_type(schema, source, names):
    if schema is True:
        return 'unknown'
    if schema is False:
        return 'never'
    unknown = set(schema) - _KEYWORDS
    if unknown:
        raise ValueError(f'Unsupported schema keyword at {source}: {sorted(unknown)}')
    if '$ref' in schema:
        target = schema['$ref']
        file, _, fragment = target.partition('#')
        file = file or source
        key = (file, fragment)
        if key not in names:
            raise ValueError(f'Unresolved TS schema reference {file}#{fragment}')
        return names[key]
    if 'const' in schema:
        return quoted(schema['const'])
    if 'enum' in schema:
        return ' | '.join(quoted(item) for item in schema['enum'])
    for key, joiner in (('oneOf', ' | '), ('anyOf', ' | '), ('allOf', ' & ')):
        if key in schema:
            return '(' + joiner.join(ts_type(item, source, names) for item in schema[key]) + ')'
    kind = schema.get('type')
    if isinstance(kind, list):
        return '('+' | '.join(ts_type({**schema, 'type': item}, source, names) for item in kind)+')'
    if kind == 'null':
        return 'null'
    if kind in ('integer', 'number'):
        return 'number'
    if kind == 'boolean':
        return 'boolean'
    if kind == 'string':
        return 'string'
    if kind == 'array':
        if 'prefixItems' in schema:
            return 'readonly ['+', '.join(ts_type(item, source, names) for item in schema['prefixItems'])+']'
        return 'ReadonlyArray<'+ts_type(schema.get('items', True), source, names)+'>'
    if kind == 'object':
        required = schema.get('required', [])
        fields = [quoted(name)+('' if name in required else '?')+': '+ts_type(value, source, names)
                  for name, value in schema.get('properties', {}).items()]
        if schema.get('additionalProperties') not in (False, None):
            fields.append('[key: string]: '+ts_type(schema['additionalProperties'], source, names))
        return '{ '+('; '.join(fields))+' }'
    raise ValueError(f'Unsupported schema construct at {source}: {schema}')


def ts_export(documents):
    names = {}
    used = set()
    def alias(file, fragment):
        if not fragment:
            base = {'result-manifest.schema.json': 'ResultManifest', 'result-pointer.schema.json': 'ResultPointer',
                    'scientific-catalog.schema.json': 'ScientificCatalogPage', 'result-cursor.schema.json': 'ResultCursor',
                    'checkpoint-declaration.schema.json': 'CheckpointDeclaration',
                    'scientific-record.schema.json': 'ScientificRecord',
                    'producer-phase-segment.schema.json': 'ProducerPhaseSegment',
                    'producer-phase-source.schema.json': 'ProducerPhaseSource',
                    'final-diagnostics.schema.json': 'FinalDiagnostics'}.get(file)
            return base
        prefix = ('Core_' if file == 'core-state.schema.json' else
                  'Common_' if file == 'result-common.schema.json' else
                  'Phase_' if file in ('producer-phase-segment.schema.json', 'producer-phase-source.schema.json') else
                  'Final_' if file == 'final-diagnostics.schema.json' else 'Source_')
        return prefix + re.sub('[^A-Za-z0-9_]', '_', fragment.rsplit('/', 1)[-1])
    # Register only references reachable from the result schemas; do not interpret unrelated model-help rules.
    def register(file, fragment=''):
        key = file, fragment
        if key in names:
            return
        name = alias(file, fragment)
        if name is None:
            return
        if name in used:
            raise ValueError('TS alias collision: '+name)
        used.add(name); names[key] = name
        node = documents[file]
        for part in fragment.lstrip('/').split('/') if fragment else ():
            node = node[part.replace('~1', '/').replace('~0', '~')]
        def walk(value):
            if isinstance(value, dict):
                if '$ref' in value:
                    other, _, frag = value['$ref'].partition('#')
                    register(other or file, frag)
                for k, child in value.items():
                    if k != '$defs':
                        walk(child)
            elif isinstance(value, list):
                for child in value:
                    walk(child)
        walk(node)
    for file in DOCUMENTS:
        register(file)
    # Export every reflected type, including nullable variants and recipes not present in the small golden.
    for field in documents['core-state.schema.json']['$defs']:
        register('core-state.schema.json', '/$defs/'+field.replace('~', '~0').replace('/', '~1'))
    lines = ['// Generated from bundled schemas and actual public Core reflection. Do not edit.',
             'export const contractSet = "qcl-negf.results.v2" as const;',
             'export type Phase_Readonly<T> = T extends object ? { readonly [K in keyof T]: Phase_Readonly<T[K]> } : T;']
    for (file, fragment), name in sorted(names.items(), key=lambda item: item[1]):
        node = documents[file]
        for part in fragment.lstrip('/').split('/') if fragment else ():
            node = node[part.replace('~1', '/').replace('~0', '~')]
        value = ts_type(node, file, names)
        # Scope deep immutability to the new producer graph, including shared refs.
        # Existing public scientific aliases retain their published declarations.
        if name.startswith(('Phase_', 'ProducerPhase')):
            value = 'Phase_Readonly<'+value+'>'
        lines.append('export type '+name+' = '+value+';')
    lines.append('export const schemas = '+quoted({name: documents[name] for name in
                 (*DOCUMENTS, 'model-help.schema.json')})+' as const;')
    return '\n'.join(lines)+'\n'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    layout = json.loads((PACKAGE / 'core_layout.json').read_text())
    generated = core_schema(layout)
    documents = {name: json.loads((PACKAGE / 'schemas' / name).read_text()) for name in DOCUMENTS if name != 'core-state.schema.json'}
    documents['core-state.schema.json'] = generated
    documents['model-help.schema.json'] = json.loads((PACKAGE / 'schemas/model-help.schema.json').read_text())
    outputs = {PACKAGE / 'schemas/core-state.schema.json': json.dumps(generated, ensure_ascii=False, indent=2)+'\n',
               PACKAGE / 'generated/contracts.ts': ts_export(documents)}
    for path, payload in outputs.items():
        if args.check:
            if not path.is_file() or path.read_text() != payload:
                raise SystemExit(f'Generated resource differs: {path}')
        else:
            path.parent.mkdir(parents=True, exist_ok=True); path.write_text(payload)
    print('Core schema / TS generation '+('check passed' if args.check else 'complete'))


if __name__ == '__main__':
    main()
