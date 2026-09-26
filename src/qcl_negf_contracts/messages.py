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
