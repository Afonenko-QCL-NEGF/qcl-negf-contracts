"""Closed outward source declarations; never file, producer or scientific proof.

The caller supplies an explicit root/byte allowance and independently verified
source contexts. Native identities, original plan bytes and transport identities
are distinct. Optical validation here is structural only; its codec is separate.
"""
from __future__ import annotations

from functools import cache

from . import schema_validator
from .artifacts import relative_path
from .messages import ContractError, Object, encode, object_value
from .results import (validate_manifest, validate_checkpoint_declaration,
                      validate_final_diagnostics, validate_final_observations)

_ROOTS = {
    'qcl-negf.native-point-source.v1': 'NativePointSource',
    'qcl-negf-series-result-v4': 'ScientificSeriesResultV4',
    'qcl-negf-current-point-v2': 'CurrentPointV2',
    'qcl-negf-configured-point-result-v2': 'ConfiguredPointResultV2',
    'qcl-negf-configured-point-status-v2': 'ConfiguredPointStatusV2',
}
_LEGACY_SOURCE = ('result_commit', 'full_state', 'analysis_physics', 'optical', 'checkpoint_source_attempt')
_U64_MAX = (1 << 64) - 1


def _require(condition, path, message):
    if not condition:
        raise ContractError(path + ': ' + message, 'corrupt_result')


@cache
def _validator(name):
    return schema_validator('outward-result.schema.json').evolve(schema={
        '$ref': 'https://qcl-negf.invalid/schema/outward-result.schema.json#/$defs/' + name})


def _root(path):
    if path != '.':
        relative_path(path)


def _counter(value, path, *, zero=False):
    _require(type(value) is int and (0 if zero else 1) <= value <= _U64_MAX,
             path, 'exact point counter out of range or wrong type')


def _state_paths(state):
    relative_path(state['manifest']['path'])


def _native_source(source):
    _root(source['artifact_root'])
    state = source['selected_state']
    if state is None:
        return
    _state_paths(state)
    paths = [state['manifest']['path']]
    for name in ('diagnostics', 'observations'):
        if source[name] is not None:
            relative_path(source[name]['path'])
            paths.append(source[name]['path'])
    _require(len(set(paths)) == len(paths), '$.native_source', 'selected immutable paths alias')


def _phase(value):
    if value['status'] == 'available':
        relative_path(value['current_path'])


def _row_source(row, source, *, scientific):
    _native_source(source)
    state = source['selected_state']
    if state is None:
        return
    identity = state['identity']
    point = row['id'] if scientific else row['point_id']
    _require(identity['point_id'] == point, '$.native_source.selected_state', 'source point differs')
    field = 'execution_id' if scientific else 'run_id'
    _require(identity[field] == row[field], '$.native_source.selected_state', 'source owning scope differs')
    original = int(identity['attempt'])
    own = row['attempt']
    if source['relation'] == 'current_point_attempt':
        _require(original == own, '$.native_source.relation', 'native point attempt differs')
    else:
        _require(original < own, '$.native_source.relation', 'retained source must precede point attempt')


def _optical(data, postprocessing, warnings):
    attachment = data['optical_attachment']
    status = postprocessing['optical']
    failed = status['status'] == 'failed'
    _require((status['error'] is not None) == failed, '$.postprocessing.optical', 'status/error differs')
    if failed:
        _require(isinstance(warnings, list) and any(item == 'OPTIONAL_OPTICS_FAILED' or isinstance(item, dict) and
                     item.get('code') == 'OPTIONAL_OPTICS_FAILED' for item in warnings),
                 '$.postprocessing.optical', 'optional failure warning is absent')
    _require((attachment is not None) == (status['status'] == 'completed'),
             '$.optical_attachment', 'optical lifecycle and attachment differ')
    if attachment is None:
        return
    source = data['native_source']
    _require(source['kind'] == 'final', '$.optical_attachment', 'optical source is not a complete final triple')
    original = source['selected_state']
    publication = attachment['publication_state']
    _require(attachment['source_state'] == original, '$.optical_attachment.source_state', 'stationary source differs')
    _require(all(publication[key] == original[key] for key in ('identity', 'state_id', 'state_sequence')),
             '$.optical_attachment.publication_state', 'optical publication changes stationary coordinates')
    _state_paths(publication)
    _require(publication['manifest']['path'] != original['manifest']['path'] and
             publication['manifest']['sha256'] != original['manifest']['sha256'],
             '$.optical_attachment.publication_state', 'separate immutable optical publication required')
    relative_path(attachment['artifact']['path'])
    paths = [original['manifest']['path'], publication['manifest']['path'], attachment['artifact']['path'],
             source['diagnostics']['path'], source['observations']['path']]
    _require(len(set(paths)) == len(paths), '$.optical_attachment', 'immutable optical/source paths alias')
    # Full Mopt inventory/declaration/DAG and native bytes are the optical owner's gate.


