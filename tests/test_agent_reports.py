"""Independent v1 literals; run-view format, not scientific acceptance.

Source-only first freeze. These tests have NOT been collected or executed.
"""
from __future__ import annotations

import copy
import json

import pytest

from qcl_negf_contracts.agent_reports import validate_agent_report
from qcl_negf_contracts.messages import ContractError

# Oracles are author literals, never obtained from validator/schema output.
ANCHOR = {
    'run_uuid': '11111111-2222-4333-8444-555555555555',
    'root_definition_id': 'study.main', 'root_kind': 'study',
    'plan_fingerprint': '0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef',
}
USED = {
    'run_uuid': 'aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee',
    'plan_fingerprint': 'abcdef0123456789abcdef0123456789abcdef0123456789abcdef0123456789',
    'execution_id': 'exec-1', 'definition_id': 'definition_1',
    'variant_id': 'variant.1', 'attempt': 1,
    'calcjob_uuid': '12345678-1234-4234-8234-123456789abc',
}
EXPECTED = {
    'schema': 'qcl-negf-agent-report-v1', 'anchor': ANCHOR,
    'question_snapshot': 'Which assumptions apply?', 'used_runs': [USED],
    'conclusion': 'No scientific acceptance is established.',
    'reasoning': 'The supplied evidence is incomplete.',
    'limitations': 'No canonical card relation is available.',
}
RAW = b''' {
 "schema":"qcl-negf-agent-report-v1",
 "anchor":{"run_uuid":"11111111-2222-4333-8444-555555555555","root_definition_id":"study.main","root_kind":"study","plan_fingerprint":"0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"},
 "question_snapshot":"Which assumptions apply?",
 "used_runs":[{"run_uuid":"aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee","plan_fingerprint":"abcdef0123456789abcdef0123456789abcdef0123456789abcdef0123456789","execution_id":"exec-1","definition_id":"definition_1","variant_id":"variant.1","attempt":1,"calcjob_uuid":"12345678-1234-4234-8234-123456789abc"}],
 "conclusion":"No scientific acceptance is established.",
 "reasoning":"The supplied evidence is incomplete.",
 "limitations":"No canonical card relation is available."
}\n'''
TEXT_FIELDS = ('question_snapshot', 'conclusion', 'reasoning', 'limitations')
TOP_FIELDS = ('schema', 'anchor', 'question_snapshot', 'used_runs',
              'conclusion', 'reasoning', 'limitations')
ANCHOR_FIELDS = ('run_uuid', 'root_definition_id', 'root_kind', 'plan_fingerprint')
USED_FIELDS = ('run_uuid', 'plan_fingerprint', 'execution_id', 'definition_id',
               'variant_id', 'attempt', 'calcjob_uuid')


def raw(document):
    """Input builder only; never an expected-output generator."""
    return json.dumps(document, ensure_ascii=False, separators=(',', ':')).encode('utf-8')


def changed(section, key, value):
    document = copy.deepcopy(EXPECTED)
    target = document if section == 'top' else (
        document['anchor'] if section == 'anchor' else document['used_runs'][0])
    target[key] = value
    return raw(document)


def test_independent_literal_report():
    assert validate_agent_report(RAW) == EXPECTED


def test_empty_used_runs_is_explicitly_valid():
    document = copy.deepcopy(EXPECTED)
    document['used_runs'] = []
    assert validate_agent_report(raw(document)) == document


def test_meta_anchor_is_valid():
    document = copy.deepcopy(EXPECTED)
    document['anchor']['root_kind'] = 'meta'
    assert validate_agent_report(raw(document)) == document


def test_multibyte_utf8_preserves_author_text_without_normalization():
    payload = RAW.replace(b'Which assumptions apply?', 'Вопрос Δ e\u0301 😀'.encode('utf-8'))
    expected = copy.deepcopy(EXPECTED)
    expected['question_snapshot'] = 'Вопрос Δ e\u0301 😀'
    assert validate_agent_report(payload) == expected
    # Literal exact raw may be retained downstream; pure dict API alone cannot prove storage.
    assert payload.startswith(b' {\n') and payload.endswith(b'}\n')
    assert b'\\u' not in payload


@pytest.mark.parametrize('count', [0, 1, 16], ids=['zero', 'one', 'sixteen'])
def test_used_tuple_count_boundary(count):
    document = copy.deepcopy(EXPECTED)
    document['used_runs'] = [{**USED, 'attempt': index + 1} for index in range(count)]
    assert validate_agent_report(raw(document)) == document


