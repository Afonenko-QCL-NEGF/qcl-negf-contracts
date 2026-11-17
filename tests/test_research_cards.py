"""Independent C1/C2 input literals; source-only, no runtime acceptance."""
from __future__ import annotations

import pytest

from qcl_negf_contracts.messages import ContractError
from qcl_negf_contracts.research_cards import validate_research_card

RAW = b' {"schema":"qcl-negf-research-card-v1","title":" T ","goal":" Goal ","question":" Why? "}\n'
EXPECTED = {
    'schema': 'qcl-negf-research-card-v1', 'title': ' T ',
    'goal': ' Goal ', 'question': ' Why? ',
}


def test_c1_literal_preserves_text_and_whitespace():
    assert validate_research_card(RAW) == EXPECTED
    # Caller storage/native UUID creation is an AiiDA gate, not proven here.
    assert validate_research_card(RAW) == EXPECTED


def test_c1_multibyte_combining_and_supplementary_text():
    payload = RAW.replace(b' Goal ', ' Цель Δ e\u0301 😀 '.encode('utf-8'))
    assert validate_research_card(payload) == {
        'schema': 'qcl-negf-research-card-v1', 'title': ' T ',
        'goal': ' Цель Δ e\u0301 😀 ', 'question': ' Why? ',
    }


@pytest.mark.parametrize('field,old,limit', [
    ('title', b' T ', 128), ('goal', b' Goal ', 16384),
    ('question', b' Why? ', 16384),
], ids=['C1-title-128', 'C1-goal-16384', 'C1-question-16384'])
def test_c1_exact_codepoint_limits(field, old, limit):
    value = 'é' * limit
    expected = dict(EXPECTED)
    expected[field] = value
    assert validate_research_card(RAW.replace(old, value.encode('utf-8'))) == expected


def test_c1_title_limit_counts_supplementary_codepoints():
    assert validate_research_card(RAW.replace(b' T ', '😀'.encode('utf-8') * 128))['title'] == '😀' * 128


def test_c1_exact_raw_byte_limit():
    payload = RAW + b' ' * (65536 - len(RAW))
    assert validate_research_card(payload) == EXPECTED


@pytest.mark.parametrize('field,old,limit', [
    ('title', b' T ', 128), ('goal', b' Goal ', 16384),
    ('question', b' Why? ', 16384),
], ids=['C2-title-129', 'C2-goal-16385', 'C2-question-16385'])
def test_c2_codepoint_limit_plus_one(field, old, limit):
    with pytest.raises(ContractError):
        validate_research_card(RAW.replace(old, ('é' * (limit + 1)).encode('utf-8')))


def test_c2_raw_byte_limit_plus_one():
    with pytest.raises(ContractError):
        validate_research_card(RAW + b' ' * (65537 - len(RAW)))


@pytest.mark.parametrize('payload', [
    None, 'text', 1, True, bytearray(RAW), memoryview(RAW), {}, [],
], ids=['C2-None', 'C2-str', 'C2-int', 'C2-bool', 'C2-bytearray',
        'C2-memoryview', 'C2-dict', 'C2-list'])
def test_c2_only_raw_bytes(payload):
    with pytest.raises(ContractError):
        validate_research_card(payload)