def _point(row, operation):
    _counter(row['attempt'], '$.attempt')
    _counter(row['coordinates']['order'], '$.coordinates.order')
    data = row['data']
    source = data['native_source']
    _row_source(row, source, scientific=True)
    _phase(data['phase_source'])
    if source['kind'] != 'absent':
        _require(not any(key in data for key in _LEGACY_SOURCE), '$.data', 'legacy source slots cannot alias native refs')
    if operation == 'stationary':
        _require('result_commit' not in data, '$.data.result_commit', 'stationary v4 requires explicit native source')
        if row['status'] in ('completed', 'completed_with_warnings'):
            _require(source['kind'] == 'final', '$.data.native_source', 'completed stationary point lacks final triple')
    if 'checkpoint_source_attempt' in data:
        _counter(data['checkpoint_source_attempt'], '$.data.checkpoint_source_attempt')
        _require(all(key in data for key in ('result_commit', 'pause_reason', 'resume_kind', 'recovery_origin')),
                 '$.data', 'legacy historical checkpoint provenance absent')
    _optical(data, row['postprocessing'], row['warnings'])
    _require(row['status'] == 'saving' or row['postprocessing']['optical']['status'] not in ('pending', 'running'),
             '$.postprocessing.optical', 'terminal point has unfinished optical publication')


def _series(value):
    for key in ('expected_point_count', 'available_point_count'):
        _counter(value[key], '$.' + key, zero=True)
    _require(value['available_point_count'] == len(value['points']) <= value['expected_point_count'],
             '$.available_point_count', 'point inventory count differs')
    executions = {}
    for execution in value['executions']:
        key = execution['id']
        _counter(execution['repetition'], '$.executions.repetition')
        _require(key not in executions and len(set(execution['point_ids'])) == len(execution['point_ids']),
                 '$.executions', 'duplicate execution/point inventory')
        executions[key] = execution
    if value.get('selected_execution_id') is not None:
        _require(value['selected_execution_id'] in executions, '$.selected_execution_id', 'selected execution absent')
    def point(row):
        execution = executions.get(row['execution_id'])
        _require(execution is not None and row['id'] in execution['point_ids'], '$.points', 'point absent from execution')
        _point(row, execution['operation'])
        return row['execution_id'], row['id']
    selected = {}
    for row in value['points']:
        key = point(row)
        _require(key not in selected, '$.points', 'duplicate selected point')
        selected[key] = row
    previous = {}
    for row in value.get('attempt_history', []):
        key = point(row)
        _require(row['attempt'] > previous.get(key, 0), '$.attempt_history', 'duplicate or nonchronological point attempt')
        previous[key] = row['attempt']
        current = selected.get(key)
        if current is not None:
            _require(row['attempt'] <= current['attempt'], '$.attempt_history', 'history exceeds selected latest point')
            if row['attempt'] == current['attempt']:
                _require(row == current, '$.attempt_history', 'same point attempt differs from selected row')