def test_seventeen_used_tuples_are_refused():
    document = copy.deepcopy(EXPECTED)
    document['used_runs'] = [{**USED, 'attempt': index + 1} for index in range(17)]
    with pytest.raises(ContractError):
        validate_agent_report(raw(document))


def test_duplicate_complete_used_tuple_is_refused():
    document = copy.deepcopy(EXPECTED)
    document['used_runs'] = [copy.deepcopy(USED), copy.deepcopy(USED)]
    with pytest.raises(ContractError):
        validate_agent_report(raw(document))


@pytest.mark.parametrize('field', USED_FIELDS)
def test_one_changed_tuple_field_is_not_duplicate(field):
    alternatives = {
        'run_uuid': 'bbbbbbbb-cccc-4ddd-8eee-ffffffffffff',
        'plan_fingerprint': '0' * 64, 'execution_id': 'exec-2',
        'definition_id': 'definition_2', 'variant_id': 'variant.2',
        'attempt': 2, 'calcjob_uuid': '23456789-2345-4345-8345-23456789abcd',
    }
    document = copy.deepcopy(EXPECTED)
    document['used_runs'] = [copy.deepcopy(USED), {**USED, field: alternatives[field]}]
    assert validate_agent_report(raw(document)) == document


@pytest.mark.parametrize('section,fields', [('top', TOP_FIELDS), ('anchor', ANCHOR_FIELDS), ('used', USED_FIELDS)])
def test_missing_fields_are_refused(section, fields):
    for field in fields:
        document = copy.deepcopy(EXPECTED)
        target = document if section == 'top' else (
            document['anchor'] if section == 'anchor' else document['used_runs'][0])
        del target[field]
        with pytest.raises(ContractError):
            validate_agent_report(raw(document))


@pytest.mark.parametrize('section', ['top', 'anchor', 'used'])
def test_unknown_field_is_refused(section):
    with pytest.raises(ContractError):
        validate_agent_report(changed(section, 'unexpected', 'x'))


@pytest.mark.parametrize('section,fields', [('top', TOP_FIELDS), ('anchor', ANCHOR_FIELDS), ('used', USED_FIELDS)])
def test_duplicate_json_keys_at_every_level_are_refused(section, fields):
    for field in fields:
        encoded = raw(EXPECTED)
        if section == 'top':
            prefix = b'{'
        elif section == 'anchor':
            prefix = b'"anchor":{'
        else:
            prefix = b'"used_runs":[{'
        # First inserted key duplicates the later literal field, even if values differ.
        encoded = encoded.replace(prefix, prefix + json.dumps(field).encode() + b':null,', 1)
        with pytest.raises(ContractError):
            validate_agent_report(encoded)


@pytest.mark.parametrize('field', TEXT_FIELDS)
@pytest.mark.parametrize('value', ['', None, False, 0, [], {}],
                         ids=['empty', 'null', 'boolean', 'integer', 'array', 'object'])
def test_required_text_is_nonempty_string(field, value):
    with pytest.raises(ContractError):
        validate_agent_report(changed('top', field, value))


@pytest.mark.parametrize('field', TEXT_FIELDS)
@pytest.mark.parametrize('escape', [b'\\ud800', b'\\udfff'], ids=['high', 'low'])
def test_lone_surrogate_in_each_text_is_refused(field, escape):
    document = copy.deepcopy(EXPECTED)
    document[field] = 'SURROGATE_MARKER'
    payload = raw(document).replace(b'SURROGATE_MARKER', escape)
    with pytest.raises(ContractError):
        validate_agent_report(payload)


@pytest.mark.parametrize('section,field', [
    ('anchor', 'root_definition_id'), ('used', 'execution_id'),
    ('used', 'definition_id'), ('used', 'variant_id')])
@pytest.mark.parametrize('value', ['', '_leading', '../x', 'a/b', 'a\n', 'é', 'a' * 129, None])
def test_portable_id_invalid(section, field, value):
    with pytest.raises(ContractError):
        validate_agent_report(changed(section, field, value))


@pytest.mark.parametrize('section,field', [
    ('anchor', 'root_definition_id'), ('used', 'execution_id'),
    ('used', 'definition_id'), ('used', 'variant_id')])
