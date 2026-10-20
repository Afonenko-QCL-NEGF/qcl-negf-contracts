"""DOC07 C2 independent synthetic semantic controls, authored from frozen DOC03/D2.

No scientific correctness or production origin capture is asserted by these data.
The private retained layout below is detached owner input, not a serialized API:
selection contains trusted selected child context/requested fragment/release;
sources maps (component, path) to revision+exact bytes; input/output/selector
allowlists are explicit tuples; public_reviews associates exact source+recipe
refs with an opaque retained owning review receipt (bytes+digest). The owning
boundary supplies that association, never an unverified ``reviewed=True``.
metadata maps Evidence.container to bytes+digest; bundle/fragment carry exact
bytes+digest; payload maps logical paths to exact bytes+kind collector facts.
effective_requirements is a PublicRef into selected owning source listing all
applicable causal Evidence locations. selected publication binding is the
release_receipt metadata, not another public manifest/receipt format.

Only these private routine argument names are frozen by these fixtures. Missing
proofs and contradictions follow D2 R2:178 ordering, not truthy status flags.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json

import pytest

from qcl_negf_contracts.messages import ContractError
from qcl_negf_contracts.model_help import (
    _resolve_value_origin,
    _validate_model_help_bindings,
)


ROOT = "a" * 40
OWNER = "b" * 40
OTHER = "c" * 40
COMPONENT = "components/qcl-negf-research"
CONTRACTS = "components/qcl-negf-contracts"
PATH = "physical.interface_roughness_height"
TEMP = "physical.lattice_temperature"
FRAGMENT_ID = "model.ifr"
FRAGMENT_PATH = "help/fragments/model.ifr.json"
FACTS = ("signature", "units", "default", "constraint", "effects", "errors",
         "formula_origin", "value_origin", "assigning_origin", "effective_origin")


def raw(value):
    """Only encode authored synthetic bytes; no production helper is an oracle."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False).encode("utf-8")


def digest(payload):
    return hashlib.sha256(payload).hexdigest()


def blob(value):
    payload = raw(value)
    return {"bytes": payload, "sha256": digest(payload)}


def atom(value=0.10, unit="nm", kind="quantity"):
    return {"kind": kind, "value": value, "unit": unit}


def ref(sources, path, kind="file", value="", component=COMPONENT):
    source = sources[(component, path)]
    return {"component": component, "revision": source["revision"], "path": path,
            "selector": {"kind": kind, "value": value}, "sha256": digest(source["bytes"])}


def evidence(retained, container, selector):
    return {"container": container, "sha256": retained["metadata"][container]["sha256"],
            "selector": selector}


def unknown_origin(reason="origin_not_recorded"):
    return {"status": "unknown", "origin": {"status": "unknown", "kind": "unknown",
            "locators": [], "note": "Synthetic fixture has no complete retained proof."},
            "binding": None, "reason": reason}


def docref():
    return {"section": "research", "path": "model.html", "anchor": "ifr"}


def case(*, reference_status="known", applicability_status="specified",
         locator_uri="https://example.org/paper", extra_payload_path=None, claim_phase="used"):
    """One complete immutable historical A, one selected child, and tiny exact blobs."""
    graph = {"format": "qcl-negf.git-graph.v1", "revision": ROOT, "components": [
        {"path": CONTRACTS, "revision": OWNER, "url": "https://example.org/contracts.git"},
        {"path": COMPONENT, "revision": OWNER, "url": "https://example.org/research.git"}]}
    sources = {
        (CONTRACTS, "src/qcl_negf_contracts/schemas/model-help.schema.json"): {
            "revision": OWNER, "bytes": b'{"type":"object"}'},
        (COMPONENT, "parameters/pilot.json"): {"revision": OWNER, "bytes": raw({
            "height": atom(), "temperature": atom(70.0, "K")})},
        (COMPONENT, "docs/src/model.md"): {"revision": OWNER,
            "bytes": b"# Interface roughness {#ifr}\nEQ-KIFR-001\n"},
        (COMPONENT, "docs/recipe.json"): {"revision": OWNER,
            "bytes": raw({"inputs": ["parameters/pilot.json", "docs/help/value-origins.json",
                                      "docs/src/model.md", "docs/recipe.json", "public/assignment.json",
                                      "docs/help/causal-steps.json"]})},
        (COMPONENT, "public/assignment.json"): {"revision": OWNER,
            "bytes": raw({"height": atom(), "temperature": atom(70.0, "K")})},
        (COMPONENT, "docs/help/causal-steps.json"): {"revision": OWNER, "bytes": raw({
            "required": {PATH: [
                {"container": "frozen_plan", "selector": "/assignment"},
                {"container": "execution_strategy", "selector": "/steps/0"}]}})},
    }
    parameter = ref(sources, "parameters/pilot.json", "json_pointer", "/height")
    statement = ref(sources, "docs/src/model.md", "anchor", "ifr")
    reference = {"id": "pilot.ifr-height", "parameter": parameter, "atom": atom(),
        "applicability": {"status": "specified", "conditions": [{
            "id": "pilot.temperature", "path": TEMP, "relation": "equal",
            "atom": atom(70.0, "K"), "source": statement}], "note": ""},
        "origin": {"status": "known", "kind": "publication", "locators": [{
            "title": "Synthetic public annotation", "uri": locator_uri,
            "location": "Table 1"}], "note": "Synthetic reference, not production attribution."}}
    if reference_status == "not_applicable":
        reference["origin"] = {"status": "not_applicable", "kind": "not_applicable",
                               "locators": [], "note": "Explicit owning inapplicability."}
    if applicability_status == "unknown":
        reference["applicability"].update(status="unknown", note="Owning conditions not specified.")
    sources[(COMPONENT, "docs/help/value-origins.json")] = {
        "revision": OWNER, "bytes": raw({"references": [reference]})}
    annotation = ref(sources, "docs/help/value-origins.json", "json_pointer", "/references/0")
    assigning = ref(sources, "public/assignment.json", "json_pointer", "/height")
    plan = {"point": {"configuration": {PATH: atom(), TEMP: atom(70.0, "K")}},
            "assignment": {"kind": "config_file", "source": assigning, "rule": None}}
    plan_blob = blob(plan)
    context = {"plan_fingerprint": plan_blob["sha256"], "scientific_fingerprint": "d" * 64,
        "model_revision": "synthetic-frozen-model", "execution_id": "E-1", "point_id": "P-1",
        "attempt": 1, "configuration_hash": digest(raw(plan["point"]["configuration"]))}
    receipt = {"source": assigning, "source_sha256": assigning["sha256"],
        "leaf_pointer": "/point/configuration/" + PATH,
        "capture": "retained_public_source_binding", "plan_fingerprint": context["plan_fingerprint"],
        "execution_id": "E-1", "point_id": "P-1", "attempt": 1}
    claim = {"reference_id": reference["id"], "annotation": annotation, "parameter": parameter,
        "phase": claim_phase, "assignment_receipt": receipt, "conditions": [{
            "id": "pilot.temperature", "input_path": TEMP, "phase": claim_phase}]}
    inputs = []
    for path, value in ((PATH, atom()), (TEMP, atom(70.0, "K"))):
        inputs.append({"path": path, "declared": {"status": "known", "atom": value},
            "used": {"status": "known", "atom": value},
            "assigning": {"status": "known", "kind": "config_file", "source": assigning, "rule": None},
            "effective_origin": {"status": "partial", "steps": [
                {"kind": "configuration_merge", "source": assigning, "rule": None},
                {"kind": "execution_strategy", "source": None, "rule": "fixed_strategy"}]}})
    snapshot = {"format": "qcl-negf.model-help-inputs.v1", "context": context,
        "phase": "solver_input", "inputs": inputs, "origin_bindings": [claim]}
    metadata = {"frozen_plan": plan_blob, "execution_input": blob(snapshot),
        "execution_strategy": blob({"steps": [{"kind": "execution_strategy",
                                               "source": None, "rule": "fixed_strategy"}]}),
        "value_origin_receipt": blob({"claims": [claim]})}
    fragment = {"format": "qcl-negf.model-help-fragment.v1", "id": FRAGMENT_ID,
        "source_revision": ROOT, "title": "Interface roughness", "summary": "Synthetic reference context.",
        "scope": "baseline", "meaning_source": statement, "full": docref(), "related": [],
        "equations": [{"id": "EQ-KIFR-001", "doc": docref()}],
        "inputs": [{"path": PATH, "schema_source": parameter,
                    "facts": [{"name": name, "status": "unknown", "text": None,
                               "sources": []} for name in FACTS], "reference_value_origin": reference}],
        "api": [], "assumptions": [], "limitations": []}
    fragment_blob = blob(fragment)
    schema_payload = b'{"synthetic":"selected Contracts resource bytes"}'
    html = b'<!doctype html><h1 id="ifr">Interface roughness</h1><p id="EQ-KIFR-001">Equation</p>'
    recipe = ref(sources, "docs/recipe.json")
    bundle = {"format": "qcl-negf.docs-bundle.v1", "sources": graph,
        "schema": ref(sources, "src/qcl_negf_contracts/schemas/model-help.schema.json", component=CONTRACTS),
        "generator": {"name": "Documenter", "version": "1.17.0",
            "uuid": "e30172f5-a6a5-5a46-863b-614d45cd2de4",
            "git_tree_sha1": "56e9c37b5e7c3b4f080ab1da18d72d5c290e184a", "julia_version": "1.13.0",
            "project_sha256": digest(schema_payload), "manifest_sha256": digest(schema_payload),
            "recipes": [recipe], "toolchain_lock": recipe},
        "fragments": [{"id": FRAGMENT_ID, "file": FRAGMENT_PATH, "sha256": fragment_blob["sha256"]}],
        "files": [{"path": FRAGMENT_PATH, "media_type": "application/json",
                   "bytes": len(fragment_blob["bytes"]), "sha256": fragment_blob["sha256"]},
                  {"path": "research/model.html", "media_type": "text/html",
                   "bytes": len(html), "sha256": digest(html)}],
        "aliases": [{"from": docref(), "to": docref()}]}
    bundle_blob = blob(bundle)
    release_manifest = blob({"format": "qcl-negf.release.v2", "sources": graph, "wheels": []})
    release_id = release_manifest["sha256"]
    api_context = {**context, "run_uuid": "12345678-1234-4234-8234-123456789abc",
                   "calcjob_uuid": "abcdefab-1234-4234-8234-123456789abc"}
    release_receipt = {"context": api_context, "release_id": release_id,
        "release_manifest_sha256": release_manifest["sha256"], "source_revision": ROOT,
        "bundle_sha256": bundle_blob["sha256"]}
    metadata["release_receipt"] = blob(release_receipt)
    retained = {"selection": {"context": api_context, "fragment_id": FRAGMENT_ID,
            "sources": graph, "release_id": release_id}, "sources": sources,
        "input_allowlist": tuple(sources), "output_allowlist": (FRAGMENT_PATH, "research/model.html"),
        "selector_allowlist": tuple([
            (component, path, "file", "") for component, path in sources] + [
            (COMPONENT, "parameters/pilot.json", "json_pointer", "/height"),
            (COMPONENT, "docs/help/value-origins.json", "json_pointer", "/references/0"),
            (COMPONENT, "docs/src/model.md", "anchor", "ifr"),
            (COMPONENT, "public/assignment.json", "json_pointer", "/height"),
            (COMPONENT, "docs/help/causal-steps.json", "json_pointer", "/required")]),
        "public_reviews": tuple({"source": ref(sources, path, component=component), "recipe": recipe,
            "receipt": {"bytes": b"Synthetic owning source review", "sha256": digest(b"Synthetic owning source review")}}
            for component, path in sources),
        "release_manifest": release_manifest, "metadata": metadata,
        "bundle": bundle_blob, "fragment": fragment_blob,
        "payload": {FRAGMENT_PATH: {"bytes": fragment_blob["bytes"], "kind": "file"},
                    "research/model.html": {"bytes": html, "kind": "file"}},
        "effective_requirements": ref(sources, "docs/help/causal-steps.json", "json_pointer", "/required")}
    if extra_payload_path is not None:
        extra = b"Synthetic public payload"
        bundle["files"].append({"path": extra_payload_path, "media_type": "text/plain",
                                "bytes": len(extra), "sha256": digest(extra)})
        retained["payload"][extra_payload_path] = {"bytes": extra, "kind": "file"}
        retained["output_allowlist"] += (extra_payload_path,)
        retained["bundle"] = blob(bundle)
        release_receipt["bundle_sha256"] = retained["bundle"]["sha256"]
        metadata["release_receipt"] = blob(release_receipt)
    used_ev = evidence(retained, "execution_input", "/inputs/0/used/atom")
    declared_ev = evidence(retained, "frozen_plan", "/point/configuration/" + PATH)
    view = {"format": "qcl-negf.model-help-view.v1", "context": api_context,
        "binding": {"status": "bound", "reason": "ok", **{k: release_receipt[k] for k in (
            "release_id", "release_manifest_sha256", "source_revision", "bundle_sha256")}},
        "fragment": {"id": FRAGMENT_ID, "url": "/docs/" + ROOT + "/" + FRAGMENT_PATH,
                     "sha256": fragment_blob["sha256"]},
        "input_status": {"status": "available", "reason": "ok"}, "inputs": [{
            "path": PATH, "declared": {"status": "known", "atom": atom(), "evidence": declared_ev},
            "used": {"status": "known", "atom": atom(), "evidence": used_ev},
            "assigning": {"status": "known", "kind": "config_file", "source": assigning,
                          "rule": None, "evidence": evidence(retained, "frozen_plan", "/assignment")},
            "effective_origin": {"status": "partial", "evidence": [
                evidence(retained, "frozen_plan", "/assignment")]},
            "value_origin": {"declared": unknown_origin(), "used": unknown_origin()}}]}
    index = {"format": "qcl-negf.model-help-index.v1", "complete": True, "entries": [{
        "path": "result/executions/E-1/P-1/attempt-1/model-help-inputs.json",
        "bytes": len(metadata["execution_input"]["bytes"]),
        "sha256": metadata["execution_input"]["sha256"],
        "execution_id": "E-1", "point_id": "P-1", "attempt": 1, "status": "valid", "reason": "ok"}]}
    return {"retained": retained, "bundle": bundle, "fragment": fragment, "snapshot": snapshot, "index": index,
            "view": view, "reference": reference, "claim": claim}


