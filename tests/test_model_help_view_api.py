"""Public View boundary over literal inputs and independent DOC07 retained bytes.

The fixture builder supplies manufactured bytes, never a private validator verdict.
These tests assert format/proof behavior, not scientific correctness or target I/O.
"""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
import sys

from jsonschema import ValidationError
import pytest

from qcl_negf_contracts import model_help, schema_validator
from qcl_negf_contracts.messages import ContractError
from test_model_help_bindings import (
    case, no_reference_case, nested_passport_case, origin_capture_conflict_case,
    blob, evidence, unknown_origin,
)


def wire(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')


def unknown_case():
    context = dict(run_uuid='e7f5313d-22fd-49fa-9be5-85fbe29e1974',
                   calcjob_uuid='10dd2a4c-031b-425c-90b8-2f7ea564d313',
                   execution_id='E-1', point_id='P-1', attempt=2,
                   plan_fingerprint='a' * 64, scientific_fingerprint='b' * 64,
                   model_revision='synthetic-ordinary-plan', configuration_hash='c' * 64)
    plan = dict(fingerprint='a' * 64, scientific_fingerprint='b' * 64,
                model_revision='synthetic-ordinary-plan',
                executions=[dict(id='E-1', point_ids=['P-1'])], points=[dict(
                    id='P-1', execution_id='E-1', temperature_K=70.0, voltage_per_period_V=0.05,
                    effective_inputs=dict(configuration_hash='c' * 64,
                        hash_encoding='qcl-negf-canonical-bytes-v1', model_sha256='d' * 64,
                        axes_applied=True, temperature_K=70.0, voltage_per_period_V=0.05))])
    raw = wire(plan)
    document = dict(format='qcl-negf.model-help-view.v1', context=context,
                    binding=dict(status='unknown', reason='source_binding_missing',
                                 release_id='recorded-A', source_revision=None,
                                 release_manifest_sha256=None, bundle_sha256=None),
                    fragment=None, inputs=[],
                    input_status=dict(status='unavailable', reason='inventory_unavailable'))
    retained = dict(selection=dict(context=deepcopy(context), release_id='recorded-A'),
                    metadata=dict(frozen_plan=dict(bytes=raw, sha256=hashlib.sha256(raw).hexdigest())))
    return document, retained


def validate(document, retained):
    validator = getattr(model_help, 'validate_model_help_view', None)
    assert callable(validator), 'public validate_model_help_view is unavailable'
    return validator(document, retained=retained)


def test_ordinary_nested_plan_keeps_recorded_unknown_and_all_caller_inputs(monkeypatch):
    document, retained = unknown_case()
    before = deepcopy((document, retained))
    monkeypatch.setenv('QCL_NEGF_RELEASE_ID', 'current-B')
    assert validate(document, retained) is document
    assert (document, retained) == before
    assert document['binding'] == dict(status='unknown', reason='source_binding_missing',
                                      release_id='recorded-A', source_revision=None,
                                      release_manifest_sha256=None, bundle_sha256=None)
    assert document['fragment'] is None and document['inputs'] == []


def test_historical_bound_view_validates_exact_retained_mapping_without_mutation():
    c = case()
    document, retained = deepcopy(c['view']), deepcopy(c['retained'])
    before = deepcopy((document, retained))
    assert validate(document, retained) is document
    assert (document, retained) == before
    assert document['binding']['status'] == 'bound' and document['binding']['reason'] == 'ok'
    assert document['fragment'] == dict(id='model.ifr', sha256=retained['fragment']['sha256'],
        url='/docs/' + 'a' * 40 + '/help/fragments/model.ifr.json')
    assert document['inputs'][0]['used']['atom'] == dict(kind='quantity', value=0.10, unit='nm')


@pytest.mark.parametrize('other', ['bundle', 'fragment', 'snapshot', 'index'])
def test_other_valid_model_help_formats_cannot_use_the_view_boundary(other):
    c = case()
    with pytest.raises(ContractError):
        validate(c[other], c['retained'])


@pytest.mark.parametrize('change', ['extra', 'missing', 'type', 'boolean_attempt'])
def test_public_c1_precedes_even_corrupt_supplied_c2_bytes(change):
    document, retained = unknown_case()
    if change == 'extra':
        document['caller_checked'] = True
    elif change == 'missing':
        del document['binding']['reason']
    elif change == 'type':
        document['inputs'] = {}
    else:
        document['context']['attempt'] = True
    retained['metadata']['frozen_plan']['sha256'] = '0' * 64
    before = deepcopy((document, retained))
    with pytest.raises(ContractError) as caught:
        validate(document, retained)
    assert isinstance(caught.value.__cause__, ValidationError)
    assert (document, retained) == before


@pytest.mark.parametrize('value', [float('nan'), float('inf'), float('-inf'), (1, 2), {1, 2}, b'bytes'])
def test_nonfinite_and_non_json_values_are_rejected_before_schema_or_c2(value):
    document, retained = unknown_case()
    document['binding']['release_id'] = value
    with pytest.raises(ContractError):
        validate(document, retained)


def test_invalid_unicode_is_a_contract_error_with_the_primary_encoding_cause():
    document, retained = unknown_case()
    document['binding']['release_id'] = '\ud800'
    with pytest.raises(ContractError) as caught:
        validate(document, retained)
    assert isinstance(caught.value.__cause__, UnicodeError)


def sized_case(size):
    document, retained = unknown_case()
    document['binding']['release_id'] = ''
    value = 'x' * (size - len(wire(document)))
    document['binding']['release_id'] = value
    retained['selection']['release_id'] = value
    assert len(wire(document)) == size
    return document, retained


def test_exact_64kib_encoded_view_is_accepted_and_one_extra_byte_is_rejected():
    document, retained = sized_case(65536)
    assert validate(document, retained) is document
    document, retained = sized_case(65537)
    with pytest.raises(ContractError):
        validate(document, retained)


def test_view_budget_counts_utf8_bytes_not_codepoints():
    document, retained = unknown_case()
    document['binding']['release_id'] = '\u0416' * 32768
    retained['selection']['release_id'] = document['binding']['release_id']
    assert len(wire(document).decode('utf-8')) < 65536 < len(wire(document))
    with pytest.raises(ContractError):
        validate(document, retained)


@pytest.mark.parametrize('change', ['selected_attempt', 'selected_child', 'selected_release',
                                    'plan_fingerprint', 'plan_point', 'digest', 'malformed_bytes'])
def test_shape_valid_unknown_never_hides_supplied_context_or_bytes_contradictions(change):
    document, retained = unknown_case()
    if change == 'selected_attempt':
        retained['selection']['context']['attempt'] = 3
    elif change == 'selected_child':
        retained['selection']['context']['calcjob_uuid'] = '20dd2a4c-031b-425c-90b8-2f7ea564d313'
    elif change == 'selected_release':
        retained['selection']['release_id'] = 'recorded-B'
    elif change == 'plan_fingerprint':
        document['context']['plan_fingerprint'] = '0' * 64
        retained['selection']['context']['plan_fingerprint'] = '0' * 64
    elif change == 'plan_point':
        document['context']['point_id'] = 'P-2'
        retained['selection']['context']['point_id'] = 'P-2'
    elif change == 'digest':
        retained['metadata']['frozen_plan']['sha256'] = '0' * 64
    else:
        raw = b'{"duplicate":1,"duplicate":2}'
        retained['metadata']['frozen_plan'] = dict(bytes=raw, sha256=hashlib.sha256(raw).hexdigest())
    before = deepcopy((document, retained))
    with pytest.raises(ContractError) as caught:
        validate(document, retained)
    assert not isinstance(caught.value, model_help.DocumentationProofMissing)
    assert caught.value.code == 'invalid_input'
    assert (document, retained) == before


@pytest.mark.parametrize('missing', ['bundle', 'fragment', 'release_receipt', 'source_review'])
def test_missing_required_bound_proofs_remain_contract_errors_not_public_bundle_missing(missing):
    c = case()
    document, retained = deepcopy(c['view']), deepcopy(c['retained'])
    if missing == 'release_receipt':
        del retained['metadata']['release_receipt']
    elif missing == 'source_review':
        retained['public_reviews'] = ()
    else:
        del retained[missing]
    with pytest.raises(ContractError) as caught:
        validate(document, retained)
    assert not isinstance(caught.value, model_help.DocumentationProofMissing)
    if missing == 'source_review':
        assert caught.value.__cause__ is not None


def test_missing_optional_mapping_keeps_known_identity_scalars_and_independent_snapshot_status():
    c = case()
    document, retained = deepcopy(c['view']), deepcopy(c['retained'])
    del retained['bundle']
    document['binding'].update(status='unavailable', reason='bundle_missing')
    document['fragment'], document['inputs'] = None, []
    before = deepcopy((document, retained))
    assert validate(document, retained) is document
    assert (document, retained) == before
    assert document['input_status'] == dict(status='available', reason='ok')
    for field in ('source_revision', 'release_manifest_sha256', 'bundle_sha256'):
        candidate = deepcopy(document)
        candidate['binding'][field] = None
        with pytest.raises(ContractError):
            validate(candidate, retained)


@pytest.mark.parametrize('change', ['unit', 'phase', 'assignment'])
def test_public_view_checks_units_phase_and_last_assignment_in_existing_c2(change):
    c = case()
    document, retained = deepcopy(c['view']), deepcopy(c['retained'])
    item = document['inputs'][0]
    if change == 'unit':
        item['used']['atom']['unit'] = 'm'
    elif change == 'phase':
        item['used']['evidence'] = deepcopy(item['declared']['evidence'])
    else:
        item['assigning']['rule'] = 'invented-policy'
    with pytest.raises(ContractError):
        validate(document, retained)


@pytest.mark.parametrize('retained', [None, [], 'implicit-reader'])
def test_retained_requires_detached_owner_inputs_not_implicit_capture(retained):
    document, _ = unknown_case()
    with pytest.raises(ContractError):
        validate(document, retained)


def test_public_function_import_does_not_require_optional_validation_runtime():
    source = Path(__file__).resolve().parents[1] / 'src'
    script = '''
import sys
class BlockValidation:
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in {'jsonschema', 'referencing'}:
            raise ModuleNotFoundError('optional validation intentionally unavailable')
sys.meta_path.insert(0, BlockValidation())
sys.path.insert(0, sys.argv[1])
from qcl_negf_contracts.model_help import validate_model_help_view
assert callable(validate_model_help_view)
assert 'jsonschema' not in sys.modules and 'referencing' not in sys.modules
'''
    completed = subprocess.run([sys.executable, '-I', '-B', '-c', script, str(source)],
                               capture_output=True, text=True, timeout=15)
    assert completed.returncode == 0, completed.stdout + completed.stderr


@pytest.mark.parametrize('field,value', [
    ('selection', None), ('selection', []), ('selection', 'implicit-selection'),
    ('metadata', None), ('metadata', []), ('metadata', 'implicit-metadata'),
])
def test_malformed_supplied_retained_mappings_keep_attribute_error_as_primary_cause(field, value):
    document, retained = unknown_case()
    retained[field] = value
    before = deepcopy((document, retained))
    with pytest.raises(ContractError) as caught:
        validate(document, retained)
    assert caught.value.code == 'invalid_input'
    assert isinstance(caught.value.__cause__, AttributeError)
    assert (document, retained) == before


@pytest.mark.parametrize('field', ['sources', 'payload'])
def test_malformed_nested_bound_evidence_maps_cannot_escape_the_public_error_contract(field):
    c = case()
    document, retained = deepcopy(c['view']), deepcopy(c['retained'])
    retained[field] = None
    with pytest.raises(ContractError) as caught:
        validate(document, retained)
    assert caught.value.code == 'invalid_input'
    assert isinstance(caught.value.__cause__, AttributeError)


def test_malformed_selected_graph_cannot_escape_the_public_error_contract():
    document, retained = unknown_case()
    retained['selection']['sources'] = []
    with pytest.raises(ContractError) as caught:
        validate(document, retained)
    assert isinstance(caught.value.__cause__, AttributeError)


@pytest.mark.parametrize('field', ['selection', 'metadata'])
def test_malformed_retained_never_preempts_document_c1(field):
    document, retained = unknown_case()
    document['caller_checked'] = True
    retained[field] = None
    with pytest.raises(ContractError) as caught:
        validate(document, retained)
    assert isinstance(caught.value.__cause__, ValidationError)


def test_encoder_integer_limit_is_normalized_without_changing_global_policy():
    document, retained = unknown_case()
    document['context']['attempt'] = 10 ** 5000
    before_limit = sys.get_int_max_str_digits()
    with pytest.raises(ContractError) as caught:
        validate(document, retained)
    assert caught.value.code == 'invalid_input'
    assert type(caught.value.__cause__) is ValueError
    assert sys.get_int_max_str_digits() == before_limit


def test_retained_json_integer_limit_is_normalized_without_changing_global_policy():
    document, retained = unknown_case()
    raw = b'{"integer":' + b'1' * 5001 + b'}'
    retained['metadata']['frozen_plan'] = dict(bytes=raw, sha256=hashlib.sha256(raw).hexdigest())
    before_limit = sys.get_int_max_str_digits()
    with pytest.raises(ContractError) as caught:
        validate(document, retained)
    assert caught.value.code == 'invalid_input'
    assert type(caught.value.__cause__) is ValueError
    assert sys.get_int_max_str_digits() == before_limit


@pytest.mark.parametrize('helper', ['encode', '_validate_model_help_bindings'])
def test_existing_contract_error_object_code_and_primary_cause_are_preserved(helper, monkeypatch):
    document, retained = unknown_case()
    primary = KeyError('detached owner proof')
    original = ContractError('already classified input failure', code='owning_classification')
    original.__cause__ = primary

    def refuse(*args, **kwargs):
        raise original

    # Inject a preclassified dependency failure to distinguish passthrough from rewrapping.
    # The real public gate order executes; the helper performs no external side effects.
    monkeypatch.setattr(model_help, helper, refuse)
    with pytest.raises(ContractError) as caught:
        validate(document, retained)
    assert caught.value is original
    assert caught.value.code == 'owning_classification'
    assert caught.value.__cause__ is primary


def test_p10_public_bundle_and_view_accept_exact_null_reference_bytes_without_mutation():
    c = no_reference_case()
    before = deepcopy(c)
    assert model_help.validate_documentation_bundle(c["bundle"], retained=c["retained"]) is c["bundle"]
    assert validate(c["view"], c["retained"]) is c["view"]
    assert c == before
    assert c["fragment"]["inputs"][0]["reference_value_origin"] is None
    assert c["view"]["inputs"][0]["used"]["atom"] == dict(kind="quantity", value=0.10, unit="nm")
    assert c["view"]["inputs"][0]["value_origin"]["used"]["reason"] == "origin_not_recorded"


def test_p10_public_view_preserves_trusted_child_and_release_with_local_capture_attempt():
    c = nested_passport_case(local_attempt=7, child_attempt=2, capture=True)
    before = deepcopy(c)
    assert validate(c["view"], c["retained"]) is c["view"]
    assert c == before
    receipt = json.loads(c["retained"]["metadata"]["release_receipt"]["bytes"])
    receipt["context"]["attempt"] = 7
    payload = wire(receipt)
    c["retained"]["metadata"]["release_receipt"] = dict(bytes=payload, sha256=hashlib.sha256(payload).hexdigest())
    with pytest.raises(ContractError, match="another selected child"):
        validate(c["view"], c["retained"])
    c = deepcopy(before)
    c["view"]["context"]["attempt"] = 7
    with pytest.raises(ContractError, match="View context differs"):
        validate(c["view"], c["retained"])


@pytest.mark.parametrize("name", ["snapshot", "index"])
def test_p10_retained_snapshot_and_index_require_their_own_public_c1(name):
    c = nested_passport_case(local_attempt=7, child_attempt=2, capture=True)
    validator = schema_validator("model-help.schema.json")
    # Owners must separately qualify these original documents; View C1 is not their C1.
    validator.validate(c["snapshot"])
    validator.validate(c["index"])
    assert validate(c["view"], c["retained"]) is c["view"]
    broken = deepcopy(c[name])
    if name == "snapshot":
        broken["phase"] = "preview"
    else:
        broken["entries"][0]["attempt"] = True
    with pytest.raises(ValidationError):
        validator.validate(broken)


def test_p10_public_nullable_view_retains_phase_and_exact_leaf_evidence_guards():
    c = no_reference_case()
    assert validate(c["view"], c["retained"]) is c["view"]
    for selector in ("/inputs/0/declared/atom", "/inputs/1/used/atom"):
        candidate = deepcopy(c["view"])
        candidate["inputs"][0]["used"]["evidence"]["selector"] = selector
        with pytest.raises(ContractError, match="exact phase and leaf"):
            validate(candidate, c["retained"])


def test_f1_public_bound_used_origin_cannot_bridge_capture_and_transport_attempts():
    c = origin_capture_conflict_case()
    before = deepcopy(c)
    with pytest.raises(ContractError, match="captured context mismatch"):
        validate(c["view"], c["retained"])
    assert c == before


@pytest.mark.parametrize("explicit_capture", [False, True])
def test_f1_legacy_same_attempt_bound_origin_stays_valid(explicit_capture):
    c = case()
    if explicit_capture:
        c["retained"]["selection"]["capture_context"] = deepcopy(c["snapshot"]["context"])
    c["view"]["inputs"][0]["value_origin"]["used"] = model_help._resolve_value_origin(
        c["reference"], c["claim"], phase="used", retained=c["retained"])
    before = deepcopy(c)
    assert c["view"]["inputs"][0]["value_origin"]["used"]["status"] == "bound"
    assert validate(c["view"], c["retained"]) is c["view"]
    assert c == before


def test_f1_different_capture_attempt_keeps_conservative_unknown_origin_available():
    c = origin_capture_conflict_case()
    c["view"]["inputs"][0]["value_origin"]["used"] = unknown_origin()
    before = deepcopy(c)
    assert validate(c["view"], c["retained"]) is c["view"]
    assert c == before
    assert c["view"]["context"]["attempt"] == 1
    assert c["snapshot"]["context"]["attempt"] == 13


def test_f1_receipt_relabelled_to_capture_cannot_bypass_trusted_child_guard():
    c = origin_capture_conflict_case()
    c["claim"]["assignment_receipt"]["attempt"] = 13
    retained = c["retained"]
    retained["metadata"]["execution_input"] = blob(c["snapshot"])
    retained["metadata"]["value_origin_receipt"] = blob({"claims": [c["claim"]]})
    item = c["view"]["inputs"][0]
    item["used"]["evidence"] = evidence(retained, "execution_input", "/inputs/0/used/atom")
    binding = item["value_origin"]["used"]["binding"]
    for proof in (binding["value"], binding["assignment"], binding["receipt"], *binding["conditions"]):
        proof["sha256"] = retained["metadata"][proof["container"]]["sha256"]
    # The relabelled claim now agrees with Snapshot13, but no new known-origin
    # semantics authorizes replacing the independently trusted child context1.
    assert model_help._validate_model_help_bindings(c["snapshot"], retained=retained) is c["snapshot"]
    with pytest.raises(ContractError, match="selected context mismatch"):
        model_help._resolve_value_origin(c["reference"], c["claim"], phase="used", retained=retained)
    with pytest.raises(ContractError, match="selected context mismatch"):
        validate(c["view"], retained)