def validate_outward_result(value: object) -> Object:
    """Check one explicit outward DTO and local joins; read no files/ORM or plans.

    Returns detached finite JSON. A configured phase may have no durable head yet;
    a structural optical edge does not verify its codec or scientific acceptance.
    """
    from jsonschema import ValidationError
    checked = object_value(value, 'outward result')
    schema = checked.get('schema')
    name = _ROOTS.get(schema) if isinstance(schema, str) else None
    if name is None:
        raise ContractError('unsupported outward result version', 'unsupported_format')
    try:
        encode(checked)
        _validator(name).validate(checked)
    except ValidationError as error:
        path = '$' + ''.join(f'[{part}]' if isinstance(part, int) else '.' + part for part in error.absolute_path)
        raise ContractError(path + ': invalid outward field (' + error.validator + ')', 'invalid_input') from error
    except UnicodeError as error:
        raise ContractError('outward result contains invalid UTF-8', 'invalid_input') from error
    if name == 'NativePointSource':
        _native_source(checked)
    elif name == 'ScientificSeriesResultV4':
        _series(checked)
    else:
        _counter(checked['attempt'], '$.attempt', zero=name == 'ConfiguredPointStatusV2')
        scientific = name == 'CurrentPointV2'
        data = checked['result'] if name == 'ConfiguredPointResultV2' else checked
        source = data['native_source']
        _row_source({'id':checked['point_id'], **checked} if scientific else checked, source, scientific=scientific)
        _phase(data['phase_source'])
        if name == 'ConfiguredPointStatusV2' and checked['attempt'] == 0:
            _require(checked['status'] == 'pending' and source['kind'] == 'absent', '$.attempt', 'zero only for pending absent source')
        if not scientific:
            _counter(checked['ordinal'], '$.ordinal')
            adapter = checked['latest_checkpoint']
            if adapter is not None:
                for key in ('generation', 'attempt'):
                    _counter(adapter[key], '$.latest_checkpoint.' + key)
                if adapter['iteration'] is not None:
                    _counter(adapter['iteration'], '$.latest_checkpoint.iteration', zero=True)
        if name == 'ConfiguredPointResultV2':
            _optical(data, data['postprocessing'], data.get('warnings', []))
            _require(data['postprocessing']['optical']['status'] not in ('pending', 'running'),
                     '$.result.postprocessing.optical', 'terminal result has unfinished optical publication')
        elif scientific:
            _root(checked['artifact_root'])
            for key in ('iteration', 'total'):
                if checked.get(key) is not None:
                    _counter(checked[key], '$.' + key, zero=True)
            for metric in checked.get('metrics', []):
                _require(metric['value'] is not None if metric['measurement_status'] == 'measured' else
                         metric['reason'] is not None, '$.metrics', 'measurement value/reason absent')
    return checked


def validate_outward_native_source(value: object, *, manifest: object,
    manifest_ref: object, checkpoint: object,
    diagnostics: object | None = None, observations: object | None = None,
    plan: object | None = None, model: object | None = None,
    parent_manifest: object | None = None,
    parent_checkpoint: object | None = None) -> Object:
    """Join caller-verified immutable native contexts using existing validators.

    No hashes/files/HDF data or numerical criteria are computed. Manifest_ref is
    the independently verified ref for manifest, not a hash certificate made here.
    Transport/canonical-plan binding and optical codec authority remain separate.
    """
    checked = validate_outward_result(value)
    _require(checked['schema'] == 'qcl-negf.native-point-source.v1' and checked['kind'] != 'absent',
             '$', 'selected checkpoint or final source required')
    reference = object_value(manifest_ref, 'manifest reference')
    _require(reference == checked['selected_state']['manifest'], '$.manifest_ref', 'selected full manifest reference differs')
    source = validate_manifest(manifest)
    state = checked['selected_state']
    _require(all(state[key] == source[key] for key in ('identity', 'state_id', 'state_sequence')),
             '$.selected_state', 'selected state differs from manifest')
    terminal = validate_checkpoint_declaration(checkpoint, manifest=source)
    if checked['kind'] == 'checkpoint':
        _require(all(context is None for context in (diagnostics, observations, plan, model, parent_manifest, parent_checkpoint)),
                 '$', 'checkpoint-only source cannot certify extra final contexts')
        return checked
    _require(all(context is not None for context in (diagnostics, observations, plan, model)),
             '$', 'final diagnostics/observations/plan/model contexts required')
    for name in ('convergence', 'physics'):
        _require(source['status'][name] == {'state':'recorded', 'reason':None, 'evidence':checked['observations']},
                 '$.status.' + name, 'recorded final evidence must be exact observations ref')
    validate_final_diagnostics(diagnostics, checkpoint=terminal, manifest=source, artifact_ref=checked['diagnostics'])
    _require(object_value(observations).get('diagnostics') == checked['diagnostics'], '$.diagnostics', 'selected diagnostics ref differs')
    validate_final_observations(observations, checkpoint=terminal, manifest=source,
        artifact_ref=checked['observations'], diagnostics=diagnostics, plan=plan, model=model,
        parent_manifest=parent_manifest, parent_checkpoint=parent_checkpoint)
    return checked