def repack(c, *, reidentify=False):
    """Reissue synthetic docs manifest after an authored mutation, preserving hash controls.

    This does not create any source/assignment/origin proof. It only prevents a
    stale outer manifest hash from masking the semantic case under inspection.
    """
    retained = c["retained"]
    if reidentify:
        # Keep selection.fragment_id unchanged: only the requested identity is
        # contradicted, while the authored replacement is internally consistent.
        replacement_id = c["fragment"]["id"]
        replacement_path = "help/fragments/" + replacement_id + ".json"
        for descriptor in c["bundle"]["fragments"]:
            if descriptor["file"] == FRAGMENT_PATH:
                descriptor.update(id=replacement_id, file=replacement_path)
        for item in c["bundle"]["files"]:
            if item["path"] == FRAGMENT_PATH:
                item["path"] = replacement_path
        retained["payload"][replacement_path] = retained["payload"].pop(FRAGMENT_PATH)
        retained["output_allowlist"] = tuple(
            replacement_path if path == FRAGMENT_PATH else path
            for path in retained["output_allowlist"])
        c["view"]["fragment"].update(id=replacement_id,
            url="/docs/" + ROOT + "/" + replacement_path)
    else:
        replacement_path = FRAGMENT_PATH
    retained["fragment"] = blob(c["fragment"])
    retained["payload"][replacement_path]["bytes"] = retained["fragment"]["bytes"]
    for descriptor in c["bundle"]["fragments"]:
        if descriptor["file"] == replacement_path:
            descriptor["sha256"] = retained["fragment"]["sha256"]
    for item in c["bundle"]["files"]:
        if item["path"] == replacement_path:
            item.update(bytes=len(retained["fragment"]["bytes"]), sha256=retained["fragment"]["sha256"])
    retained["bundle"] = blob(c["bundle"])
    receipt = json.loads(retained["metadata"]["release_receipt"]["bytes"])
    receipt["bundle_sha256"] = retained["bundle"]["sha256"]
    retained["metadata"]["release_receipt"] = blob(receipt)
    c["view"]["binding"]["bundle_sha256"] = retained["bundle"]["sha256"]
    if c["view"]["fragment"] is not None:
        c["view"]["fragment"]["sha256"] = retained["fragment"]["sha256"]


def reauthor_reference(c, *, additional_references=()):
    """Author synthetic annotation+claim+review associations before repacking.

    No production source or receipt is repaired: these are fresh fixture bytes
    with exact associations, so duplicate IDs cannot hide behind a stale hash.
    """
    retained = c["retained"]
    path = "docs/help/value-origins.json"
    retained["sources"][(COMPONENT, path)]["bytes"] = raw({
        "references": [c["reference"], *additional_references]})
    c["claim"]["annotation"] = ref(retained["sources"], path, "json_pointer", "/references/0")
    c["snapshot"]["origin_bindings"] = [c["claim"]]
    retained["metadata"]["execution_input"] = blob(c["snapshot"])
    retained["metadata"]["value_origin_receipt"] = blob({"claims": [c["claim"]]})
    for review in retained["public_reviews"]:
        if (review["source"]["component"], review["source"]["path"]) == (COMPONENT, path):
            review["source"] = ref(retained["sources"], path)
    c["view"]["inputs"][0]["used"]["evidence"] = evidence(
        retained, "execution_input", "/inputs/0/used/atom")
    c["index"]["entries"][0].update(bytes=len(retained["metadata"]["execution_input"]["bytes"]),
        sha256=retained["metadata"]["execution_input"]["sha256"])
    repack(c)


def resolve(c, claim="retained", phase="used"):
    return _resolve_value_origin(c["reference"], c["claim"] if claim == "retained" else claim,
                                 phase=phase, retained=c["retained"])


def validate(c, name="view"):
    document = c[name]
    before = deepcopy(document)
    result = _validate_model_help_bindings(document, retained=c["retained"])
    assert result is document
    assert document == before
    return result


def assert_unknown(result, reason):
    assert set(result) == {"status", "origin", "binding", "reason"}
    assert result["status"] == "unknown"
    assert result["reason"] == reason
    assert result["binding"] is None
    assert result["origin"]["status"] == "unknown"
    assert result["origin"]["kind"] == "unknown"
    assert result["origin"]["locators"] == []
    assert isinstance(result["origin"]["note"], str) and result["origin"]["note"]


def test_exact_historical_mapping_and_return_identity():
    c = case()
    validate(c)
    validate(c, "fragment")
    validate(c, "snapshot")
    validate(c, "bundle")
    validate(c, "index")


def test_origin_complete_retained_proofs_only_branch_bound():
    c = case()
    result = resolve(c)
    assert result["status"] == "bound" and result["reason"] == "ok"
    assert result["origin"] == c["reference"]["origin"]
    binding = result["binding"]
    assert set(binding) == {"reference_id", "annotation", "parameter", "phase", "value",
                            "assignment", "conditions", "receipt"}
    assert binding["phase"] == "used"
    assert binding["reference_id"] == c["reference"]["id"]
    assert binding["annotation"] == c["claim"]["annotation"]
    assert binding["parameter"] == c["claim"]["parameter"]
    assert binding["value"] == evidence(c["retained"], "execution_input", "/inputs/0/used/atom")
    assert binding["assignment"] == evidence(c["retained"], "value_origin_receipt", "/claims/0/assignment_receipt")
    assert binding["receipt"] == evidence(c["retained"], "value_origin_receipt", "/claims/0")
    assert len(binding["conditions"]) == 1
    assert binding["conditions"][0] == evidence(c["retained"], "execution_input", "/inputs/1/used/atom")
    assert binding["conditions"][0]["sha256"] == c["retained"]["metadata"]["execution_input"]["sha256"]


def test_reference_equal_scalar_without_claim_is_not_actual_origin():
    c = case()
    assert_unknown(resolve(c, None), "origin_not_recorded")
    assert c["reference"]["origin"]["status"] == "known"


@pytest.mark.parametrize("missing", ["annotation", "parameter", "graph"])
def test_missing_source_proof_is_unknown_not_false_bound(missing):
    c = case()
    resolve(c)  # Paired complete control.
    if missing == "graph":
        c["retained"]["selection"]["sources"] = None
    else:
        key = (c["claim"][missing]["component"], c["claim"][missing]["path"])
        del c["retained"]["sources"][key]
    assert_unknown(resolve(c, None), "origin_not_recorded")
    assert_unknown(resolve(c), "source_unbound")


def test_missing_last_assignment_proof_is_override_unbound():
    c = case()
    resolve(c)
    del c["retained"]["sources"][(COMPONENT, "public/assignment.json")]
    assert_unknown(resolve(c), "override_unbound")


def test_missing_target_value_precedes_missing_claim():
    c = case()
    resolve(c)
    del c["retained"]["metadata"]["execution_input"]
    assert_unknown(resolve(c, None), "value_unavailable")


