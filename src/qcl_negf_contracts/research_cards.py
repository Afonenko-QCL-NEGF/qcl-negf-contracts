"""Pure research-card metadata format; no native identity or science checks."""
from __future__ import annotations

import json

from . import messages
from .messages import ContractError

MAX_RESEARCH_CARD_BYTES = 65536
SCHEMA = 'qcl-negf-research-card-v1'
_FIELDS = frozenset({'schema', 'title', 'goal', 'question'})


def validate_research_card(raw: bytes) -> dict:
    """Validate the envelope without normalizing canonical goal/question text.

    Callers storing the card must retain the original validated ``raw`` bytes.
    Native card UUIDs, frozen-plan ownership and scientific acceptance belong
    to consumers; none is established by this pure format check.
    """
    if not isinstance(raw, bytes):
        raise ContractError('research card must be bytes')
    if len(raw) > MAX_RESEARCH_CARD_BYTES:
        raise ContractError('research card exceeds byte budget')
    try:
        text = raw.decode('utf-8', 'strict')
        # STR preflight forbids BOMs and the general decoder's UTF-16/32
        # autodetection. Keep original bytes for strict duplicate/finite checks.
        json.loads(text)
    except (UnicodeError, ValueError, RecursionError) as error:
        raise ContractError('research card must be strict UTF-8 JSON') from error
    card = messages.decode(raw, maximum=MAX_RESEARCH_CARD_BYTES)
    if set(card) != _FIELDS:
        raise ContractError('research card: exact fields required')
    if card['schema'] != SCHEMA:
        raise ContractError('unsupported research card schema')
    for field, maximum in (('title', 128), ('goal', 16384), ('question', 16384)):
        value = card[field]
        if not isinstance(value, str) or not value.strip():
            raise ContractError(f'{field}: nonempty text required')
        try:
            value.encode('utf-8', 'strict')
        except UnicodeError as error:
            raise ContractError(f'{field}: invalid UTF-8 text') from error
        if len(value) > maximum:
            raise ContractError(f'{field}: codepoint budget exceeded')
    return card