@pytest.mark.parametrize('value', ['A', 'a' * 128, 'A0._-'])
def test_portable_id_valid_boundaries(section, field, value):
    document = copy.deepcopy(EXPECTED)
    target = document['anchor'] if section == 'anchor' else document['used_runs'][0]
    target[field] = value
    assert validate_agent_report(raw(document)) == document


@pytest.mark.parametrize('section,field', [
    ('anchor', 'run_uuid'), ('used', 'run_uuid'), ('used', 'calcjob_uuid')])
@pytest.mark.parametrize('value', ['', 'AAAAAAAA-BBBB-4CCC-8DDD-EEEEEEEEEEEE',
    'aaaaaaaabbbb4ccc8dddeeeeeeeeeeee', '{aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee}',
    'urn:uuid:aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee', 'not-a-uuid', None])
def test_uuid_requires_canonical_full_literal(section, field, value):
    with pytest.raises(ContractError):
        validate_agent_report(changed(section, field, value))


@pytest.mark.parametrize('section', ['anchor', 'used'])
@pytest.mark.parametrize('value', ['A' * 64, 'g' * 64, 'a' * 63, 'a' * 65, '', None, 42])
def test_fingerprint_requires_lowercase_exact64(section, value):
    with pytest.raises(ContractError):
        validate_agent_report(changed(section, 'plan_fingerprint', value))


@pytest.mark.parametrize('value', ['Study', 'execution', '', None, True])
def test_root_kind_requires_study_or_meta(value):
    with pytest.raises(ContractError):
        validate_agent_report(changed('anchor', 'root_kind', value))


@pytest.mark.parametrize('value', [True, False, 0, -1, 1.0, '1', None])
def test_attempt_requires_positive_nonboolean_integer(value):
    with pytest.raises(ContractError):
        validate_agent_report(changed('used', 'attempt', value))


@pytest.mark.parametrize('field,value', [
    ('schema', 'qcl-negf-agent-report-v2'), ('schema', None),
    ('anchor', []), ('anchor', None), ('used_runs', {}),
    ('used_runs', None), ('used_runs', [None]), ('used_runs', [[]])])
def test_envelope_and_collection_types_are_refused(field, value):
    with pytest.raises(ContractError):
        validate_agent_report(changed('top', field, value))


def test_exact_raw_byte_cap_and_plus_one():
    document = copy.deepcopy(EXPECTED)
    document['reasoning'] = ''
    fixed = len(raw(document))
    document['reasoning'] = 'x' * (262144 - fixed)
    payload = raw(document)
    assert len(payload) == 262144
    assert validate_agent_report(payload) == document
    with pytest.raises(ContractError):
        validate_agent_report(payload + b' ')


def test_multibyte_raw_cap_counts_bytes_not_characters():
    document = copy.deepcopy(EXPECTED)
    document['reasoning'] = 'Δ' * 131072
    payload = raw(document)
    assert len(payload) > 262144 and len(payload.decode('utf-8')) < 262144
    with pytest.raises(ContractError):
        validate_agent_report(payload)


@pytest.mark.parametrize('encoding', ['utf-16-le', 'utf-16-be', 'utf-32-le', 'utf-32-be'])
@pytest.mark.parametrize('with_bom', [False, True], ids=['no-bom', 'bom'])
def test_non_utf8_raw_is_refused_even_with_valid_decoded_fields(encoding, with_bom):
    boms = {'utf-16-le': b'\xff\xfe', 'utf-16-be': b'\xfe\xff',
            'utf-32-le': b'\xff\xfe\x00\x00', 'utf-32-be': b'\x00\x00\xfe\xff'}
    payload = (boms[encoding] if with_bom else b'') + RAW.decode('ascii').encode(encoding)
    assert len(payload) < 262144
    with pytest.raises(ContractError):
        validate_agent_report(payload)


@pytest.mark.parametrize('payload', [b'\xef\xbb\xbf' + RAW, b'\xff',
    RAW.replace(b'Which assumptions apply?', b'\xc3\x28'),
    RAW.replace(b'Which assumptions apply?', b'\xed\xa0\x80'),
    b'[]', b'null', b'{', RAW + b'{}'],
    ids=['utf8-bom', 'invalid-leading', 'invalid-continuation', 'utf8-surrogate',
         'array', 'null', 'truncated', 'multiple-documents'])
def test_invalid_raw_json_or_utf8_is_refused(payload):
    with pytest.raises(ContractError):
        validate_agent_report(payload)