def test_unbound_override_precedes_missing_claim_even_when_reference_equal():
    c = case()
    resolve(c)
    c["snapshot"]["inputs"][0]["assigning"] = {
        "status": "unknown", "kind": "unknown", "source": None, "rule": None}
    c["snapshot"]["inputs"][0]["effective_origin"] = {"status": "partial", "steps": [{
        "kind": "checkpoint_restore", "source": None, "rule": "unbound_restore"}]}
    c["retained"]["metadata"]["execution_input"] = blob(c["snapshot"])
    assert_unknown(resolve(c, None), "override_unbound")


@pytest.mark.parametrize("change", [atom(0.15), atom(0.10, "m"), atom(0.10, "nm", "number")])
def test_phase_atom_value_kind_unit_mismatch_is_not_converted(change):
    c = case()
    resolve(c)
    c["snapshot"]["inputs"][0]["used"]["atom"] = change
    c["retained"]["metadata"]["execution_input"] = blob(c["snapshot"])
    assert_unknown(resolve(c, None), "override_unbound")


def test_condition_mismatch_precedes_absent_claim():
    c = case()
    resolve(c)
    c["snapshot"]["inputs"][1]["used"]["atom"] = atom(80.0, "K")
    c["retained"]["metadata"]["execution_input"] = blob(c["snapshot"])
    assert_unknown(resolve(c, None), "conditions_unbound")


def test_missing_condition_does_not_guess_earlier_mismatch():
    c = case()
    resolve(c)
    c["snapshot"]["inputs"] = c["snapshot"]["inputs"][:1]
    c["retained"]["metadata"]["execution_input"] = blob(c["snapshot"])
    assert_unknown(resolve(c, None), "origin_not_recorded")
    assert_unknown(resolve(c), "conditions_unbound")


def test_claim_phase_cannot_transfer_declared_to_used():
    c = case()
    resolve(c)
    declared_claim = deepcopy(c["claim"])
    declared_claim["phase"] = "declared"
    declared_claim["conditions"][0]["phase"] = "declared"
    c["retained"]["metadata"]["value_origin_receipt"] = blob({"claims": [declared_claim]})
    assert_unknown(resolve(c, None, phase="used"), "origin_not_recorded")
    with pytest.raises(ContractError):
        resolve(c, declared_claim, phase="used")


@pytest.mark.parametrize("field,value", [("attempt", 2), ("point_id", "P-2"),
                                         ("execution_id", "E-2"), ("plan_fingerprint", "e" * 64),
                                         ("source_sha256", "e" * 64)])
def test_corrupt_claim_context_is_rejected_before_missing_proofs(field, value):
    c = case()
    resolve(c)
    c["claim"]["assignment_receipt"][field] = value
    with pytest.raises(ContractError):
        resolve(c)


@pytest.mark.parametrize("container", ["execution_input", "frozen_plan", "value_origin_receipt"])
def test_hash_tamper_never_downgrades_to_missing(container):
    c = case()
    resolve(c)
    c["retained"]["metadata"][container]["bytes"] += b" "
    with pytest.raises(ContractError):
        resolve(c)


def test_attempted_bound_view_requires_actual_origin_proof():
    c = case()
    validate(c)
    bound = resolve(c)
    c["view"]["inputs"][0]["value_origin"]["used"] = bound
    validate(c)
    del c["retained"]["metadata"]["value_origin_receipt"]
    with pytest.raises(ContractError):
        validate(c)


def test_documentation_unavailable_preserves_independent_verified_used():
    c = case()
    c["view"]["binding"].update(status="unavailable", reason="bundle_missing")
    c["view"]["fragment"] = None
    validate(c)
    assert c["view"]["inputs"][0]["declared"]["status"] == "known"
    assert c["view"]["inputs"][0]["used"]["status"] == "known"


def test_no_mapping_cannot_fall_back_to_current_or_global_leaf_list():
    c = case()
    c["view"]["binding"].update(status="unknown", reason="source_binding_missing")
    c["view"]["fragment"] = None
    del c["retained"]["fragment"]
    c["view"]["inputs"] = []
    validate(c)
    c["view"]["inputs"] = case()["view"]["inputs"]
    with pytest.raises(ContractError):
        validate(c)


def test_no_snapshot_keeps_declared_from_exact_frozen_point():
    c = case()
    del c["retained"]["metadata"]["execution_input"]
    c["view"]["input_status"] = {"status": "unavailable", "reason": "snapshot_missing"}
    c["view"]["inputs"][0]["used"] = {"status": "unknown", "atom": None, "evidence": None}
    validate(c)
    c["view"]["inputs"][0]["used"] = case()["view"]["inputs"][0]["used"]
    with pytest.raises(ContractError):
        validate(c)


@pytest.mark.parametrize("field,value", [("attempt", 2), ("point_id", "P-2"),
    ("execution_id", "E-2"), ("configuration_hash", "e" * 64),
    ("calcjob_uuid", "ffffffff-1234-4234-8234-123456789abc"),
    ("run_uuid", "ffffffff-1234-4234-8234-123456789abc")])
def test_view_context_is_one_selected_child(field, value):
    c = case()
    validate(c)
    c["view"]["context"][field] = value
    with pytest.raises(ContractError):
        validate(c)


@pytest.mark.parametrize("part", ["bundle", "fragment"])
def test_mapping_blob_hash_is_checked(part):
    c = case()
    validate(c)
    c["retained"][part]["bytes"] += b" "
    with pytest.raises(ContractError):
        validate(c)


@pytest.mark.parametrize("part,field,value", [
    ("fragment", "id", "model.other"), ("fragment", "source_revision", OTHER)])
def test_retained_mapping_id_and_revision_are_exact(part, field, value):
    c = case()
    validate(c)
    c[part][field] = value
    repack(c, reidentify=(field == "id"))
    with pytest.raises(ContractError):
        validate(c)


def test_same_label_and_numbers_do_not_make_graph_B_historical_A():
    c = case()
    validate(c)
    c["retained"]["selection"]["sources"]["revision"] = OTHER
    with pytest.raises(ContractError):
        validate(c)


@pytest.mark.parametrize("where", ["inputs", "conditions", "fragments", "files", "components"])
def test_keyed_collisions_do_not_become_first_match(where):
    c = case()
    validate(c)
    if where == "inputs":
        c["fragment"]["inputs"].append(deepcopy(c["fragment"]["inputs"][0]))
        c["retained"]["fragment"] = blob(c["fragment"])
    elif where == "conditions":
        conditions = c["reference"]["applicability"]["conditions"]
        conditions.append(deepcopy(conditions[0]))
        c["claim"]["conditions"].append(deepcopy(c["claim"]["conditions"][0]))
        reauthor_reference(c)
    elif where == "components":
        c["bundle"]["sources"]["components"].append(deepcopy(c["bundle"]["sources"]["components"][0]))
        c["retained"]["bundle"] = blob(c["bundle"])
    else:
        c["bundle"][where].append(deepcopy(c["bundle"][where][0]))
        c["retained"]["bundle"] = blob(c["bundle"])
    repack(c)
    with pytest.raises(ContractError):
        if where == "conditions":
            resolve(c)
        else:
            validate(c)


@pytest.mark.parametrize("unsafe", ["../private.json", "/private.json", "x/../private.json",
    "x\\private.json", ".git/config", "x/.aws/key", "x/%2e%2e/private.json", "x/%252e%252e/private.json",
    "x/secret\x00.json", "x/secret\n.json"])
def test_public_payload_paths_are_not_silently_normalized(unsafe):
    validate(case(), "bundle")
    c = case(extra_payload_path=unsafe)
    with pytest.raises(ContractError):
        validate(c, "bundle")


def test_source_path_allowlist_is_exact_not_basename_heuristic():
    c = case()
    validate(c, "fragment")
    c["fragment"]["meaning_source"]["path"] = "private/model.md"
    with pytest.raises(ContractError):
        validate(c, "fragment")


@pytest.mark.parametrize("uri", ["https://example.org/paper?", "https://example.org/paper?x=1",
    "https://u:p@example.org/paper", "https://example.org/paper\n", "http://example.org/paper",
    "file:///private/paper", "javascript:alert(1)", "https:paper"])
def test_public_locator_parser_rejects_queries_credentials_and_controls(uri):
    validate(case(), "fragment")
    c = case(locator_uri=uri)
    before = deepcopy(c["fragment"])
    with pytest.raises(ContractError):
        validate(c, "fragment")
    assert c["fragment"] == before  # No query stripping/repair.


def test_query_free_locator_still_requires_owning_public_source_review():
    c = case()
    validate(c, "fragment")
    c["retained"]["public_reviews"] = ()
    with pytest.raises(ContractError):
        validate(c, "fragment")


def test_missing_alias_anchor_or_symlink_is_not_public_ready():
    for mutation in ("anchor", "symlink", "blob"):
        c = case()
        validate(c, "bundle")
        if mutation == "anchor":
            c["bundle"]["aliases"][0]["to"]["anchor"] = "missing"
        elif mutation == "symlink":
            c["retained"]["payload"]["research/model.html"]["kind"] = "symlink"
        else:
            c["retained"]["payload"]["research/model.html"]["bytes"] += b"tamper"
        repack(c)
        with pytest.raises(ContractError):
            validate(c, "bundle")


def test_known_effective_origin_requires_full_owning_chain_not_nonempty_evidence():
    c = case()
    validate(c)
    effective = c["view"]["inputs"][0]["effective_origin"]
    effective["status"] = "known"
    effective["evidence"].append(evidence(c["retained"], "execution_strategy", "/steps/0"))
    validate(c)
    effective["evidence"].pop()
    with pytest.raises(ContractError):
        validate(c)


def test_known_effective_origin_cannot_invent_complete_step_universe():
    c = case()
    effective = c["view"]["inputs"][0]["effective_origin"]
    effective["status"] = "known"
    effective["evidence"].append(evidence(c["retained"], "execution_strategy", "/steps/0"))
    validate(c)
    del c["retained"]["effective_requirements"]
    with pytest.raises(ContractError):
        validate(c)


def test_evidence_selector_and_hash_must_address_the_actual_scalar():
    for mutation in ("selector", "sha256", "atom"):
        c = case()
        validate(c)
        state = c["view"]["inputs"][0]["used"]
        if mutation == "selector":
            state["evidence"]["selector"] = "/inputs/1/used/atom"
        elif mutation == "sha256":
            state["evidence"]["sha256"] = "e" * 64
        else:
            state["atom"] = atom(0.15)
        with pytest.raises(ContractError):
            validate(c)