@pytest.mark.parametrize('payload', [
    b'', b' ', b'{', RAW + b'{}', b'null', b'[]', b'false', b'"card"',
    b'{"schema":"qcl-negf-research-card-v1","title":"T","goal":"G"}',
    b'{"schema":"qcl-negf-research-card-v2","title":"T","goal":"G","question":"Q"}',
    b'{"schema":null,"title":"T","goal":"G","question":"Q"}',
    b'{"schema":"qcl-negf-research-card-v1","title":"T","goal":"G","question":"Q","uuid":"11111111-2222-4333-8444-555555555555"}',
    b'{"schema":"qcl-negf-research-card-v1","title":"T","goal":"G","question":"Q","sha256":"abc"}',
    b'{"schema":"qcl-negf-research-card-v1","title":"T","goal":"G","question":"Q","ScientificAssessment":"pass"}',
    b'{"schema":"qcl-negf-research-card-v1","title":"T","goal":"G","question":"Q","title":"T"}',
    b'{"schema":"qcl-negf-research-card-v1","schema":"qcl-negf-research-card-v1","title":"T","goal":"G","question":"Q"}',
    b'{"schema":"qcl-negf-research-card-v1","title":"T","goal":"G","question":"Q","\\u0074itle":"T"}',
], ids=['C2-empty-json', 'C2-space-json', 'C2-truncated', 'C2-trailing-json',
        'C2-null-root', 'C2-array-root', 'C2-bool-root', 'C2-text-root',
        'C2-missing-question', 'C2-schema-version', 'C2-schema-null',
        'C2-surplus-uuid', 'C2-surplus-self-hash', 'C2-surplus-assessment',
        'C2-duplicate-title', 'C2-duplicate-schema', 'C2-escaped-duplicate'])
def test_c2_invalid_envelopes(payload):
    with pytest.raises(ContractError):
        validate_research_card(payload)


@pytest.mark.parametrize('old', [b'" T "', b'" Goal "', b'" Why? "'],
                         ids=['title', 'goal', 'question'])
@pytest.mark.parametrize('bad', [
    b'""', b'" \\t\\n "', '"\u00a0\u2003"'.encode('utf-8'),
    b'null', b'true', b'1', b'[]', b'{}',
    b'"\\ud800"', b'"\\udfff"', b'"\\ud800X"',
    b'NaN', b'Infinity', b'-Infinity', b'1e999',
], ids=['C2-empty-text', 'C2-ascii-whitespace', 'C2-unicode-whitespace',
        'C2-null-text', 'C2-bool-text', 'C2-int-text', 'C2-array-text',
        'C2-object-text', 'C2-high-surrogate', 'C2-low-surrogate',
        'C2-surrogate-followed-text', 'C2-NaN', 'C2-Infinity',
        'C2-negative-Infinity', 'C2-overflow-number'])
def test_c2_invalid_text_values(old, bad):
    with pytest.raises(ContractError):
        validate_research_card(RAW.replace(old, bad))


@pytest.mark.parametrize('payload', [
    b'\xef\xbb\xbf' + RAW,
    RAW.replace(b' Goal ', b'\xff'),
    RAW.replace(b' Goal ', b'\xc0\xaf'),
    RAW.replace(b' Goal ', b'\xed\xa0\x80'),
    RAW.replace(b' Goal ', b'\xf0\x9f\x98'),
], ids=['C2-UTF8-BOM', 'C2-invalid-byte', 'C2-overlong-UTF8',
        'C2-encoded-surrogate', 'C2-truncated-UTF8'])
def test_c2_invalid_utf8(payload):
    with pytest.raises(ContractError):
        validate_research_card(payload)


@pytest.mark.parametrize('encoding,bom', [
    ('utf-16-le', b''), ('utf-16-be', b''),
    ('utf-16-le', b'\xff\xfe'), ('utf-16-be', b'\xfe\xff'),
    ('utf-32-le', b''), ('utf-32-be', b''),
    ('utf-32-le', b'\xff\xfe\x00\x00'), ('utf-32-be', b'\x00\x00\xfe\xff'),
], ids=['C2-UTF16LE', 'C2-UTF16BE', 'C2-UTF16LE-BOM', 'C2-UTF16BE-BOM',
        'C2-UTF32LE', 'C2-UTF32BE', 'C2-UTF32LE-BOM', 'C2-UTF32BE-BOM'])
def test_c2_other_encodings(encoding, bom):
    with pytest.raises(ContractError):
        validate_research_card(bom + RAW.decode('ascii').encode(encoding))


def test_c1_valid_escaped_surrogate_pair():
    assert validate_research_card(RAW.replace(b' T ', b'\\ud83d\\ude00'))['title'] == '😀'
