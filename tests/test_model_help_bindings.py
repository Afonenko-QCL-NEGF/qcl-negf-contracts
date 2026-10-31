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

from qcl_negf_contracts import schema_validator
from qcl_negf_contracts.messages import ContractError
from qcl_negf_contracts.model_help import (
    _Evidence,
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

# Literal historical Root source-graph.json, not a maintained revision lock.
# Its raw bytes and mixed-case order are independent of the consumer/producer.
ACTUAL_GRAPH_BYTES = b'''{
  "format": "qcl-negf.git-graph.v1",
  "revision": "46709f7a89f0d537c055b01af784f3210fc7e204",
  "components": [
    {
      "revision": "d8f8092ca1c76523d85384b4bac8198d8bfa736b",
      "path": "components/qcl-negf-aiida",
      "url": "https://github.com/Afonenko-QCL-NEGF/qcl-negf-aiida.git"
    },
    {
      "revision": "f4009c933183d8537e289d2fa5fa898defd2d9b5",
      "path": "components/qcl-negf-contracts",
      "url": "https://github.com/Afonenko-QCL-NEGF/qcl-negf-contracts.git"
    },
    {
      "revision": "f729e2681224d6537538179ab760fefefd575003",
      "path": "components/qcl-negf-platform",
      "url": "https://github.com/Afonenko-QCL-NEGF/qcl-negf-platform.git"
    },
    {
      "revision": "2622de5ee28b454ff4f809cc3dd00c1e5bc2295d",
      "path": "components/qcl-negf-portal",
      "url": "https://github.com/Afonenko-QCL-NEGF/qcl-negf-portal.git"
    },
    {
      "revision": "3ed8a9fe5f16f51bbcb7547ff2d677e8d3608731",
      "path": "components/qcl-negf-research",
      "url": "https://github.com/Afonenko-QCL-NEGF/qcl-negf-research.git"
    },
    {
      "revision": "a0b426759959d9011a41e8d8812704774f950eda",
      "path": "components/qcl-negf-results",
      "url": "https://github.com/Afonenko-QCL-NEGF/qcl-negf-results.git"
    },
    {
      "revision": "5b1cdd458eb07ff8c7c792642eda58d9061e1017",
      "path": "components/QCLNEGF.jl",
      "url": "https://github.com/Afonenko-QCL-NEGF/QCLNEGF.jl.git"
    },
    {
      "revision": "f0e5950e6a4b4551aa54f039e9718042f34df8aa",
      "path": "components/QCLNEGFRunner.jl",
      "url": "https://github.com/Afonenko-QCL-NEGF/QCLNEGFRunner.jl.git"
    }
  ]
}
'''
ACTUAL_PATHS = [
    "components/qcl-negf-aiida", "components/qcl-negf-contracts",
    "components/qcl-negf-platform", "components/qcl-negf-portal",
    "components/qcl-negf-research", "components/qcl-negf-results",
    "components/QCLNEGF.jl", "components/QCLNEGFRunner.jl",
]


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


def actual_graph_docs_case():
    """Actual historical graph, explicitly synthetic docs-only retained proofs."""
    c = case()
    graph = json.loads(ACTUAL_GRAPH_BYTES)
    sources = {
        (CONTRACTS, "src/qcl_negf_contracts/schemas/model-help.schema.json"): {
            "revision": "f4009c933183d8537e289d2fa5fa898defd2d9b5",
            "bytes": b'{"synthetic":"schema source"}'},
        (COMPONENT, "docs/recipe.json"): {
            "revision": "3ed8a9fe5f16f51bbcb7547ff2d677e8d3608731",
            "bytes": b'{"synthetic":"reviewed recipe and toolchain"}'},
    }
    recipe = ref(sources, "docs/recipe.json")
    bundle = c["bundle"]
    bundle.update(sources=graph, fragments=[], aliases=[])
    bundle["schema"] = ref(sources, "src/qcl_negf_contracts/schemas/model-help.schema.json",
                           component=CONTRACTS)
    bundle["generator"].update(recipes=[recipe], toolchain_lock=recipe)
    bundle["files"] = [item for item in bundle["files"] if item["path"] == "research/model.html"]
    retained = c["retained"]
    retained["selection"]["sources"] = graph  # Shared intentionally, as in case().
    retained["sources"] = sources
    retained["input_allowlist"] = tuple(sources)
    retained["selector_allowlist"] = tuple((component, path, "file", "")
                                           for component, path in sources)
    retained["public_reviews"] = tuple({
        "source": ref(sources, path, component=component), "recipe": recipe,
        "receipt": {"bytes": b"Synthetic docs-only review",
                    "sha256": digest(b"Synthetic docs-only review")}}
        for component, path in sources)
    retained["payload"].pop(FRAGMENT_PATH)
    retained.pop("fragment")
    retained["output_allowlist"] = ("research/model.html",)
    retained["bundle"] = blob(bundle)
    retained["release_manifest"] = blob({"format": "qcl-negf.release.v2", "sources": graph, "wheels": []})
    retained["selection"]["release_id"] = retained["release_manifest"]["sha256"]
    retained["metadata"] = {"release_receipt": blob({
        "context": retained["selection"]["context"],
        "release_id": retained["release_manifest"]["sha256"],
        "release_manifest_sha256": retained["release_manifest"]["sha256"],
        "source_revision": graph["revision"], "bundle_sha256": retained["bundle"]["sha256"]})}
    return c


def test_actual_root_mixed_case_graph_preserves_identity_order_and_bytes():
    c = actual_graph_docs_case()
    retained = c["retained"]
    graph = retained["selection"]["sources"]
    before = raw(graph)
    candidate_bytes = retained["bundle"]["bytes"]
    assert digest(ACTUAL_GRAPH_BYTES) == "aeb06fc29c5efc4e8e745c6879e6fc9230fc1aef8b6f9c5ed4130d7ac1f6e69a"
    assert [row["path"] for row in graph["components"]] == ACTUAL_PATHS
    schema_validator("model-help.schema.json").validate(c["bundle"])
    assert _Evidence(retained).graph() is graph
    validate(c, "bundle")
    _Evidence(retained).publication(c["bundle"])
    assert raw(graph) == before
    assert [row["path"] for row in graph["components"]] == ACTUAL_PATHS
    assert retained["bundle"]["bytes"] == candidate_bytes


@pytest.mark.parametrize("conflicting", [False, True])
def test_actual_graph_duplicate_component_paths_are_rejected(conflicting):
    c = actual_graph_docs_case()
    validate(c, "bundle")
    duplicate = deepcopy(c["bundle"]["sources"]["components"][0])
    if conflicting:
        duplicate.update(revision=OTHER, url="https://example.org/conflicting.git")
    c["bundle"]["sources"]["components"].append(duplicate)
    c["retained"]["bundle"] = blob(c["bundle"])
    with pytest.raises(ContractError, match="duplicate source component"):
        validate(c, "bundle")


def test_actual_graph_bundle_reorder_does_not_reorder_selected_graph():
    c = actual_graph_docs_case()
    validate(c, "bundle")
    retained = c["retained"]
    selected_bytes = raw(retained["selection"]["sources"])
    c["bundle"]["sources"] = deepcopy(c["bundle"]["sources"])
    c["bundle"]["sources"]["components"].reverse()
    retained["bundle"] = blob(c["bundle"])
    receipt = json.loads(retained["metadata"]["release_receipt"]["bytes"])
    receipt["bundle_sha256"] = retained["bundle"]["sha256"]
    retained["metadata"]["release_receipt"] = blob(receipt)
    with pytest.raises(ContractError, match="bundle differs from selected graph"):
        validate(c, "bundle")
    assert raw(retained["selection"]["sources"]) == selected_bytes


def test_actual_graph_release_reorder_keeps_honest_hashes_and_selected_graph():
    c = actual_graph_docs_case()
    retained = c["retained"]
    _Evidence(retained).publication(c["bundle"])
    selected_bytes = raw(retained["selection"]["sources"])
    manifest = json.loads(retained["release_manifest"]["bytes"])
    manifest["sources"]["components"].reverse()  # Detached by decoding only this branch.
    retained["release_manifest"] = blob(manifest)
    retained["selection"]["release_id"] = retained["release_manifest"]["sha256"]
    receipt = json.loads(retained["metadata"]["release_receipt"]["bytes"])
    receipt.update(release_id=retained["release_manifest"]["sha256"],
                   release_manifest_sha256=retained["release_manifest"]["sha256"])
    retained["metadata"]["release_receipt"] = blob(receipt)
    with pytest.raises(ContractError, match="release source graph mismatch"):
        _Evidence(retained).publication(c["bundle"])
    assert raw(retained["selection"]["sources"]) == selected_bytes


def test_actual_graph_valid_sha_wrong_owner_revision_is_rejected():
    c = actual_graph_docs_case()
    validate(c, "bundle")
    c["bundle"]["schema"]["revision"] = OTHER
    c["retained"]["bundle"] = blob(c["bundle"])
    with pytest.raises(ContractError, match="source revision mismatch"):
        validate(c, "bundle")


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


# P10 USED: detached contract controls; no capture/ORM/source authority is asserted.
def no_reference_case():
    c = case()
    c["fragment"]["inputs"][0]["reference_value_origin"] = None
    repack(c)
    return c


def nested_passport_case(*, local_attempt=1, child_attempt=1, capture=False):
    """Original Runner-shaped passports; their hash is NOT the JSON row digest.

    Values and identity are synthetic independent literals. Original whitespace
    bytes remain authoritative; no flat Atom configuration is constructed.
    """
    c = two_point_index_case()
    r = c["retained"]
    plan = json.loads(r["metadata"]["frozen_plan"]["bytes"])
    plan.update(fingerprint="1" * 64, scientific_fingerprint="d" * 64,
                model_revision="synthetic-frozen-model", executions=[{
                    "id": "E-1", "point_ids": ["P-1", "P-2"]}])
    for i, point in enumerate(plan["points"]):
        del point["configuration"]
        point.update(temperature_K=70.0 + i, voltage_per_period_V=0.05 + i * 0.01,
                     effective_inputs={
                         "temperature_K": 70.0 + i, "voltage_per_period_V": 0.05 + i * 0.01,
                         "configuration_hash": str(3 + i) * 64,
                         "hash_encoding": "qcl-negf-canonical-bytes-v1",
                         "model_sha256": "2" * 64, "axes_applied": True})
    payload = (json.dumps(plan, indent=2) + "\n").encode("utf-8")
    r["metadata"]["frozen_plan"] = {"bytes": payload, "sha256": digest(payload)}
    r.pop("point_passports")
    r["snapshot_files"] = {}
    entries = []
    for i, point in enumerate(plan["points"]):
        snap = deepcopy(c["snapshot"])
        snap["context"].update(plan_fingerprint="1" * 64, point_id=point["id"],
                               configuration_hash=str(3 + i) * 64, attempt=local_attempt)
        for leaf in snap["inputs"]:
            leaf["declared"] = {"status": "unknown", "atom": None}
        snap["inputs"][0]["used"]["atom"] = atom(0.20 + i * 0.05)
        record = blob(snap)
        inventory = {"bytes": len(record["bytes"]), "sha256": record["sha256"]}
        path = f'result/executions/E-1/{point["id"]}/attempt-{local_attempt}/model-help-inputs.json'
        r["snapshot_files"][path] = {**record, "inventory": inventory}
        entries.append({"path": path, **inventory, "execution_id": "E-1", "point_id": point["id"],
                        "attempt": local_attempt, "status": "valid", "reason": "ok"})
        if i == 0:
            c["snapshot"] = snap
            r["metadata"]["execution_input"] = record
    c["index"]["entries"] = entries
    child = {**c["snapshot"]["context"], "attempt": child_attempt,
             "run_uuid": c["view"]["context"]["run_uuid"],
             "calcjob_uuid": c["view"]["context"]["calcjob_uuid"]}
    c["view"]["context"] = deepcopy(child)
    r["selection"]["context"] = deepcopy(child)
    if capture:
        r["selection"]["capture_context"] = deepcopy(c["snapshot"]["context"])
    receipt = json.loads(r["metadata"]["release_receipt"]["bytes"])
    receipt["context"] = deepcopy(child)
    r["metadata"]["release_receipt"] = blob(receipt)
    item = c["view"]["inputs"][0]
    item["declared"] = {"status": "unknown", "atom": None, "evidence": None}
    item["used"] = {"status": "known", "atom": atom(0.20),
                    "evidence": evidence(r, "execution_input", "/inputs/0/used/atom")}
    item["value_origin"]["declared"] = unknown_origin("value_unavailable")
    return c


def replace_nested_plan(c, mutate):
    r = c["retained"]
    plan = json.loads(r["metadata"]["frozen_plan"]["bytes"])
    mutate(plan)
    payload = (json.dumps(plan, indent=2) + "\n").encode("utf-8")
    r["metadata"]["frozen_plan"] = {"bytes": payload, "sha256": digest(payload)}


def test_p10_null_and_mixed_references_keep_full_source_mapping_guards():
    c = no_reference_case()
    for path in ("physical.lattice_temperature", "production.energy_chunk"):
        row = deepcopy(c["fragment"]["inputs"][0])
        row["path"] = path
        c["fragment"]["inputs"].append(row)
    nonnull = deepcopy(case()["fragment"]["inputs"][0])
    nonnull["path"] = "physical.reference_leaf"
    c["fragment"]["inputs"].append(nonnull)
    repack(c)
    for name in ("bundle", "fragment", "view"):
        schema_validator("model-help.schema.json").validate(c[name])
        validate(c, name)
    # Source validation is still required for leaves without any reference value.
    c["fragment"]["inputs"][1]["schema_source"]["revision"] = OTHER
    repack(c)
    with pytest.raises(ContractError, match="source revision mismatch"):
        validate(c, "fragment")


@pytest.mark.parametrize("phase", ["declared", "used"])
@pytest.mark.parametrize("status", ["bound", "not_applicable"])
def test_p10_absent_reference_refuses_attribution_even_with_manufactured_receipt(phase, status):
    original = case()
    attributed = resolve(original)  # A complete nonnull fixture has healthy bound proof.
    assert attributed["status"] == "bound"
    c = no_reference_case()
    if status == "not_applicable":
        attributed = {"status": status, "origin": {"status": status, "kind": status,
                      "locators": [], "note": "Manufactured explicit inapplicability."},
                      "binding": None, "reason": status}
    elif phase == "declared":
        attributed["binding"]["phase"] = phase
    c["view"]["inputs"][0]["value_origin"][phase] = attributed
    schema_validator("model-help.schema.json").validate(c["view"])
    with pytest.raises(ContractError, match="absent reference"):
        validate(c)


@pytest.mark.parametrize("phase", ["declared", "used"])
def test_p10_absent_reference_unknown_reason_tracks_actual_phase_availability(phase):
    c = no_reference_case()
    validate(c)
    target = c["view"]["inputs"][0]
    target["value_origin"][phase] = unknown_origin("value_unavailable")
    with pytest.raises(ContractError, match="absent reference"):
        validate(c)
    target[phase] = {"status": "unknown", "atom": None, "evidence": None}
    validate(c)
    target["value_origin"][phase] = unknown_origin("source_unbound")
    with pytest.raises(ContractError, match="absent reference"):
        validate(c)


def test_p10_nullable_mapping_keeps_nonnull_reference_id_collisions_invalid():
    c = no_reference_case()
    for path in ("physical.first_reference", "physical.second_reference"):
        row = deepcopy(case()["fragment"]["inputs"][0])
        row["path"] = path
        c["fragment"]["inputs"].append(row)
    repack(c)
    with pytest.raises(ContractError, match="duplicate reference id"):
        validate(c, "fragment")


def test_p10_nonnull_origin_candidate_skips_absent_references_without_losing_proof():
    c = case()
    unreferenced = deepcopy(c["fragment"]["inputs"][0])
    unreferenced.update(path=TEMP, reference_value_origin=None)
    c["fragment"]["inputs"].insert(0, unreferenced)
    repack(c)
    bound = resolve(c)
    assert bound["status"] == "bound"
    assert bound["binding"]["reference_id"] == "pilot.ifr-height"


def test_p10_nested_original_passport_bytes_accept_unknown_declared_and_complete_index():
    c = nested_passport_case()
    before = deepcopy(c)
    original = c["retained"]["metadata"]["frozen_plan"]["bytes"]
    assert b'\n  "' in original
    plan = json.loads(original)
    assert plan["points"][0]["effective_inputs"]["configuration_hash"] == "3" * 64
    assert digest(raw(plan["points"][0]["effective_inputs"])) != "3" * 64
    for name in ("snapshot", "index", "view"):
        schema_validator("model-help.schema.json").validate(c[name])
        validate(c, name)
    assert c == before
    assert c["view"]["inputs"][0]["declared"] == {"status": "unknown", "atom": None, "evidence": None}
    assert c["view"]["inputs"][0]["used"]["atom"] == {"kind": "quantity", "value": 0.20, "unit": "nm"}


def test_p10_nested_plan_requires_its_fingerprint_instead_of_legacy_byte_digest_fallback():
    c = nested_passport_case()
    replace_nested_plan(c, lambda plan: plan.pop("fingerprint"))
    digest_as_fingerprint = c["retained"]["metadata"]["frozen_plan"]["sha256"]
    c["snapshot"]["context"]["plan_fingerprint"] = digest_as_fingerprint
    c["retained"]["selection"]["context"]["plan_fingerprint"] = digest_as_fingerprint
    c["retained"]["metadata"]["execution_input"] = blob(c["snapshot"])
    with pytest.raises(ContractError):
        validate(c, "snapshot")


@pytest.mark.parametrize("defect", [
    "null", "list", "missing_encoding", "encoding", "axes_flag", "temperature", "voltage",
    "axis_boolean", "configuration_hash", "model_sha", "science", "model_revision",
    "execution_missing", "execution_nonmember", "duplicate_point", "foreign_execution"])
def test_p10_nested_malformed_passport_cannot_fall_back_to_flat_configuration(defect):
    c = nested_passport_case()
    validate(c, "snapshot")
    def mutate(plan):
        point = plan["points"][0]
        passport = point["effective_inputs"]
        # These counterfeit legacy leaves must never hide a corrupt nested row.
        point["configuration"] = {PATH: atom()}
        plan["point"] = {"configuration": {PATH: atom()}}
        if defect == "null":
            point["effective_inputs"] = None
        elif defect == "list":
            point["effective_inputs"] = []
        elif defect == "missing_encoding":
            del passport["hash_encoding"]
        elif defect == "encoding":
            passport["hash_encoding"] = "contracts-json"
        elif defect == "axes_flag":
            passport["axes_applied"] = False
        elif defect == "temperature":
            passport["temperature_K"] = 71.0
        elif defect == "voltage":
            passport["voltage_per_period_V"] = 0.06
        elif defect == "axis_boolean":
            passport["temperature_K"] = point["temperature_K"] = True
        elif defect == "configuration_hash":
            passport["configuration_hash"] = "9" * 64
        elif defect == "model_sha":
            passport["model_sha256"] = "unrecorded"
        elif defect == "science":
            plan["scientific_fingerprint"] = "e" * 64
        elif defect == "model_revision":
            plan["model_revision"] = "other-model"
        elif defect == "execution_missing":
            plan["executions"] = []
        elif defect == "execution_nonmember":
            plan["executions"][0]["point_ids"] = ["P-2"]
        elif defect == "duplicate_point":
            plan["points"].append(deepcopy(point))
        else:
            point["execution_id"] = "E-2"
    replace_nested_plan(c, mutate)
    with pytest.raises(ContractError):
        validate(c, "snapshot")


def test_p10_nested_index_requires_each_original_point_membership_and_association():
    c = nested_passport_case()
    validate(c, "index")
    c["retained"]["point_passports"] = {
        ("E-1", "P-2"): evidence(c["retained"], "frozen_plan", "/points/0/effective_inputs")}
    with pytest.raises(ContractError, match="another frozen leaf"):
        validate(c, "index")
    del c["retained"]["point_passports"]
    replace_nested_plan(c, lambda plan: plan["executions"][0]["point_ids"].pop())
    with pytest.raises(ContractError):
        validate(c, "index")


@pytest.mark.parametrize("name", ["snapshot", "view"])
def test_p10_nested_passport_identity_never_supplies_a_declared_atom(name):
    c = nested_passport_case()
    validate(c, name)
    if name == "snapshot":
        c[name]["inputs"][0]["declared"] = {"status": "known", "atom": atom(0.20)}
        c["retained"]["metadata"]["execution_input"] = blob(c[name])
    else:
        c[name]["inputs"][0]["declared"] = {"status": "known", "atom": atom(0.20),
            "evidence": evidence(c["retained"], "frozen_plan", "/points/0/effective_inputs")}
    with pytest.raises(ContractError):
        validate(c, name)


@pytest.mark.parametrize("name", ["snapshot", "index", "view"])
def test_p10_detached_local_attempt7_preserves_transport_attempt2(name):
    c = nested_passport_case(local_attempt=7, child_attempt=2, capture=True)
    before = deepcopy(c)
    validate(c, name)
    assert c == before
    assert c["snapshot"]["context"]["attempt"] == 7
    assert c["view"]["context"]["attempt"] == 2
    del c["retained"]["selection"]["capture_context"]
    c["retained"]["selection"]["native"] = True  # A Boolean grants no provenance authority.
    with pytest.raises(ContractError, match="local context|child attempt"):
        validate(c, name)


@pytest.mark.parametrize("field,value", [
    ("plan_fingerprint", "e" * 64), ("scientific_fingerprint", "e" * 64),
    ("model_revision", "foreign"), ("execution_id", "E-2"), ("point_id", "P-2"),
    ("configuration_hash", "e" * 64)])
def test_p10_capture_context_cannot_replace_other_selected_local_fields(field, value):
    c = nested_passport_case(local_attempt=7, child_attempt=2, capture=True)
    c["retained"]["selection"]["capture_context"][field] = value
    with pytest.raises(ContractError, match="capture context"):
        validate(c)


@pytest.mark.parametrize("defect", ["null", "boolean", "missing", "uuid", "authority", "boolean_attempt"])
def test_p10_capture_context_is_exact_schema_valid_local_context(defect):
    c = nested_passport_case(local_attempt=7, child_attempt=2, capture=True)
    selection = c["retained"]["selection"]
    if defect == "null":
        selection["capture_context"] = None
    elif defect == "boolean":
        selection["capture_context"] = True
    elif defect == "missing":
        del selection["capture_context"]["attempt"]
    elif defect == "uuid":
        selection["capture_context"]["calcjob_uuid"] = c["view"]["context"]["calcjob_uuid"]
    elif defect == "authority":
        selection["capture_context"]["owner_verified"] = True
    else:
        selection["capture_context"]["attempt"] = True
    with pytest.raises(ContractError, match="capture context"):
        validate(c)


def origin_capture_conflict_case():
    """A healthy old bound proof followed by actual capture13/transport1.

    Keep receipt attempt1 untouched. Rebind only the exact scalar/condition
    Evidence digests to the newly closed Snapshot bytes, so a stale digest
    cannot mask the missing receipt-to-capture check.
    """
    c = case()
    bound = resolve(c)
    assert bound["status"] == "bound"
    c["snapshot"]["context"]["attempt"] = 13
    c["retained"]["selection"]["capture_context"] = deepcopy(c["snapshot"]["context"])
    c["retained"]["metadata"]["execution_input"] = blob(c["snapshot"])
    c["view"]["inputs"][0]["used"]["evidence"] = evidence(
        c["retained"], "execution_input", "/inputs/0/used/atom")
    for proof in (bound["binding"]["value"], *bound["binding"]["conditions"]):
        if proof["container"] == "execution_input":
            proof["sha256"] = c["retained"]["metadata"]["execution_input"]["sha256"]
    c["view"]["inputs"][0]["value_origin"]["used"] = bound
    return c


def test_f1_used_resolver_rejects_receipt_for_transport_instead_of_actual_capture():
    c = origin_capture_conflict_case()
    before = deepcopy(c)
    schema_validator("model-help.schema.json").validate(c["snapshot"])
    with pytest.raises(ContractError, match="snapshot claim context mismatch"):
        validate(c, "snapshot")
    with pytest.raises(ContractError, match="captured context mismatch"):
        resolve(c)
    assert c == before


def json_source_case(payload, pointer):
    """Add a reviewed detached JSON source to the complete public bundle fixture."""
    c = case()
    retained = c["retained"]
    path = "docs/help/authored.json"
    retained["sources"][(COMPONENT, path)] = {"revision": OWNER, "bytes": payload}
    source = ref(retained["sources"], path, "json_pointer", pointer)
    retained["input_allowlist"] += ((COMPONENT, path),)
    retained["selector_allowlist"] += ((COMPONENT, path, "json_pointer", pointer),)
    retained["public_reviews"] += ({"source": ref(retained["sources"], path),
        "recipe": c["bundle"]["generator"]["recipes"][0],
        "receipt": {"bytes": b"review", "sha256": digest(b"review")}},)
    return c, source


@pytest.mark.parametrize("payload,pointer", [
    (b'[{"inputs":[{"x":1}]}]', '/0/inputs/0'),
    (b'{"nested":[{"a/b":{"~key":1}}]}', '/nested/0/a~1b/~0key'),
    (b'42', ''),
])
def test_public_bundle_accepts_reviewed_json_source_values(payload, pointer):
    from qcl_negf_contracts.model_help import validate_documentation_bundle
    c, source = json_source_case(payload, pointer)
    before = deepcopy((c["bundle"], c["retained"], source))
    result = validate_documentation_bundle(c["bundle"], retained=c["retained"], required_sources=[source])
    assert result is c["bundle"]
    assert (c["bundle"], c["retained"], source) == before


@pytest.mark.parametrize("payload,pointer", [
    (b'[1]', '/01'), (b'[1]', '/-1'), (b'[1]', '/1'),
    (b'[1]', '/x'), (b'[1]', '/0/~2'), (b'42', '/0'),
    (b'\xff', ''), (b'[', ''), (b'[{"x":1,"x":2}]', '/0'),
    (b'[NaN]', '/0'), (b'[Infinity]', '/0'),
    (b'[' * 66 + b'0' + b']' * 66, ''),
    (b' ' * (8 * 1024 * 1024) + b'0', ''),
])
def test_public_bundle_rejects_invalid_reviewed_json_source(payload, pointer):
    from qcl_negf_contracts.model_help import validate_documentation_bundle
    c, source = json_source_case(payload, pointer)
    with pytest.raises(ContractError):
        validate_documentation_bundle(c["bundle"], retained=c["retained"], required_sources=[source])


@pytest.mark.parametrize("failure", ["hash", "revision", "allowlist", "selector", "review"])
def test_public_bundle_checks_source_provenance_before_json_decoding(failure):
    from qcl_negf_contracts.model_help import DocumentationProofMissing, validate_documentation_bundle
    c, source = json_source_case(b'not JSON', '')
    retained = c["retained"]
    if failure == "hash":
        source["sha256"] = "0" * 64
    elif failure == "revision":
        source["revision"] = OTHER
    elif failure == "allowlist":
        retained["input_allowlist"] = tuple(x for x in retained["input_allowlist"] if x != (COMPONENT, source["path"]))
    elif failure == "selector":
        retained["selector_allowlist"] = tuple(x for x in retained["selector_allowlist"] if x[1] != source["path"])
    else:
        retained["public_reviews"] = tuple(x for x in retained["public_reviews"] if x["source"]["path"] != source["path"])
    expected = {"hash": "hash mismatch", "revision": "revision mismatch", "allowlist": "input allowlist",
                "selector": "selector is outside", "review": "proof is missing"}[failure]
    with pytest.raises((ContractError, DocumentationProofMissing), match=expected):
        validate_documentation_bundle(c["bundle"], retained=retained, required_sources=[source])


@pytest.mark.parametrize("payload", [
    b'[' * 64 + b'0' + b']' * 64,
    b' ' * (8 * 1024 * 1024 - 1) + b'0',
])
def test_public_bundle_accepts_source_at_json_limits(payload):
    from qcl_negf_contracts.model_help import validate_documentation_bundle
    c, source = json_source_case(payload, '')
    assert validate_documentation_bundle(c["bundle"], retained=c["retained"], required_sources=[source]) is c["bundle"]


def test_public_bundle_source_uses_only_retained_bytes_without_executing_or_mutating(monkeypatch):
    import builtins
    import os
    import subprocess
    from qcl_negf_contracts.model_help import validate_documentation_bundle
    c, source = json_source_case(b'[{"command":"must never run"}]', '/0/command')
    before = deepcopy((c["bundle"], c["retained"], source))
    original_open = builtins.open

    def guarded_open(path, *args, **kwargs):
        assert not str(path).endswith(source["path"]), "source path opened"
        return original_open(path, *args, **kwargs)

    def forbidden(*args, **kwargs):
        pytest.fail("source execution attempted")

    monkeypatch.setattr(builtins, "open", guarded_open)
    monkeypatch.setattr(os, "system", forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    assert validate_documentation_bundle(c["bundle"], retained=c["retained"], required_sources=[source]) is c["bundle"]
    assert (c["bundle"], c["retained"], source) == before