def test_explicit_owning_inapplicability_precedes_absent_value_and_claim():
    c = case(reference_status="not_applicable")
    del c["retained"]["metadata"]["execution_input"]
    result = resolve(c, None)
    assert result == {"status": "not_applicable", "origin": c["reference"]["origin"],
                      "binding": None, "reason": "not_applicable"}


def test_unknown_applicability_never_becomes_bound_from_equal_numbers():
    c = case(applicability_status="unknown")
    assert_unknown(resolve(c), "conditions_unbound")


@pytest.mark.parametrize("mutation", ["path", "point", "attempt", "sha256", "bytes", "duplicate"])
def test_index_identity_hash_size_and_unique_paths(mutation):
    c = case()
    validate(c, "index")
    entry = c["index"]["entries"][0]
    if mutation == "path":
        entry["path"] = "result/executions/E-1/P-2/attempt-1/model-help-inputs.json"
    elif mutation == "point":
        entry["point_id"] = "P-2"
    elif mutation == "attempt":
        entry["attempt"] = 2
    elif mutation == "sha256":
        entry["sha256"] = "e" * 64
    elif mutation == "bytes":
        entry["bytes"] += 1
    else:
        c["index"]["entries"].append(deepcopy(entry))
    with pytest.raises(ContractError):
        validate(c, "index")


def test_exact_input_path_slice_rejects_a_different_valid_snapshot_leaf():
    c = case()
    validate(c)
    temperature_reference = deepcopy(c["reference"])
    temperature_reference.update(id="pilot.temperature", atom=atom(70.0, "K"),
        parameter=ref(c["retained"]["sources"], "parameters/pilot.json", "json_pointer", "/temperature"))
    temperature_mapping = deepcopy(c["fragment"]["inputs"][0])
    temperature_mapping.update(path=TEMP, schema_source=temperature_reference["parameter"],
                               reference_value_origin=temperature_reference)
    c["fragment"]["inputs"].append(temperature_mapping)
    c["retained"]["selector_allowlist"] += (
        (COMPONENT, "parameters/pilot.json", "json_pointer", "/temperature"),
        (COMPONENT, "docs/help/value-origins.json", "json_pointer", "/references/1"))
    reauthor_reference(c, additional_references=(temperature_reference,))
    temperature_input = {"path": TEMP,
        "declared": {"status": "known", "atom": atom(70.0, "K"),
            "evidence": evidence(c["retained"], "frozen_plan", "/point/configuration/" + TEMP)},
        "used": {"status": "known", "atom": atom(70.0, "K"),
            "evidence": evidence(c["retained"], "execution_input", "/inputs/1/used/atom")},
        "assigning": {"status": "unknown", "kind": "unknown", "source": None,
                      "rule": None, "evidence": None},
        "effective_origin": {"status": "unknown", "evidence": []},
        "value_origin": {"declared": unknown_origin(), "used": unknown_origin()}}
    c["view"]["inputs"] = [temperature_input]
    validate(c)  # Exact TEMP Atom/Evidence and selected mapping are healthy.
    c["fragment"]["inputs"].pop()  # Only semantic change: remove TEMP mapping.
    repack(c)
    with pytest.raises(ContractError):
        validate(c)


def test_public_source_revision_and_selector_proofs_are_not_file_name_matches():
    for mutation in ("revision", "sha256", "selector"):
        c = case()
        validate(c, "fragment")
        source = c["fragment"]["meaning_source"]
        if mutation == "selector":
            source["selector"]["value"] = "missing-anchor"
        else:
            source[mutation] = OTHER if mutation == "revision" else "e" * 64
        repack(c)
        with pytest.raises(ContractError):
            validate(c, "fragment")


def test_bound_documentation_cannot_be_claimed_without_retained_release_receipt():
    c = case()
    validate(c)
    del c["retained"]["metadata"]["release_receipt"]
    with pytest.raises(ContractError):
        validate(c)


def test_missing_bundle_mapping_is_empty_even_with_valid_selected_snapshot():
    c = case()
    validate(c)
    del c["retained"]["bundle"]
    c["view"]["binding"].update(status="unavailable", reason="bundle_missing")
    c["view"]["fragment"] = None
    c["view"]["inputs"] = []
    validate(c)
    assert c["view"]["input_status"] == {"status": "available", "reason": "ok"}
    c["view"]["inputs"] = case()["view"]["inputs"]
    with pytest.raises(ContractError):
        validate(c)


@pytest.mark.parametrize("mutation", ["missing_one", "source", "revision", "recipe", "receipt_bytes"])
def test_review_association_must_match_exact_source_recipe_and_receipt_digest(mutation):
    c = case()
    validate(c, "fragment")
    target_path = "parameters/pilot.json"
    reviews = list(deepcopy(c["retained"]["public_reviews"]))
    position = next(i for i, row in enumerate(reviews)
                    if row["source"]["component"] == COMPONENT and row["source"]["path"] == target_path)
    if mutation == "missing_one":
        reviews.pop(position)
    elif mutation == "source":
        reviews[position]["source"] = ref(c["retained"]["sources"], "docs/src/model.md")
        # Preserve one exact review for model.md rather than introducing an
        # unrelated duplicate-key witness; only pilot.json loses association.
        reviews = [row for i, row in enumerate(reviews) if i == position or
                   not (row["source"]["component"] == COMPONENT and
                        row["source"]["path"] == "docs/src/model.md")]
    elif mutation == "revision":
        reviews[position]["source"]["revision"] = OTHER
    elif mutation == "recipe":
        reviews[position]["recipe"] = ref(c["retained"]["sources"], "public/assignment.json")
    else:
        reviews[position]["receipt"]["bytes"] += b" changed"
    # Other exact owning reviews remain: tuple truthiness is insufficient.
    assert reviews
    c["retained"]["public_reviews"] = tuple(reviews)
    with pytest.raises(ContractError):
        validate(c, "fragment")


@pytest.mark.parametrize("replacement", ["duplicate", "unrelated_existing_selector"])
def test_known_chain_requires_exact_steps_at_same_evidence_cardinality(replacement):
    c = case()
    effective = c["view"]["inputs"][0]["effective_origin"]
    effective["status"] = "known"
    effective["evidence"].append(evidence(c["retained"], "execution_strategy", "/steps/0"))
    validate(c)
    if replacement == "duplicate":
        effective["evidence"][1] = deepcopy(effective["evidence"][0])
    else:
        effective["evidence"][1] = evidence(c["retained"], "execution_input", "/inputs/0/assigning")
    assert len(effective["evidence"]) == 2
    with pytest.raises(ContractError):
        validate(c)


@pytest.mark.parametrize("mutation", ["revision", "sha256", "source_bytes"])
def test_complete_chain_universe_must_be_bound_to_exact_owning_source(mutation):
    c = case()
    effective = c["view"]["inputs"][0]["effective_origin"]
    effective["status"] = "known"
    effective["evidence"].append(evidence(c["retained"], "execution_strategy", "/steps/0"))
    validate(c)
    requirement = c["retained"]["effective_requirements"]
    if mutation == "revision":
        requirement["revision"] = OTHER
    elif mutation == "sha256":
        requirement["sha256"] = "e" * 64
    else:
        c["retained"]["sources"][(requirement["component"], requirement["path"])]["bytes"] += b" "
    # The list of applicable locations and supplied Evidence cardinality stay fixed.
    with pytest.raises(ContractError):
        validate(c)


def test_declared_origin_all_four_proofs_bind_to_frozen_point_phase():
    c = case(claim_phase="declared")
    result = resolve(c, phase="declared")
    assert result["status"] == "bound" and result["reason"] == "ok"
    assert result["origin"] == c["reference"]["origin"]
    binding = result["binding"]
    assert set(binding) == {"reference_id", "annotation", "parameter", "phase", "value",
                            "assignment", "conditions", "receipt"}
    assert binding["phase"] == "declared"
    assert binding["reference_id"] == c["reference"]["id"]
    assert binding["annotation"] == c["claim"]["annotation"]
    assert binding["parameter"] == c["claim"]["parameter"]
    assert binding["value"] == evidence(c["retained"], "frozen_plan", "/point/configuration/" + PATH)
    assert binding["assignment"] == evidence(c["retained"], "value_origin_receipt", "/claims/0/assignment_receipt")
    assert binding["conditions"] == [evidence(c["retained"], "frozen_plan", "/point/configuration/" + TEMP)]
    assert binding["receipt"] == evidence(c["retained"], "value_origin_receipt", "/claims/0")


# Final collated C2 CPP regressions F1-F6; original 40274-byte prefix is frozen.
def append_public_fragment(c, document):
    """Author a second exact public artifact, without changing selected identity."""
    path = "help/fragments/" + document["id"] + ".json"
    content = raw(document)
    c["bundle"]["fragments"].append({"id": document["id"], "file": path, "sha256": digest(content)})
    c["bundle"]["files"].append({"path": path, "media_type": "application/json",
                                   "bytes": len(content), "sha256": digest(content)})
    c["retained"]["payload"][path] = {"bytes": content, "kind": "file"}
    c["retained"]["output_allowlist"] += (path,)
    repack(c)


def test_cpp_bundle_checks_selected_fragment_semantics_with_fresh_hashes():
    good = case()
    validate(good, "bundle")
    bad = case(locator_uri="https://example.org/paper?token=synthetic")
    with pytest.raises(ContractError):
        validate(bad, "bundle")


@pytest.mark.parametrize("defect", [None, "query", "selector"])
def test_cpp_bundle_checks_every_unselected_public_fragment(defect):
    c = case()
    extra = deepcopy(c["fragment"])
    extra["id"] = "model.unselected"
    extra_reference = extra["inputs"][0]["reference_value_origin"]
    extra_reference["id"] = "pilot.unselected-reference"
    if defect == "query":
        extra_reference["origin"]["locators"][0]["uri"] = "https://example.org/paper?"
    elif defect == "selector":
        extra["inputs"][0]["schema_source"]["selector"]["value"] = "/missing"
    reauthor_reference(c, additional_references=(extra_reference,))
    append_public_fragment(c, extra)
    assert c["retained"]["selection"]["fragment_id"] == FRAGMENT_ID
    if defect is None:
        validate(c, "bundle")
    else:
        with pytest.raises(ContractError):
            validate(c, "bundle")


@pytest.mark.parametrize("field", ["release_id", "release_manifest_sha256", "source_revision", "bundle_sha256"])
def test_cpp_unavailable_docs_preserve_each_known_identity_scalar(field):
    c = case()
    c["view"]["binding"].update(status="unavailable", reason="bundle_missing")
    c["view"]["fragment"] = None
    validate(c)
    c["view"]["binding"][field] = None
    with pytest.raises(ContractError):
        validate(c)


