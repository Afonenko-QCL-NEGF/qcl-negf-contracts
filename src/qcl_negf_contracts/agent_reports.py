"""Pure UTF-8 agent report envelope; no scientific or run binding checks."""
from __future__ import annotations

import json
import re
from uuid import UUID

from . import messages
from .messages import ContractError

MAX_AGENT_REPORT_BYTES = 262144
MAX_USED_RUNS = 16
SCHEMA = 'qcl-negf-agent-report-v1'
_TOP_FIELDS = frozenset({
    'schema', 'anchor', 'question_snapshot', 'used_runs',
    'conclusion', 'reasoning', 'limitations',
})
_ANCHOR_FIELDS = frozenset({
    'run_uuid', 'root_definition_id', 'root_kind', 'plan_fingerprint',
})
_USED_FIELDS = (
    'run_uuid', 'plan_fingerprint', 'execution_id', 'definition_id',
    'variant_id', 'attempt', 'calcjob_uuid',
)
_IDENTIFIER = re.compile(r'[A-Za-z0-9][A-Za-z0-9._-]{0,127}')
_FINGERPRINT = re.compile(r'[0-9a-f]{64}')


def _object(value: object, fields: frozenset[str], path: str) -> dict:
    if not isinstance(value, dict) or set(value) != fields:
        raise ContractError(f'{path}: exact fields required')
    return value


def _text(value: object, path: str) -> str:
    if not isinstance(value, str) or not value:
        raise ContractError(f'{path}: nonempty text required')
    try:
        value.encode('utf-8', 'strict')
    except UnicodeError as error:
        raise ContractError(f'{path}: invalid UTF-8 text') from error
    return value


def _identifier(value: object, path: str) -> None:
    if _IDENTIFIER.fullmatch(_text(value, path)) is None:
        raise ContractError(f'{path}: invalid portable ID')


def _uuid(value: object, path: str) -> None:
    text = _text(value, path)
    try:
        canonical = str(UUID(text))
    except ValueError as error:
        raise ContractError(f'{path}: invalid UUID') from error
    if canonical != text:
        raise ContractError(f'{path}: canonical full UUID required')


def _fingerprint(value: object, path: str) -> None:
    if _FINGERPRINT.fullmatch(_text(value, path)) is None:
        raise ContractError(f'{path}: lowercase 64-digit fingerprint required')


def validate_agent_report(raw: bytes) -> dict:
    """Return the validated envelope without normalizing author text.

    Callers retaining the file must store the original validated ``raw`` bytes.
    This checks only format, not frozen plans, ORM membership or assessments.
    """
    if not isinstance(raw, bytes):
        raise ContractError('agent report must be bytes')
    if len(raw) > MAX_AGENT_REPORT_BYTES:
        raise ContractError('agent report exceeds byte budget')
    try:
        text = raw.decode('utf-8', 'strict')
        # Parse the STR first: the general bytes decoder autodetects UTF-16/32.
        # This preflight also rejects UTF-8 BOMs; retain raw for duplicate checks.
        json.loads(text)
    except (UnicodeError, ValueError, RecursionError) as error:
        raise ContractError('agent report must be strict UTF-8 JSON') from error
    report = messages.decode(raw, maximum=MAX_AGENT_REPORT_BYTES)
    _object(report, _TOP_FIELDS, 'agent report')
    if report['schema'] != SCHEMA:
        raise ContractError('unsupported agent report schema')
    for field in ('question_snapshot', 'conclusion', 'reasoning', 'limitations'):
        _text(report[field], field)

    anchor = _object(report['anchor'], _ANCHOR_FIELDS, 'anchor')
    _uuid(anchor['run_uuid'], 'anchor.run_uuid')
    _identifier(anchor['root_definition_id'], 'anchor.root_definition_id')
    if _text(anchor['root_kind'], 'anchor.root_kind') not in ('study', 'meta'):
        raise ContractError('anchor.root_kind must be study or meta')
    _fingerprint(anchor['plan_fingerprint'], 'anchor.plan_fingerprint')

    used = report['used_runs']
    if not isinstance(used, list) or len(used) > MAX_USED_RUNS:
        raise ContractError('used_runs must be a list of at most 16 tuples')
    seen: set[tuple] = set()
    for index, item in enumerate(used):
        path = f'used_runs[{index}]'
        row = _object(item, frozenset(_USED_FIELDS), path)
        for field in ('run_uuid', 'calcjob_uuid'):
            _uuid(row[field], f'{path}.{field}')
        _fingerprint(row['plan_fingerprint'], f'{path}.plan_fingerprint')
        for field in ('execution_id', 'definition_id', 'variant_id'):
            _identifier(row[field], f'{path}.{field}')
        if type(row['attempt']) is not int or row['attempt'] < 1:
            raise ContractError(f'{path}.attempt must be a positive nonboolean integer')
        identity = tuple(row[field] for field in _USED_FIELDS)
        if identity in seen:
            raise ContractError(f'{path}: duplicate complete used tuple')
        seen.add(identity)
    return report
