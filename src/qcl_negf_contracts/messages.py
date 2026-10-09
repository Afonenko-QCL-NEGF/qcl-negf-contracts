"""Finite JSON boundaries and scientific plan validation."""
from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from typing import TypeAlias, cast

JSON: TypeAlias = None | bool | int | float | str | list['JSON'] | dict[str, 'JSON']
Object: TypeAlias = dict[str, JSON]
MAX_MESSAGE_BYTES = 8 * 1024 * 1024
MAX_PLAN_BYTES = 64 * 1024 * 1024
TERMINAL = frozenset({'completed', 'completed_with_warnings', 'failed', 'cancelled'})


class ContractError(ValueError):
    def __init__(self, message: str, code: str = 'invalid_input') -> None:
        super().__init__(message)
        self.code = code


def validate_json(value: object, path: str = '$', depth: int = 0) -> JSON:
    if depth > 64:
        raise ContractError(f'{path}: nesting exceeds 64')
    if value is None or isinstance(value, (bool, str, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ContractError(f'{path}: number must be finite')
        return value
    if isinstance(value, list):
        return [validate_json(item, f'{path}[{i}]', depth + 1) for i, item in enumerate(value)]
    if isinstance(value, dict) and all(isinstance(key, str) for key in value):
        return {key: validate_json(item, f'{path}.{key}', depth + 1) for key, item in value.items()}
    raise ContractError(f'{path}: unsupported JSON type')


def object_value(value: object, name: str = 'message') -> Object:
    checked = validate_json(value)
    if not isinstance(checked, dict):
        raise ContractError(f'{name} must be an object')
    return checked


def string(value: Object, key: str) -> str:
    item = value.get(key)
    if not isinstance(item, str) or not item:
        raise ContractError(f'{key} must be a nonempty string')
    return item


def integer(value: Object, key: str, minimum: int = 0) -> int:
    item = value.get(key)
    if isinstance(item, bool) or not isinstance(item, int) or item < minimum:
        raise ContractError(f'{key} must be an integer >= {minimum}')
    return item


def encode(value: Object) -> bytes:
    return json.dumps(validate_json(value), ensure_ascii=False, allow_nan=False,
                      sort_keys=True, separators=(',', ':')).encode('utf-8')


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ContractError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def decode(payload: bytes, maximum: int = MAX_MESSAGE_BYTES) -> Object:
    if len(payload) > maximum:
        raise ContractError('message exceeds byte budget')
    try:
        return object_value(json.loads(payload, object_pairs_hook=_unique_object))
    except (UnicodeError, json.JSONDecodeError, RecursionError) as error:
        raise ContractError('invalid UTF-8 JSON') from error


def fingerprint(value: Object) -> str:
    return hashlib.sha256(encode(value)).hexdigest()


def scientific_plan(value: object) -> Object:
    plan = object_value(value, 'scientific plan')
    if plan.get('schema') != 'qcl-negf-scientific-plan-v2':
        raise ContractError('unsupported scientific plan', 'incompatible_contract')
    for field in ('root_definition_id', 'name', 'fingerprint'):
        string(plan, field)
    if plan.get('root_kind') not in {'study', 'meta'}:
        raise ContractError('invalid root_kind')
    integer(plan, 'computation_count')
    for field in ('inclusions', 'executions', 'points'):
        rows = plan.get(field)
        if not isinstance(rows, list) or not all(isinstance(item, dict) for item in rows):
            raise ContractError(f'plan.{field} must be objects')
        identifiers = [string(cast(Object, item), 'id') for item in rows]
        if len(set(identifiers)) != len(identifiers):
            raise ContractError(f'plan.{field} has duplicate IDs')
    points = cast(list[Object], plan['points'])
    if len(points) != plan['computation_count']:
        raise ContractError('plan computation_count disagrees with points')
    return plan


@dataclass(frozen=True)
class ScientificPointOutcome:
    identifier: str
    execution_id: str
    status: str
    quality: str
    converged: bool

    @classmethod
    def from_json(cls, item: object) -> ScientificPointOutcome:
        value = object_value(item, 'point result')
        converged = value.get('converged')
        if not isinstance(converged, bool):
            raise ContractError('point.converged must be Boolean', 'corrupt_result')
        status = string(value, 'status')
        if status not in {'completed', 'completed_with_warnings', 'failed', 'skipped', 'cancelled', 'paused'}:
            raise ContractError('unknown scientific point status', 'corrupt_result')
        return cls(string(value, 'id'), string(value, 'execution_id'), status,
                   string(value, 'quality'), converged)


_BRANCH_FIELDS = frozenset({
    'code', 'scope', 'reason_kind', 'source_execution_id', 'source_point_id',
    'source_attempt', 'message',
})
_BRANCH_REASONS = frozenset({
    'process_failure', 'iteration_not_converged', 'physical_gate_failed',
    'interrupted', 'data_unavailable', 'assessment_unavailable', 'metadata_invalid',
})
_EXECUTION_PROJECTION = (
    'id', 'definition_id', 'variant_id', 'method_id', 'purpose', 'label',
    'operation', 'point_ids', 'repetition',
)
_COORDINATES = ('temperature_K', 'voltage_per_period_V', 'branch', 'order')


def _branch_require(condition: bool, diagnostic: str) -> None:
    if not condition:
        raise ContractError(f'branch reason: {diagnostic}', 'corrupt_result')


def _branch_id(value: JSON) -> str:
    # ASCII portable ID, without Unicode character-class or anchor surprises.
    alphabet = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789'
    _branch_require(isinstance(value, str) and 1 <= len(value) <= 128
                    and value[0] in alphabet
                    and all(c in alphabet + '._-' for c in value), 'invalid portable ID')
    return cast(str, value)


def _branch_positive(value: JSON) -> int:
    _branch_require(type(value) is int and value >= 1, 'invalid positive integer')
    return cast(int, value)


def _branch_rows(value: JSON, name: str) -> list[Object]:
    _branch_require(isinstance(value, list) and all(isinstance(row, dict) for row in value),
                    f'{name} collection unavailable or invalid')
    return cast(list[Object], value)


def _branch_coordinates(value: Object) -> Object:
    result = {field: value.get(field) for field in _COORDINATES}
    for field, minimum, strict in (('temperature_K', 0, True),
                                   ('voltage_per_period_V', 0, False)):
        number = result[field]
        _branch_require(type(number) in (int, float)
                        and (number > minimum if strict else number >= minimum),
                        'invalid frozen/result coordinates')
    _branch_require(isinstance(result['branch'], str) and bool(result['branch']),
                    'invalid branch coordinate')
    _branch_positive(result['order'])
    return result


def branch_reason(record: object, *, plan: object, owner_point: object,
                  owner_execution: object, source_points: object) -> Object | None:
    """Bind one typed warning to its exact frozen owner and historical source.

    Requires a pinned complete series snapshot including attempt_history.
    A bound reason proves identity/graph consistency, not its physical truth.
    Legacy warnings return None without consulting caller context.
    """
    try:
        warning = object_value(record, 'branch warning')
        encode(warning)  # also reject invalid UTF-8 on legacy inputs
        typed = (warning.get('code') == 'BRANCH_STOPPED'
                 or 'reason_kind' in warning
                 or (warning.get('code') == 'DEPENDENCY_UNAVAILABLE'
                     and any(key in warning for key in
                             ('source_execution_id', 'source_point_id', 'source_attempt'))))
        if not typed:
            return None
        _branch_require(set(warning) == _BRANCH_FIELDS, 'invalid typed warning fields')
        _branch_require(warning['code'] in ('BRANCH_STOPPED', 'DEPENDENCY_UNAVAILABLE')
                        and warning['scope'] == 'branch'
                        and warning['reason_kind'] in _BRANCH_REASONS,
                        'unsupported typed warning literal')
        source_execution = _branch_id(warning['source_execution_id'])
        source_id = _branch_id(warning['source_point_id'])
        source_attempt = _branch_positive(warning['source_attempt'])
        message = warning['message']
        _branch_require(isinstance(message, str) and bool(message)
                        and len(message.encode('utf-8')) <= 2048, 'invalid warning message')

        frozen = object_value(plan, 'frozen plan')
        snapshot = object_value(source_points, 'series snapshot')
        owner = object_value(owner_point, 'owner point')
        execution = object_value(owner_execution, 'owner execution')
        for document in (frozen, snapshot, owner, execution):
            encode(document)
        if (frozen.get('schema') != 'qcl-negf-scientific-plan-v2'
                or frozen.get('model_revision') != 'transport-contract-v2'
                or snapshot.get('schema') != 'qcl-negf-series-result-v3'
                or snapshot.get('contract_set') != 'qcl-negf.results.v1'):
            raise ContractError('branch reason: incompatible frozen plan/result contract',
                                'incompatible_contract')
        _branch_id(frozen.get('root_definition_id'))
        string(frozen, 'name')
        for field in ('fingerprint', 'scientific_fingerprint'):
            digest = frozen.get(field)
            _branch_require(isinstance(digest, str) and len(digest) == 64
                            and all(c in '0123456789abcdefABCDEF' for c in digest),
                            'invalid frozen fingerprint')
        for result_key, plan_key in (
                ('plan_fingerprint', 'fingerprint'),
                ('plan_scientific_fingerprint', 'scientific_fingerprint'),
                ('root_definition_id', 'root_definition_id'), ('name', 'name')):
            _branch_require(snapshot.get(result_key) == frozen[plan_key],
                            'snapshot header identity mismatch')

        executions: dict[str, Object] = {}
        for entry in _branch_rows(frozen.get('executions'), 'plan executions'):
            identifier = _branch_id(entry.get('id'))
            _branch_require(identifier not in executions, 'duplicate frozen execution ID')
            for field in ('definition_id', 'variant_id', 'method_id'):
                _branch_id(entry.get(field))
            for field in ('purpose', 'operation'):
                string(entry, field)
            _branch_require(isinstance(entry.get('label'), str), 'invalid execution label')
            _branch_positive(entry.get('repetition'))
            identifiers = entry.get('point_ids')
            _branch_require(isinstance(identifiers, list) and bool(identifiers),
                            'execution point_ids unavailable')
            ids = [_branch_id(item) for item in cast(list[JSON], identifiers)]
            _branch_require(len(ids) == len(set(ids)), 'duplicate execution point_ids')
            executions[identifier] = entry
        points: dict[str, Object] = {}
        coordinates: dict[str, Object] = {}
        for point in _branch_rows(frozen.get('points'), 'plan points'):
            identifier = _branch_id(point.get('id'))
            execution_id = _branch_id(point.get('execution_id'))
            _branch_require(identifier not in points, 'duplicate frozen point ID')
            _branch_require(execution_id in executions
                            and identifier in executions[execution_id]['point_ids'],
                            'point outside frozen execution')
            _branch_require('predecessor_id' in point, 'predecessor unavailable')
            if point['predecessor_id'] is not None:
                _branch_id(point['predecessor_id'])
            points[identifier] = point
            coordinates[identifier] = _branch_coordinates(point)
        count = frozen.get('computation_count')
        _branch_require(type(count) is int and count == len(points), 'frozen point count mismatch')
        for identifier, entry in executions.items():
            _branch_require(all(point_id in points
                                and points[point_id]['execution_id'] == identifier
                                for point_id in entry['point_ids']),
                            'execution references unavailable/foreign point')

        owner_execution_id = _branch_id(owner.get('execution_id'))
        owner_id = _branch_id(owner.get('id'))
        owner_attempt = _branch_positive(owner.get('attempt'))
        _branch_require(owner_execution_id in executions
                        and encode(execution) == encode(executions[owner_execution_id]),
                        'full owner execution mismatch')
        seen_descriptors: set[str] = set()
        for descriptor in _branch_rows(snapshot.get('executions'), 'result executions'):
            identifier = _branch_id(descriptor.get('id'))
            _branch_require(identifier in executions and identifier not in seen_descriptors,
                            'unknown/duplicate result execution')
            projection = {field: executions[identifier][field] for field in _EXECUTION_PROJECTION}
            _branch_require(encode(descriptor) == encode(projection),
                            'result execution projection mismatch')
            seen_descriptors.add(identifier)
        _branch_require(owner_execution_id in seen_descriptors, 'owner result descriptor unavailable')

        index: dict[tuple[str, str, int], Object] = {}
        rows = (_branch_rows(snapshot.get('points'), 'result points')
                + _branch_rows(snapshot.get('attempt_history'), 'attempt history'))
        for row in rows:
            identifier = _branch_id(row.get('id'))
            execution_id = _branch_id(row.get('execution_id'))
            attempt = _branch_positive(row.get('attempt'))
            _branch_require(identifier in points
                            and points[identifier]['execution_id'] == execution_id,
                            'result point identity mismatch')
            row_coordinates = object_value(row.get('coordinates'), 'result coordinates')
            _branch_require(set(row_coordinates) == set(_COORDINATES)
                            and _branch_coordinates(row_coordinates) == coordinates[identifier],
                            'result coordinates mismatch')
            key = (execution_id, identifier, attempt)
            _branch_require(key not in index or encode(index[key]) == encode(row),
                            'conflicting historical tuple')
            index[key] = row
        owner_key = (owner_execution_id, owner_id, owner_attempt)
        source_key = (source_execution, source_id, source_attempt)
        _branch_require(owner_key in index and encode(index[owner_key]) == encode(owner),
                        'owner row unavailable or substituted')
        warnings = _branch_rows(owner.get('warnings'), 'owner warnings')
        _branch_require(any(encode(item) == encode(warning) for item in warnings),
                        'warning unattached to owner')
        _branch_require(source_key in index, 'exact historical source unavailable')
        _branch_require(source_execution == owner_execution_id
                        and coordinates[source_id]['branch'] == coordinates[owner_id]['branch']
                        and coordinates[source_id]['temperature_K'] == coordinates[owner_id]['temperature_K'],
                        'foreign causal source')
        _branch_require(source_attempt == owner_attempt if source_id == owner_id
                        else source_attempt <= owner_attempt, 'invalid causal attempt')

        # Validate the complete owner path even after encountering the source.
        current = owner_id
        visited: set[str] = set()
        ancestors: set[str] = set()
        for _ in range(len(points)):
            _branch_require(current not in visited, 'cycle in predecessor path')
            visited.add(current)
            predecessor = points[current]['predecessor_id']
            if predecessor is None:
                break
            predecessor = cast(str, predecessor)
            _branch_require(predecessor in points, 'predecessor unavailable')
            previous, following = points[predecessor], points[current]
            _branch_require(previous['execution_id'] == following['execution_id']
                            and coordinates[predecessor]['branch'] == coordinates[current]['branch']
                            and coordinates[predecessor]['temperature_K'] == coordinates[current]['temperature_K']
                            and coordinates[predecessor]['order'] < coordinates[current]['order'],
                            'invalid predecessor edge')
            ancestors.add(predecessor)
            current = predecessor
        else:
            raise ContractError('branch reason: predecessor path exceeds point bound', 'corrupt_result')
        _branch_require(source_id == owner_id or source_id in ancestors,
                        'source is not a declared ancestor')
        return warning
    except ContractError as error:
        if error.code in ('corrupt_result', 'incompatible_contract'):
            raise
        raise ContractError('branch reason: invalid or unavailable JSON provenance',
                            'corrupt_result') from error
    except (KeyError, TypeError, UnicodeError, RecursionError, OverflowError) as error:
        raise ContractError('branch reason: invalid or unavailable JSON provenance',
                            'corrupt_result') from error