def test_cpp_genuinely_missing_retained_identity_stays_null():
    c = case()
    c["retained"]["selection"].update(sources=None, release_id=None)
    del c["retained"]["metadata"]["release_receipt"]
    for key in ("bundle", "fragment", "release_manifest"):
        del c["retained"][key]
    c["view"]["binding"] = {"status": "unknown", "reason": "source_binding_missing",
        "release_id": None, "release_manifest_sha256": None, "source_revision": None, "bundle_sha256": None}
    c["view"]["fragment"] = None
    c["view"]["inputs"] = []
    validate(c)


def test_cpp_assigning_evidence_must_select_the_target_last_assignment():
    c = case()
    validate(c)  # Existing frozen-plan assignment is healthy.
    c["view"]["inputs"][0]["assigning"]["evidence"] = evidence(
        c["retained"], "execution_input", "/inputs/0/assigning")
    validate(c)  # The exact selected snapshot assignment is also healthy.
    c["view"]["inputs"][0]["assigning"] = {"status": "known", "kind": "execution_strategy",
        "source": None, "rule": "fixed_strategy",
        "evidence": evidence(c["retained"], "execution_strategy", "/steps/0")}
    with pytest.raises(ContractError):
        validate(c)


def test_cpp_known_effective_chain_cannot_emit_extra_out_of_scope_evidence():
    c = case()
    effective = c["view"]["inputs"][0]["effective_origin"]
    effective["status"] = "known"
    effective["evidence"].append(evidence(c["retained"], "execution_strategy", "/steps/0"))
    validate(c)
    effective["evidence"].append(evidence(c["retained"], "execution_input", "/context"))
    with pytest.raises(ContractError):
        validate(c)


def two_point_index_case(selected="P-1"):
    """Two original point files of one child, each with a frozen passport proof.

    Private point_passports maps point keys to existing Evidence in original
    frozen_plan bytes. snapshot_files maps logical paths to closed bytes/digest
    and the owning inventory measurement. Neither is a new public receipt.
    """
    c = case()
    r = c["retained"]
    plan = json.loads(r["metadata"]["frozen_plan"]["bytes"])
    first = deepcopy(plan.pop("point")["configuration"])
    second = deepcopy(first)
    second[PATH] = atom(0.15)
    plan["points"] = [{"id": "P-1", "execution_id": "E-1", "configuration": first},
                      {"id": "P-2", "execution_id": "E-1", "configuration": second}]
    r["metadata"]["frozen_plan"] = blob(plan)
    r["point_passports"] = {
        ("E-1", "P-1"): evidence(r, "frozen_plan", "/points/0/configuration"),
        ("E-1", "P-2"): evidence(r, "frozen_plan", "/points/1/configuration")}
    r["snapshot_files"] = {}
    entries, snapshots = [], {}
    for position, point in enumerate(plan["points"]):
        snap = deepcopy(c["snapshot"])
        snap["context"].update(plan_fingerprint=r["metadata"]["frozen_plan"]["sha256"],
            point_id=point["id"], configuration_hash=digest(raw(point["configuration"])))
        snap["origin_bindings"] = []  # No origin receipt is invented for either point.
        for leaf in snap["inputs"]:
            leaf["declared"]["atom"] = deepcopy(point["configuration"][leaf["path"]])
            leaf["used"]["atom"] = deepcopy(leaf["declared"]["atom"])
            leaf["assigning"] = {"status": "unknown", "kind": "unknown", "source": None, "rule": None}
            leaf["effective_origin"] = {"status": "unknown", "steps": []}
        # Runtime used is intentionally distinct, preserving declared/used axes.
        snap["inputs"][0]["used"]["atom"] = atom(0.20 + position * 0.05)
        path = "result/executions/E-1/" + point["id"] + "/attempt-1/model-help-inputs.json"
        record = blob(snap)
        inventory = {"bytes": len(record["bytes"]), "sha256": record["sha256"]}
        r["snapshot_files"][path] = {**record, "inventory": inventory}
        entries.append({"path": path, **inventory, "execution_id": "E-1", "point_id": point["id"],
                        "attempt": 1, "status": "valid", "reason": "ok"})
        snapshots[point["id"]] = snap
    c["snapshot"] = snapshots[selected]
    r["metadata"]["execution_input"] = blob(c["snapshot"])
    del r["metadata"]["value_origin_receipt"]
    selected_context = {**c["snapshot"]["context"],
        "run_uuid": c["view"]["context"]["run_uuid"], "calcjob_uuid": c["view"]["context"]["calcjob_uuid"]}
    r["selection"]["context"] = deepcopy(selected_context)
    c["view"]["context"] = deepcopy(selected_context)
    receipt = json.loads(r["metadata"]["release_receipt"]["bytes"])
    receipt["context"] = deepcopy(selected_context)
    r["metadata"]["release_receipt"] = blob(receipt)
    item = c["view"]["inputs"][0]
    pointer = r["point_passports"][("E-1", selected)]["selector"]
    item["declared"] = {"status": "known", "atom": deepcopy(c["snapshot"]["inputs"][0]["declared"]["atom"]),
        "evidence": evidence(r, "frozen_plan", pointer + "/" + PATH)}
    item["used"] = {"status": "known", "atom": deepcopy(c["snapshot"]["inputs"][0]["used"]["atom"]),
        "evidence": evidence(r, "execution_input", "/inputs/0/used/atom")}
    item["assigning"] = {"status": "unknown", "kind": "unknown", "source": None, "rule": None, "evidence": None}
    item["effective_origin"] = {"status": "unknown", "evidence": []}
    c["index"] = {"format": "qcl-negf.model-help-index.v1", "complete": True, "entries": entries}
    return c


@pytest.mark.parametrize("selected", ["P-1", "P-2"])
def test_cpp_complete_two_point_index_and_each_endpoint_selection(selected):
    c = two_point_index_case(selected)
    validate(c, "index")
    validate(c, "snapshot")
    validate(c)
    assert len(c["index"]["entries"]) == 2
    assert c["view"]["context"]["point_id"] == selected
    assert c["view"]["inputs"][0]["used"]["atom"] != c["view"]["inputs"][0]["declared"]["atom"]


@pytest.mark.parametrize("mutation", ["attempt", "execution", "nonmember", "sibling_payload",
    "passport", "inventory", "duplicate", "count", "aggregate", "missing_sibling"])
def test_cpp_multi_point_index_requires_each_exact_point_file_and_passport(mutation):
    c = two_point_index_case()
    validate(c, "index")
    entries = c["index"]["entries"]
    target = entries[1]
    if mutation in {"attempt", "execution", "nonmember"}:
        if mutation == "attempt":
            target["attempt"] = 2
        elif mutation == "execution":
            target["execution_id"] = "E-2"
        else:
            target["point_id"] = "P-3"
        target["path"] = ("result/executions/" + target["execution_id"] + "/" + target["point_id"] +
                           "/attempt-" + str(target["attempt"]) + "/model-help-inputs.json")
    elif mutation == "sibling_payload":
        # Rehash/index/inventory all agree with real P-1 bytes under P-2 path;
        # only their point context/association is wrong.
        source = deepcopy(c["retained"]["snapshot_files"][entries[0]["path"]])
        c["retained"]["snapshot_files"][target["path"]] = source
        target.update(bytes=len(source["bytes"]), sha256=source["sha256"])
    elif mutation == "passport":
        c["retained"]["point_passports"][("E-1", "P-2")] = deepcopy(
            c["retained"]["point_passports"][("E-1", "P-1")])
    elif mutation == "inventory":
        c["retained"]["snapshot_files"][target["path"]]["inventory"]["bytes"] += 1
    elif mutation == "duplicate":
        entries.append(deepcopy(target))
    elif mutation == "count":
        extra = deepcopy(target)
        extra.update(point_id="P-3", path="result/executions/E-1/P-3/attempt-1/model-help-inputs.json")
        entries.append(extra)
    elif mutation == "aggregate":
        # Two individually bounded invalid files cross only the aggregate cap.
        # Their actual bytes/index/inventory digests remain mutually consistent;
        # no stale selected snapshot alias is retained for those invalid files.
        del c["retained"]["metadata"]["execution_input"]
        for entry in entries:
            payload = b" " * (4 * 1024 * 1024 + 1)
            inventory = {"bytes": len(payload), "sha256": digest(payload)}
            c["retained"]["snapshot_files"][entry["path"]] = {
                "bytes": payload, "sha256": digest(payload), "inventory": inventory}
            entry.update(**inventory, status="invalid", reason="too_large")
    else:
        del c["retained"]["snapshot_files"][target["path"]]
    with pytest.raises(ContractError):
        validate(c, "index")


@pytest.mark.parametrize("replacement", [atom(0.15), atom(0.10, "m"), atom(0.10, "nm", "number")])
def test_cpp_snapshot_declared_value_unit_kind_must_match_frozen_passport(replacement):
    c = case()
    validate(c, "snapshot")
    c["snapshot"]["inputs"][0]["declared"]["atom"] = replacement
    c["retained"]["metadata"]["execution_input"] = blob(c["snapshot"])
    c["index"]["entries"][0].update(bytes=len(c["retained"]["metadata"]["execution_input"]["bytes"]),
        sha256=c["retained"]["metadata"]["execution_input"]["sha256"])
    with pytest.raises(ContractError):
        validate(c, "snapshot")


def test_cpp_snapshot_used_can_differ_and_unknown_declared_is_not_filled():
    c = case()
    c["snapshot"]["inputs"][0]["used"]["atom"] = atom(0.15)
    c["retained"]["metadata"]["execution_input"] = blob(c["snapshot"])
    validate(c, "snapshot")
    c["snapshot"]["inputs"][0]["declared"] = {"status": "unknown", "atom": None}
    c["retained"]["metadata"]["execution_input"] = blob(c["snapshot"])
    before = deepcopy(c["snapshot"])
    validate(c, "snapshot")
    assert c["snapshot"] == before


def test_cpp_unknown_snapshot_declarations_survive_missing_passport_proof():
    c = case()
    plan = json.loads(c["retained"]["metadata"]["frozen_plan"]["bytes"])
    del plan["point"]["configuration"]
    c["retained"]["metadata"]["frozen_plan"] = blob(plan)
    context = c["snapshot"]["context"]
    context.update(plan_fingerprint=c["retained"]["metadata"]["frozen_plan"]["sha256"], configuration_hash=None)
    c["retained"]["selection"]["context"].update(
        plan_fingerprint=context["plan_fingerprint"], configuration_hash=None)
    c["snapshot"]["origin_bindings"] = []
    for item in c["snapshot"]["inputs"]:
        item["declared"] = {"status": "unknown", "atom": None}
    c["retained"]["metadata"]["execution_input"] = blob(c["snapshot"])
    before = deepcopy(c["snapshot"])
    validate(c, "snapshot")
    assert c["snapshot"] == before


