"""Public docs validation uses real C1/C2 and detached synthetic owner proofs.

No source paths are opened and no reviewed source is imported or executed. The
existing independent C2 fixtures supply bytes, not an oracle for API outcomes.
Root presentation/media policy deliberately remains outside this package.
"""
from copy import deepcopy

import pytest

from qcl_negf_contracts import model_help
from qcl_negf_contracts.messages import ContractError
from test_model_help_bindings import (
    COMPONENT, OTHER, actual_graph_docs_case, blob, case, digest, ref,
)


def required_source_case():
    c = case()
    retained = c["retained"]
    sources = retained["sources"]
    refs = []
    # Arbitrary owner paths, not a Root presentation filename allowlist.
    for path, payload in (("docs/src/chart.svg", b"<svg><title>Synthetic</title></svg>"),
                          ("docs/src/table.csv", b"x,y\n1,2\n")):
        sources[(COMPONENT, path)] = {"revision": c["bundle"]["sources"]["components"][1]["revision"],
                                      "bytes": payload}
        reference = ref(sources, path)
        refs.append(reference)
        retained["input_allowlist"] += ((COMPONENT, path),)
        retained["selector_allowlist"] += ((COMPONENT, path, "file", ""),)
        retained["public_reviews"] += ({
            "source": reference,
            "recipe": c["bundle"]["generator"]["recipes"][0],
            "receipt": {"bytes": b"Synthetic independent media review",
                        "sha256": digest(b"Synthetic independent media review")},
        },)
    refs.append(ref(sources, "docs/src/model.md", "anchor", "ifr"))
    return c, refs


def validate(c, required_sources=()):
    return model_help.validate_documentation_bundle(
        c["bundle"], retained=c["retained"], required_sources=required_sources)


def test_public_api_is_available_without_private_evidence_access():
    assert callable(getattr(model_help, "validate_documentation_bundle", None))
    missing = getattr(model_help, "DocumentationProofMissing", None)
    assert isinstance(missing, type) and issubclass(missing, Exception)
    assert not issubclass(missing, ContractError)


@pytest.mark.parametrize("factory", [case, actual_graph_docs_case])
def test_valid_c2_bundle_returns_exact_input_and_preserves_all_caller_data(factory):
    c = factory()
    before = deepcopy(c)
    assert validate(c) is c["bundle"]
    assert c == before


@pytest.mark.parametrize("container", [tuple, list])
def test_all_explicit_media_and_coverage_refs_are_bound_without_target_io(container):
    c, refs = required_source_case()
    before = deepcopy((c, refs))
    assert validate(c, container(refs)) is c["bundle"]
    assert (c, refs) == before


def test_missing_bundle_is_public_missing_with_original_private_cause_chain():
    c = case()
    del c["retained"]["bundle"]
    with pytest.raises(model_help.DocumentationProofMissing) as caught:
        validate(c)
    primary = caught.value.__cause__
    assert isinstance(primary, ContractError)
    assert isinstance(primary.__cause__, model_help._MissingProof)
    assert str(primary.__cause__) == "missing byte record"


@pytest.mark.parametrize("missing", ["bytes", "review", "receipt"])
def test_required_source_missing_proof_has_public_class_and_raw_primary_cause(missing):
    c, refs = required_source_case()
    reference = refs[1]  # Last media item, so checking only the first cannot pass.
    retained = c["retained"]
    if missing == "bytes":
        del retained["sources"][(COMPONENT, reference["path"])]
    elif missing == "review":
        retained["public_reviews"] = tuple(
            row for row in retained["public_reviews"] if row["source"] != reference)
    else:
        review = next(row for row in retained["public_reviews"] if row["source"] == reference)
        review["receipt"] = None
    before = deepcopy((c, refs))
    with pytest.raises(model_help.DocumentationProofMissing) as caught:
        validate(c, refs)
    assert isinstance(caught.value.__cause__, model_help._MissingProof)
    assert (c, refs) == before


@pytest.mark.parametrize("change", ["selected_graph", "bundle_bytes", "source_hash", "payload"])
def test_c2_contradictions_stay_contract_errors_instead_of_missing_or_success(change):
    c = case()
    if change == "selected_graph":
        c["retained"]["selection"]["sources"] = deepcopy(c["bundle"]["sources"])
        c["retained"]["selection"]["sources"]["revision"] = OTHER
    elif change == "bundle_bytes":
        c["retained"]["bundle"]["sha256"] = "e" * 64
    elif change == "source_hash":
        c["bundle"]["schema"]["sha256"] = "e" * 64
        c["retained"]["bundle"] = blob(c["bundle"])
    else:
        c["retained"]["payload"]["research/model.html"]["bytes"] += b"wrong"
    before = deepcopy(c)
    with pytest.raises(ContractError) as caught:
        validate(c)
    assert not isinstance(caught.value.__cause__, model_help._MissingProof)
    assert c == before


@pytest.mark.parametrize("change", ["revision", "hash", "selector", "owner", "allowlist", "receipt"])
def test_required_source_contradictions_cannot_be_hidden_by_a_valid_bundle(change):
    c, refs = required_source_case()
    reference = refs[1]
    retained = c["retained"]
    if change == "revision":
        reference["revision"] = OTHER
    elif change == "hash":
        reference["sha256"] = "e" * 64
    elif change == "selector":
        reference["selector"] = {"kind": "symbol", "value": "not_a_reviewed_symbol"}
    elif change == "owner":
        retained["sources"][(COMPONENT, reference["path"])]["revision"] = OTHER
    elif change == "allowlist":
        retained["input_allowlist"] = tuple(
            row for row in retained["input_allowlist"] if row != (COMPONENT, reference["path"]))
    else:
        review = next(row for row in retained["public_reviews"] if row["source"] == reference)
        review["receipt"]["sha256"] = "e" * 64
    before = deepcopy((c, refs))
    with pytest.raises(ContractError):
        validate(c, refs)
    assert (c, refs) == before


@pytest.mark.parametrize("change", ["extra", "missing", "type", "format"])
def test_c1_is_owned_by_the_public_boundary_not_assumed_of_its_caller(change):
    c = case()
    if change == "extra":
        c["bundle"]["caller_checked"] = True
    elif change == "missing":
        del c["bundle"]["generator"]["uuid"]
    elif change == "type":
        c["bundle"]["files"][0]["bytes"] = True
    else:
        c["bundle"] = c["fragment"]
    c["retained"]["bundle"] = blob(c["bundle"])
    with pytest.raises(ContractError):
        validate(c)


@pytest.mark.parametrize("value", [float("nan"), float("inf"), {1, 2}, (1, 2)])
def test_nonfinite_or_non_json_document_is_not_normalized_into_a_valid_one(value):
    c = case()
    c["bundle"]["generator"]["version"] = value
    with pytest.raises(ContractError):
        validate(c)


@pytest.mark.parametrize("change", ["extra", "missing", "selector", "nonfinite"])
def test_required_sources_receive_finite_closed_publicref_validation(change):
    c, refs = required_source_case()
    reference = refs[1]
    if change == "extra":
        reference["reviewed"] = True
    elif change == "missing":
        del reference["sha256"]
    elif change == "selector":
        reference["selector"]["kind"] = "execute"
    else:
        reference["path"] = float("nan")
    with pytest.raises(ContractError):
        validate(c, refs)


@pytest.mark.parametrize("value", [None, {}, "source", iter(())])
def test_required_sources_require_a_detached_list_or_tuple_not_an_implicit_reader(value):
    with pytest.raises(ContractError):
        validate(case(), value)