# DOC07-C2-F3-SOURCE-E1: assigning authority is independent of numeric display.
def assigning_authority_case(raw_assignment, *, numeric_status="known"):
    c = case()
    c["snapshot"]["inputs"][0]["assigning"] = deepcopy(raw_assignment)
    c["snapshot"]["origin_bindings"] = []
    c["retained"]["metadata"]["execution_input"] = blob(c["snapshot"])
    c["retained"]["metadata"]["value_origin_receipt"] = blob({"claims": []})
    record = c["retained"]["metadata"]["execution_input"]
    c["index"]["entries"][0].update(bytes=len(record["bytes"]), sha256=record["sha256"])
    item = c["view"]["inputs"][0]
    item["used"] = ({"status": "known", "atom": atom(),
                     "evidence": evidence(c["retained"], "execution_input", "/inputs/0/used/atom")}
                    if numeric_status == "known" else {"status": "unknown", "atom": None, "evidence": None})
    item["assigning"] = {**deepcopy(raw_assignment), "evidence": evidence(
        c["retained"], "execution_input", "/inputs/0/assigning")}
    return c


@pytest.mark.parametrize("numeric_status", ["known", "unknown"])
def test_e1_retained_runtime_assigning_is_authoritative_with_any_numeric_display(numeric_status):
    runtime = {"status": "known", "kind": "execution_strategy", "source": None, "rule": "fixed_strategy"}
    c = assigning_authority_case(runtime, numeric_status=numeric_status)
    validate(c)
    # Old frozen assignment is a genuine record but is not the latest assignment.
    stale = case()["view"]["inputs"][0]["assigning"]
    c["view"]["inputs"][0]["assigning"] = stale
    with pytest.raises(ContractError):
        validate(c)


@pytest.mark.parametrize("numeric_status", ["known", "unknown"])
def test_e1_same_runtime_and_frozen_assignment_allow_both_exact_evidence_paths(numeric_status):
    c = case()
    if numeric_status == "unknown":
        c["view"]["inputs"][0]["used"] = {"status": "unknown", "atom": None, "evidence": None}
    validate(c)
    c["view"]["inputs"][0]["assigning"]["evidence"] = evidence(
        c["retained"], "execution_input", "/inputs/0/assigning")
    validate(c)


def test_e1_genuinely_missing_runtime_retains_declared_assignment_fallback():
    c = case()
    del c["retained"]["metadata"]["execution_input"]
    c["view"]["input_status"] = {"status": "unavailable", "reason": "snapshot_missing"}
    c["view"]["inputs"][0]["used"] = {"status": "unknown", "atom": None, "evidence": None}
    validate(c)
    assert c["view"]["inputs"][0]["assigning"]["evidence"] == evidence(
        c["retained"], "frozen_plan", "/assignment")


@pytest.mark.parametrize("numeric_status", ["known", "unknown"])
def test_e1_genuine_redacted_last_assignment_accepts_exact_nonnull_evidence(numeric_status):
    redacted = {"status": "redacted", "kind": "config_file", "source": None, "rule": None}
    c = assigning_authority_case(redacted, numeric_status=numeric_status)
    before = deepcopy(c["view"])
    validate(c)
    assert c["view"] == before
    assert c["view"]["inputs"][0]["assigning"]["source"] is None
    assert c["view"]["inputs"][0]["assigning"]["evidence"] is not None


@pytest.mark.parametrize("mutation", ["known_status", "wrong_leaf", "wrong_kind", "wrong_rule", "digest", "public_source", "private_path"])
def test_e1_redacted_projection_cannot_fabricate_known_source_or_assignment(mutation):
    redacted = {"status": "redacted", "kind": "config_file", "source": None, "rule": None}
    if mutation == "known_status":
        redacted.update(kind="execution_strategy", rule="fixed_strategy")
    c = assigning_authority_case(redacted)
    if mutation == "wrong_leaf":
        # The sibling is a real identical redacted record: hash/record equality
        # cannot distinguish it from the target; only leaf association can.
        c["snapshot"]["inputs"][1]["assigning"] = deepcopy(redacted)
        c["retained"]["metadata"]["execution_input"] = blob(c["snapshot"])
        record = c["retained"]["metadata"]["execution_input"]
        c["index"]["entries"][0].update(bytes=len(record["bytes"]), sha256=record["sha256"])
        c["view"]["inputs"][0]["used"]["evidence"] = evidence(
            c["retained"], "execution_input", "/inputs/0/used/atom")
        c["view"]["inputs"][0]["assigning"]["evidence"] = evidence(
            c["retained"], "execution_input", "/inputs/0/assigning")
    validate(c)
    assigning = c["view"]["inputs"][0]["assigning"]
    if mutation == "known_status":
        assigning["status"] = "known"
    elif mutation == "wrong_leaf":
        assigning["evidence"] = evidence(c["retained"], "execution_input", "/inputs/1/assigning")
    elif mutation == "wrong_kind":
        assigning["kind"] = "execution_strategy"
    elif mutation == "wrong_rule":
        assigning["rule"] = "fixed_strategy"
    elif mutation == "digest":
        assigning["evidence"]["sha256"] = "e" * 64
    elif mutation == "public_source":
        assigning["source"] = ref(c["retained"]["sources"], "public/assignment.json", "json_pointer", "/height")
    else:
        assigning["source"] = {**ref(c["retained"]["sources"], "public/assignment.json"),
                                "path": "/private/operator/assignment.json"}
    with pytest.raises(ContractError):
        validate(c)


def actual_identity_case(selected="P-1"):
    """Authored actual-shaped identity control, never a solver/archive capture.

    The stored Julia passport digest is opaque; it deliberately differs from
    Python JSON hashes. No declared projection or source origin is supplied.
    """
    c = two_point_index_case(selected)
    r = c["retained"]
    plan = {"schema": "qcl-negf-scientific-plan-v2", "fingerprint": "1" * 64,
            "scientific_fingerprint": "2" * 64, "model_revision": "transport-contract-v2",
            "executions": [{"id": "E-1", "point_ids": ["P-1", "P-2"],
                "resolved_configuration": {"physical": {"lattice_temperature": "80 K",
                    "voltage_per_period": "56 mV", "interface_roughness_height": "0.10 nm"}}}],
            "points": []}
    for position, point_id in enumerate(("P-1", "P-2")):
        axes = {"temperature_K": 70.0 + position, "voltage_per_period_V": 0.0}
        plan["points"].append({"id": point_id, "execution_id": "E-1", **axes,
            "effective_inputs": {**axes, "configuration_hash": str(position + 3) * 64,
                "hash_encoding": "qcl-negf-canonical-bytes-v1", "axes_applied": True}})
    r["metadata"]["frozen_plan"] = blob(plan)
    del r["point_passports"]  # Actual plan contains the identity, never /configuration.
    for entry, point in zip(c["index"]["entries"], plan["points"]):
        snap = json.loads(r["snapshot_files"][entry["path"]]["bytes"])
        snap["context"].update(plan_fingerprint=plan["fingerprint"],
            scientific_fingerprint=plan["scientific_fingerprint"], model_revision=plan["model_revision"],
            configuration_hash=point["effective_inputs"]["configuration_hash"])
        for leaf in snap["inputs"]:
            leaf["declared"] = {"status": "unknown", "atom": None}
        record = blob(snap)
        inventory = {"bytes": len(record["bytes"]), "sha256": record["sha256"]}
        r["snapshot_files"][entry["path"]] = {**record, "inventory": inventory}
        entry.update(inventory)
        if point["id"] == selected:
            c["snapshot"] = snap
    r["metadata"]["execution_input"] = blob(c["snapshot"])
    context = {**r["selection"]["context"], **c["snapshot"]["context"]}
    r["selection"]["context"] = deepcopy(context)
    c["view"]["context"] = deepcopy(context)
    receipt = json.loads(r["metadata"]["release_receipt"]["bytes"])
    receipt["context"] = deepcopy(context)
    r["metadata"]["release_receipt"] = blob(receipt)
    item = c["view"]["inputs"][0]
    item["declared"] = {"status": "unknown", "atom": None, "evidence": None}
    item["used"]["evidence"] = evidence(r, "execution_input", "/inputs/0/used/atom")
    item["value_origin"] = {"declared": unknown_origin(), "used": unknown_origin()}
    return c


@pytest.mark.parametrize("selected", ["P-1", "P-2"])
def test_actual_identity_keeps_declared_unknown_and_retained_used(selected):
    c = actual_identity_case(selected)
    validate(c, "index")
    validate(c, "snapshot")
    validate(c)
    assert c["snapshot"]["inputs"][0]["declared"]["status"] == "unknown"
    assert c["view"]["inputs"][0]["value_origin"]["used"]["status"] == "unknown"
    # Endpoint validation must not open any sibling snapshot bytes.
    del c["retained"]["snapshot_files"]
    validate(c, "snapshot")
    validate(c)


@pytest.mark.parametrize("mutation", ["duplicate_execution", "duplicate_point", "orphan_point",
    "foreign_membership", "duplicate_membership", "missing_membership", "extra_membership",
    "temperature", "voltage", "axes_false", "encoding", "absent_passport", "malformed_passport",
    "malformed_hash", "hash", "fingerprint", "scientific_fingerprint", "model_revision",
    "unknown_schema", "null_schema"])
def test_actual_identity_rejects_contradictory_or_missing_plan_proof(mutation):
    c = actual_identity_case()
    r = c["retained"]
    plan = json.loads(r["metadata"]["frozen_plan"]["bytes"])
    row = plan["points"][0]
    if mutation == "duplicate_execution":
        plan["executions"].append(deepcopy(plan["executions"][0]))
    elif mutation == "duplicate_point":
        plan["points"].append(deepcopy(row))
    elif mutation == "orphan_point":
        row["execution_id"] = "E-2"
    elif mutation == "foreign_membership":
        plan["executions"].append({"id": "E-2", "point_ids": ["P-1"]})
    elif mutation == "duplicate_membership":
        plan["executions"][0]["point_ids"].append("P-1")
    elif mutation == "missing_membership":
        plan["executions"][0]["point_ids"].remove("P-1")
    elif mutation == "extra_membership":
        plan["executions"][0]["point_ids"].append("P-3")
    elif mutation in {"temperature", "voltage"}:
        row["effective_inputs"]["temperature_K" if mutation == "temperature" else "voltage_per_period_V"] += 1
    elif mutation == "axes_false":
        row["effective_inputs"]["axes_applied"] = False
    elif mutation == "encoding":
        row["effective_inputs"]["hash_encoding"] = "json"
    elif mutation == "absent_passport":
        del row["effective_inputs"]
    elif mutation == "malformed_passport":
        row["effective_inputs"] = []
    elif mutation in {"malformed_hash", "hash"}:
        row["effective_inputs"]["configuration_hash"] = "invalid" if mutation == "malformed_hash" else "9" * 64
    elif mutation in {"fingerprint", "scientific_fingerprint", "model_revision"}:
        plan[mutation] = "9" * 64
    else:
        plan["schema"] = "unsupported-plan" if mutation == "unknown_schema" else None
    r["metadata"]["frozen_plan"] = blob(plan)
    with pytest.raises(ContractError):
        validate(c, "snapshot")


@pytest.mark.parametrize("field,value", [("execution_id", "E-2"), ("point_id", "P-2"),
                                        ("attempt", 2)])
def test_actual_snapshot_cannot_select_sibling_or_retry(field, value):
    c = actual_identity_case()
    c["snapshot"]["context"][field] = value
    c["retained"]["metadata"]["execution_input"] = blob(c["snapshot"])
    with pytest.raises(ContractError):
        validate(c, "snapshot")


def test_actual_known_declared_requires_separate_projection_proof():
    c = actual_identity_case()
    c["snapshot"]["inputs"][0]["declared"] = {"status": "known", "atom": atom()}
    c["retained"]["metadata"]["execution_input"] = blob(c["snapshot"])
    with pytest.raises(ContractError):
        validate(c, "snapshot")


def test_actual_raw_plan_digest_remains_exact_despite_identity_equality():
    c = actual_identity_case()
    r = c["retained"]
    original = r["metadata"]["frozen_plan"]["sha256"]
    plan = json.loads(r["metadata"]["frozen_plan"]["bytes"])
    payload = json.dumps(plan, indent=2).encode("utf-8")
    r["metadata"]["frozen_plan"] = {"bytes": payload, "sha256": digest(payload)}
    assert digest(payload) != original
    validate(c, "snapshot")  # Fingerprint/passport equality does not reserialize plan.
    # A caller cannot keep an old raw digest after changing bytes.
    r["metadata"]["frozen_plan"]["sha256"] = original
    with pytest.raises(ContractError):
        validate(c, "snapshot")


@pytest.mark.parametrize("mutation", ["retry", "sibling_context", "sibling_hash", "raw_size", "raw_hash"])
def test_actual_full_index_retains_each_sibling_and_original_byte_contract(mutation):
    c = actual_identity_case()
    r = c["retained"]
    entry = c["index"]["entries"][1]
    record = r["snapshot_files"][entry["path"]]
    snapshot = json.loads(record["bytes"])
    if mutation == "retry":
        snapshot["context"]["attempt"] = 2
    elif mutation == "sibling_context":
        snapshot["context"]["point_id"] = "P-1"
    elif mutation == "sibling_hash":
        snapshot["context"]["configuration_hash"] = c["snapshot"]["context"]["configuration_hash"]
    elif mutation == "raw_size":
        entry["bytes"] += 1
    else:
        entry["sha256"] = "9" * 64
    if mutation in {"retry", "sibling_context", "sibling_hash"}:
        # Rehash/reinventory excludes stale outer bytes as the failure oracle.
        replacement = blob(snapshot)
        inventory = {"bytes": len(replacement["bytes"]), "sha256": replacement["sha256"]}
        r["snapshot_files"][entry["path"]] = {**replacement, "inventory": inventory}
        entry.update(inventory)
    with pytest.raises(ContractError):
        validate(c, "index")


def test_actual_matching_sibling_values_do_not_authorize_wrong_identity():
    c = actual_identity_case()
    c["snapshot"]["context"]["point_id"] = "P-2"
    # Used values matching another point cannot change selected child authority.
    c["retained"]["metadata"]["execution_input"] = blob(c["snapshot"])
    with pytest.raises(ContractError):
        validate(c, "snapshot")


def test_actual_identity_does_not_authorize_known_view_declaration():
    c = actual_identity_case()
    c["view"]["inputs"][0]["declared"] = {
        "status": "known", "atom": atom(),
        "evidence": evidence(c["retained"], "frozen_plan",
                             "/executions/0/resolved_configuration/physical/interface_roughness_height")}
    with pytest.raises(ContractError):
        validate(c)


def test_actual_repeated_passport_key_is_not_silently_last_wins():
    c = actual_identity_case()
    r = c["retained"]
    payload = r["metadata"]["frozen_plan"]["bytes"]
    payload = payload.replace(b'"effective_inputs":{', b'"effective_inputs":{},"effective_inputs":{', 1)
    r["metadata"]["frozen_plan"] = {"bytes": payload, "sha256": digest(payload)}
    with pytest.raises(ContractError):
        validate(c, "snapshot")


# DOC07 G2-L source-only controls. These are authored synthetic associations;
# the map producer's publication/production recipe is not established here.
RUNNER = "components/QCLNEGFRunner.jl"
DECLARED_MAP = "docs/help/declared-input-map.json"


def declared_map_document():
    rows = [
        ("physical.impurity_screening_wavenumber", "execution_configuration", "/physical/impurity_screening_wavenumber", "quantity", "nm^-1", "canonical_quantity_literal"),
        ("physical.interface_correlation_length", "execution_configuration", "/physical/interface_correlation_length", "quantity", "nm", "canonical_quantity_literal"),
        (PATH, "execution_configuration", "/physical/interface_roughness_height", "quantity", "nm", "canonical_quantity_literal"),
        (TEMP, "point", "/temperature_K", "quantity", "K", "json_number"),
        ("physical.lo_phonon_energy", "execution_configuration", "/physical/lo_phonon_energy", "quantity", "meV", "canonical_quantity_literal"),
        ("physical.lo_screening_wavenumber", "execution_configuration", "/physical/lo_screening_wavenumber", "quantity", "nm^-1", "canonical_quantity_literal"),
        ("physical.lo_temperature", "point", "/temperature_K", "quantity", "K", "json_number"),
        ("production.energy_chunk", "execution_configuration", "/production/energy_chunk", "integer", "1", "json_integer"),
    ]
    return {"format": "qcl-negf.declared-input-map.v1", "rows": [dict(zip(
        ("phase", "path", "base", "pointer", "atom_kind", "unit", "rule"),
        ("declared", *row))) for row in rows]}


def declared_projection_case(selected="P-1"):
    c = actual_identity_case(selected)
    r = c["retained"]
    r["selection"]["sources"]["components"].append(
        {"path": RUNNER, "revision": OTHER, "url": "https://example.org/runner.git"})
    r["selection"]["sources"]["components"].sort(key=lambda row: row["path"])
    r["sources"][(RUNNER, DECLARED_MAP)] = {"revision": OTHER, "bytes": raw(declared_map_document())}
    reference = ref(r["sources"], DECLARED_MAP, "json_pointer", "", RUNNER)
    r["declared_map_ref"] = reference
    r["input_allowlist"] = (*r["input_allowlist"], (RUNNER, DECLARED_MAP))
    r["selector_allowlist"] = (*r["selector_allowlist"], (RUNNER, DECLARED_MAP, "json_pointer", ""))
    bundle = json.loads(r["bundle"]["bytes"])
    r["public_reviews"] = (*r["public_reviews"], {
        "source": {**reference, "selector": {"kind": "file", "value": ""}},
        "recipe": bundle["generator"]["recipes"][0], "receipt": blob({"synthetic": True})})
    plan = json.loads(r["metadata"]["frozen_plan"]["bytes"])
    config = plan["executions"][0]["resolved_configuration"]
    config["physical"].update(impurity_screening_wavenumber="0.2 nm^-1",
        interface_correlation_length="9 nm", lo_phonon_energy="36 meV", lo_screening_wavenumber="0.3 nm^-1")
    config["production"] = {"energy_chunk": 9007199254740993}
    r["metadata"]["frozen_plan"] = blob(plan)
    # Fresh synthetic publication graph, never production publication evidence.
    c["bundle"]["sources"] = deepcopy(r["selection"]["sources"])
    r["bundle"] = blob(c["bundle"])
    manifest = json.loads(r["release_manifest"]["bytes"])
    manifest["sources"] = deepcopy(r["selection"]["sources"])
    r["release_manifest"] = blob(manifest)
    receipt = json.loads(r["metadata"]["release_receipt"]["bytes"])
    receipt.update(bundle_sha256=r["bundle"]["sha256"], release_manifest_sha256=r["release_manifest"]["sha256"])
    r["metadata"]["release_receipt"] = blob(receipt)
    c["view"]["binding"].update(bundle_sha256=receipt["bundle_sha256"],
        release_manifest_sha256=receipt["release_manifest_sha256"])
    return c


def replace_declared_map(c, payload):
    r = c["retained"]
    r["sources"][(RUNNER, DECLARED_MAP)]["bytes"] = payload
    r["declared_map_ref"]["sha256"] = digest(payload)
    r["public_reviews"][-1]["source"]["sha256"] = digest(payload)


@pytest.mark.parametrize("selected,temperature", [("P-1", 70.0), ("P-2", 71.0)])
def test_declared_projection_exact_raw_evidence_and_point_overlay(selected, temperature):
    from qcl_negf_contracts.model_help import _Evidence
    c = declared_projection_case(selected)
    session = _Evidence(c["retained"])
    value, proof = session.scalar(PATH, "declared")
    assert value == atom()
    assert proof == evidence(c["retained"], "frozen_plan", "/executions/0/resolved_configuration/physical/interface_roughness_height")
    assert session.evidence(proof) == "0.10 nm"  # Raw evidence stays raw.
    assert session.scalar(TEMP, "declared")[0] == atom(temperature, "K")
    assert session.declared_scalar(TEMP, "E-1", "P-2")[0] == atom(71.0, "K")
    assert session.scalar("production.energy_chunk", "declared")[0] == atom(9007199254740993, "1", "integer")
    assert session.scalar("unsupported.path", "declared") == (None, None)


@pytest.mark.parametrize("mutation", ["owner", "revision", "hash", "selector", "extra", "duplicate_row", "order", "version", "unit", "rule", "pointer", "duplicate_key", "cap", "input_allowlist", "selector_allowlist"])
def test_declared_map_supplied_contradictions_reject(mutation):
    from qcl_negf_contracts.model_help import _Evidence
    c = declared_projection_case()
    r = c["retained"]
    document = declared_map_document()
    if mutation in {"owner", "revision", "hash", "selector"}:
        key, value = {"owner": ("component", COMPONENT), "revision": ("revision", ROOT),
            "hash": ("sha256", "0" * 64), "selector": ("selector", {"kind": "json_pointer", "value": "/rows"})}[mutation]
        r["declared_map_ref"][key] = value
    elif mutation in {"input_allowlist", "selector_allowlist"}:
        r[mutation] = ()
    else:
        if mutation == "extra":
            document["extra"] = 0
        elif mutation == "duplicate_row":
            document["rows"][1] = deepcopy(document["rows"][0])
        elif mutation == "order":
            document["rows"].reverse()
        elif mutation == "version":
            document["format"] = "qcl-negf.declared-input-map.v2"
        elif mutation in {"unit", "rule", "pointer"}:
            document["rows"][0][mutation] = "wrong"
        payload = raw(document)
        if mutation == "duplicate_key":
            payload = payload.replace(b'"format":', b'"format":"duplicate","format":', 1)
        if mutation == "cap":
            payload = b" " * 4097 + payload
        replace_declared_map(c, payload)
    with pytest.raises(ContractError):
        _Evidence(r).scalar(PATH, "declared")


@pytest.mark.parametrize("missing", ["ref", "source", "review", "recipe"])
def test_declared_map_missing_proof_does_not_authorize_known(missing):
    from qcl_negf_contracts.model_help import _Evidence, _MissingProof
    c = declared_projection_case()
    r = c["retained"]
    if missing == "ref":
        del r["declared_map_ref"]
    elif missing == "source":
        del r["sources"][(RUNNER, DECLARED_MAP)]
    elif missing == "review":
        r["public_reviews"] = ()
    else:
        r["public_reviews"][-1]["recipe"] = {**r["public_reviews"][-1]["recipe"], "sha256": "0" * 64}
    with pytest.raises(_MissingProof):
        _Evidence(r).scalar(PATH, "declared")
    c["snapshot"]["inputs"][0]["declared"] = {"status": "known", "atom": atom()}
    r["metadata"]["execution_input"] = blob(c["snapshot"])
    with pytest.raises(ContractError):
        validate(c, "snapshot")


@pytest.mark.parametrize("literal", [None, True, {}, "0.1 m", "+0.1 nm", ".1 nm", "01 nm", "0.1  nm", " 0.1 nm", "1e999 nm", "NaN nm", "1\tnm", "1" * 65 + " nm"])
def test_declared_unsupported_literals_remain_unknown(literal):
    from qcl_negf_contracts.model_help import _Evidence
    c = declared_projection_case()
    r = c["retained"]
    plan = json.loads(r["metadata"]["frozen_plan"]["bytes"])
    plan["executions"][0]["resolved_configuration"]["physical"]["interface_roughness_height"] = literal
    r["metadata"]["frozen_plan"] = blob(plan)
    assert _Evidence(r).scalar(PATH, "declared") == (None, None)


def test_declared_map_cap_precedes_source_decode(monkeypatch):
    import qcl_negf_contracts.model_help as model_help
    c = declared_projection_case()
    replace_declared_map(c, b" " * 4097)
    session = model_help._Evidence(c["retained"])
    def forbidden(*args, **kwargs):
        raise AssertionError("map source decode must not run before cap rejection")
    monkeypatch.setattr(session, "source", forbidden)
    with pytest.raises(ContractError):
        session.scalar(PATH, "declared")


def test_used_direct_atom_never_reads_declared_map():
    from qcl_negf_contracts.model_help import _Evidence
    c = declared_projection_case()
    c["retained"]["declared_map_ref"] = {"malformed": True}
    value, proof = _Evidence(c["retained"]).scalar(PATH, "used")
    assert value == atom(0.2)
    assert proof["container"] == "execution_input"


def test_declared_known_snapshot_view_and_raw_pointer_controls():
    c = declared_projection_case()
    r = c["retained"]
    c["snapshot"]["inputs"][0]["declared"] = {"status": "known", "atom": atom()}
    r["metadata"]["execution_input"] = blob(c["snapshot"])
    validate(c, "snapshot")
    from qcl_negf_contracts.model_help import _Evidence
    session = _Evidence(r)
    _, proof = session.scalar(PATH, "declared")
    item = c["view"]["inputs"][0]
    item["declared"] = {"status": "known", "atom": atom(), "evidence": proof}
    item["used"]["evidence"] = evidence(r, "execution_input", "/inputs/0/used/atom")
    validate(c)
    item["declared"]["evidence"] = evidence(r, "frozen_plan", "/points/0/temperature_K")
    with pytest.raises(ContractError):
        validate(c)
    assert proof["selector"] != "/points/0/temperature_K"
    assert c["view"]["inputs"][0]["value_origin"]["declared"]["status"] == "unknown"
    c["snapshot"]["inputs"][0]["declared"]["atom"] = atom(0.2)
    r["metadata"]["execution_input"] = blob(c["snapshot"])
    with pytest.raises(ContractError):
        validate(c, "snapshot")


@pytest.mark.parametrize("path,value,expected", [
    ("physical.impurity_screening_wavenumber", "0.2 nm^-1", atom(0.2, "nm^-1")),
    ("physical.interface_correlation_length", "9 nm", atom(9.0)),
    (PATH, "-1.25e-1 nm", atom(-0.125)),
    ("physical.lo_phonon_energy", "36 meV", atom(36.0, "meV")),
    ("physical.lo_screening_wavenumber", "0.3 nm^-1", atom(0.3, "nm^-1")),
    ("production.energy_chunk", True, None), ("production.energy_chunk", 1.0, None),
    ("production.energy_chunk", None, None), (TEMP, True, None),
    (TEMP, "70", None), (TEMP, None, None),
])
def test_declared_rule_types_and_exact_units(path, value, expected):
    from qcl_negf_contracts.model_help import _Evidence
    c = declared_projection_case()
    r = c["retained"]
    plan = json.loads(r["metadata"]["frozen_plan"]["bytes"])
    if path == TEMP:
        plan["points"][0]["temperature_K"] = value
        plan["points"][0]["effective_inputs"]["temperature_K"] = value
    else:
        section, leaf = path.split(".")
        plan["executions"][0]["resolved_configuration"][section][leaf] = value
    r["metadata"]["frozen_plan"] = blob(plan)
    if path == TEMP and (value is None or isinstance(value, (str, bool))):
        # The pre-existing identity contract rejects contradictory point axes
        # before projection; test primitive subset independently in that case.
        from qcl_negf_contracts.model_help import _declared_atom
        row = next(row for row in declared_map_document()["rows"] if row["path"] == path)
        assert _declared_atom(value, row) is None
    else:
        actual, proof = _Evidence(r).scalar(path, "declared")
        assert actual == expected
        assert (proof is None) == (expected is None)


def test_declared_index_uses_each_snapshot_context_for_equal_leaf_values():
    c = declared_projection_case()
    r = c["retained"]
    for position, entry in enumerate(c["index"]["entries"]):
        snapshot = json.loads(r["snapshot_files"][entry["path"]]["bytes"])
        temperature = next(item for item in snapshot["inputs"] if item["path"] == TEMP)
        temperature["declared"] = {"status": "known", "atom": atom(70.0 + position, "K")}
        assert len({item["path"] for item in snapshot["inputs"]}) == len(snapshot["inputs"])
        record = blob(snapshot)
        inventory = {"bytes": len(record["bytes"]), "sha256": record["sha256"]}
        r["snapshot_files"][entry["path"]] = {**record, "inventory": inventory}
        entry.update(inventory)
        if entry["point_id"] == r["selection"]["context"]["point_id"]:
            c["snapshot"] = snapshot
            r["metadata"]["execution_input"] = deepcopy(record)
            assert r["metadata"]["execution_input"]["bytes"] == r["snapshot_files"][entry["path"]]["bytes"]
    validate(c, "index")
    selected_bytes = r["metadata"]["execution_input"]["bytes"]
    sibling = c["index"]["entries"][1]
    snapshot = json.loads(r["snapshot_files"][sibling["path"]]["bytes"])
    temperature = next(item for item in snapshot["inputs"] if item["path"] == TEMP)
    temperature["declared"]["atom"] = atom(70.0, "K")
    record = blob(snapshot)
    inventory = {"bytes": len(record["bytes"]), "sha256": record["sha256"]}
    r["snapshot_files"][sibling["path"]] = {**record, "inventory": inventory}
    sibling.update(inventory)
    assert r["metadata"]["execution_input"]["bytes"] == selected_bytes
    with pytest.raises(ContractError):
        validate(c, "index")


def test_declared_projection_does_not_create_origin_and_exact_receipt_can_bind():
    c = declared_projection_case()
    r = c["retained"]
    assert _resolve_value_origin(c["reference"], None, phase="declared", retained=r)["status"] == "unknown"
    claim = deepcopy(c["claim"])
    claim["phase"] = "declared"
    claim["conditions"][0]["phase"] = "declared"
    receipt = claim["assignment_receipt"]
    for field in ("plan_fingerprint", "execution_id", "point_id", "attempt"):
        receipt[field] = r["selection"]["context"][field]
    receipt["leaf_pointer"] = "/executions/0/resolved_configuration/physical/interface_roughness_height"
    plan = json.loads(r["metadata"]["frozen_plan"]["bytes"])
    plan["assignment"] = {"status": "known", "kind": "config_file", "source": receipt["source"], "rule": None}
    r["metadata"]["frozen_plan"] = blob(plan)
    c["snapshot"]["origin_bindings"] = [claim]
    r["metadata"]["execution_input"] = blob(c["snapshot"])
    r["metadata"]["value_origin_receipt"] = blob({"claims": [claim]})
    result = _resolve_value_origin(c["reference"], claim, phase="declared", retained=r)
    assert result["status"] == "bound"
    assert result["binding"]["value"] == evidence(r, "frozen_plan", receipt["leaf_pointer"])
    # Genuine sibling raw leaf exists and even matches: equality cannot choose it.
    plan["executions"][0]["resolved_configuration"]["physical"]["interface_correlation_length"] = "0.10 nm"
    r["metadata"]["frozen_plan"] = blob(plan)
    receipt["leaf_pointer"] = "/executions/0/resolved_configuration/physical/interface_correlation_length"
    c["snapshot"]["origin_bindings"] = [claim]
    r["metadata"]["execution_input"] = blob(c["snapshot"])
    r["metadata"]["value_origin_receipt"] = blob({"claims": [claim]})
    result = _resolve_value_origin(c["reference"], claim, phase="declared", retained=r)
    assert result["status"] == "unknown"
