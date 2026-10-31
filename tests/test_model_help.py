"""DOC07 C1 shape controls; synthetic records never establish binding proof.

The five public documents below are authored from DOC03, not from schema defs.
C2 must separately check selected retained bytes/context/last assignment. In
particular a literal ``bound`` below is only a structurally healthy record.
"""
from __future__ import annotations

from copy import deepcopy

import pytest

from qcl_negf_contracts import load_schema, schema_names, schema_validator
from qcl_negf_contracts.messages import ContractError, decode, encode, validate_json


RESOURCE = "model-help.schema.json"
SHA1 = "a" * 40
SHA256 = "b" * 64
FACT_NAMES = (
    "signature", "units", "default", "constraint", "effects", "errors",
    "formula_origin", "value_origin", "assigning_origin", "effective_origin",
)
FORMATS = {
    "bundle": "qcl-negf.docs-bundle.v1",
    "fragment": "qcl-negf.model-help-fragment.v1",
    "view": "qcl-negf.model-help-view.v1",
    "snapshot": "qcl-negf.model-help-inputs.v1",
    "index": "qcl-negf.model-help-index.v1",
}


def public_ref(kind="file", value=""):
    return {"component": "components/qcl-negf-research", "revision": SHA1,
            "path": "parameters/pilot.json", "selector": {"kind": kind, "value": value},
            "sha256": SHA256}


def doc_ref():
    return {"section": "research", "path": "model.html", "anchor": "pilot"}


def atom():
    return {"kind": "quantity", "value": 70.0, "unit": "K"}


def origin(status="known"):
    if status == "unknown":
        return {"status": "unknown", "kind": "unknown", "locators": [],
                "note": "Retained origin assignment receipt is absent."}
    if status == "not_applicable":
        return {"status": "not_applicable", "kind": "not_applicable", "locators": [],
                "note": "Explicitly inapplicable in the owning synthetic example."}
    return {"status": "known", "kind": "publication", "locators": [
        {"title": "Synthetic source", "uri": "https://example.org/paper", "location": "Table 1"}],
        "note": "Shape fixture only; no scientific attribution is established."}


def facts():
    return [{"name": name, "status": "unknown", "text": None, "sources": [public_ref()]}
            for name in FACT_NAMES]


def evidence():
    return {"container": "execution_input", "sha256": SHA256, "selector": "/inputs/0/used"}


def local_context():
    return {"plan_fingerprint": SHA256, "scientific_fingerprint": SHA256,
            "model_revision": "synthetic-model-v1", "execution_id": "E-1",
            "point_id": "P-1", "attempt": 1, "configuration_hash": SHA256}


def value_origin_binding():
    return {"reference_id": "pilot.temperature", "annotation": public_ref("json_pointer", "/origin"),
            "parameter": public_ref("json_pointer", "/temperature"), "phase": "used",
            "value": evidence(), "assignment": evidence(), "conditions": [evidence()],
            "receipt": evidence()}


def value_origin(status="bound"):
    return {"status": status, "origin": origin("known" if status == "bound" else status),
            "binding": value_origin_binding() if status == "bound" else None,
            "reason": {"bound": "ok", "unknown": "origin_not_recorded",
                       "not_applicable": "not_applicable"}[status]}


def bundle():
    return {
        "format": FORMATS["bundle"],
        "sources": {"format": "qcl-negf.git-graph.v1", "revision": SHA1, "components": [
            {"path": "components/qcl-negf-research", "revision": SHA1,
             "url": "https://example.org/research.git"}]},
        "schema": {**public_ref(), "component": "components/qcl-negf-contracts",
                   "path": "src/qcl_negf_contracts/schemas/model-help.schema.json"},
        "generator": {"name": "Documenter", "version": "1.17.0",
                      "uuid": "e30172f5-a6a5-5a46-863b-614d45cd2de4",
                      "git_tree_sha1": "56e9c37b5e7c3b4f080ab1da18d72d5c290e184a",
                      "julia_version": "1.13.0", "project_sha256": SHA256,
                      "manifest_sha256": SHA256, "recipes": [public_ref()],
                      "toolchain_lock": public_ref()},
        "fragments": [{"id": "pilot.temperature", "file": "help/fragments/pilot.temperature.json",
                       "sha256": SHA256}],
        "files": [{"path": "help/fragments/pilot.temperature.json",
                   "media_type": "application/json", "bytes": 1024, "sha256": SHA256}],
        "aliases": [{"from": doc_ref(), "to": doc_ref()}],
    }


def fragment():
    return {
        "format": FORMATS["fragment"], "id": "pilot.temperature", "source_revision": SHA1,
        "title": "Lattice temperature", "summary": "Synthetic shape example.", "scope": "baseline",
        "meaning_source": public_ref(), "full": doc_ref(), "related": [doc_ref()],
        "equations": [{"id": "AUTHORED-EQUATION", "doc": doc_ref()}],
        "inputs": [{"path": "physical.lattice_temperature",
                    "schema_source": public_ref("json_pointer", "/properties/physical/properties/lattice_temperature"),
                    "facts": facts(), "reference_value_origin": {
                        "id": "pilot.temperature", "parameter": public_ref("json_pointer", "/temperature"),
                        "atom": atom(), "applicability": {"status": "specified", "conditions": [
                            {"id": "pilot.condition", "path": "physical.lattice_temperature",
                             "relation": "equal", "atom": atom(), "source": public_ref()}], "note": ""},
                        "origin": origin()}}],
        "api": [{"symbol": "PhysicalParameters", "source": public_ref("symbol", "PhysicalParameters"),
                 "doc": doc_ref(), "facts": facts()}],
        "assumptions": ["Synthetic authored assumption."], "limitations": ["No binding proof."],
    }


def view():
    return {
        "format": FORMATS["view"],
        "context": {**local_context(), "run_uuid": "12345678-1234-4234-8234-123456789abc",
                    "calcjob_uuid": "abcdefab-1234-4234-8234-123456789abc"},
        "binding": {"status": "bound", "release_id": "release-pilot-1",
                    "release_manifest_sha256": SHA256, "source_revision": SHA1,
                    "bundle_sha256": SHA256, "reason": "ok"},
        "fragment": {"id": "pilot.temperature",
                     "url": "/docs/" + SHA1 + "/help/fragments/pilot.temperature.json", "sha256": SHA256},
        "inputs": [{"path": "physical.lattice_temperature",
                    "declared": {"status": "known", "atom": atom(), "evidence": evidence()},
                    "used": {"status": "known", "atom": atom(), "evidence": evidence()},
                    "assigning": {"status": "known", "kind": "config_file", "source": public_ref(),
                                  "rule": None, "evidence": evidence()},
                    "effective_origin": {"status": "partial", "evidence": [evidence()]},
                    "value_origin": {"declared": value_origin(), "used": value_origin()}}],
        "input_status": {"status": "available", "reason": "ok"},
    }


def snapshot():
    return {
        "format": FORMATS["snapshot"], "context": local_context(), "phase": "solver_input",
        "inputs": [{"path": "physical.lattice_temperature",
                    "declared": {"status": "known", "atom": atom()},
                    "used": {"status": "known", "atom": atom()},
                    "assigning": {"status": "known", "kind": "config_file", "source": public_ref(), "rule": None},
                    "effective_origin": {"status": "partial", "steps": [
                        {"kind": "configuration_merge", "source": public_ref(), "rule": None}]}}],
        "origin_bindings": [{"reference_id": "pilot.temperature", "annotation": public_ref("json_pointer", "/origin"),
                             "parameter": public_ref("json_pointer", "/temperature"), "phase": "used",
                             "assignment_receipt": {"source": public_ref(), "source_sha256": SHA256,
                                 "leaf_pointer": "/configuration/physical/lattice_temperature",
                                 "capture": "retained_public_source_binding", "plan_fingerprint": SHA256,
                                 "execution_id": "E-1", "point_id": "P-1", "attempt": 1},
                             "conditions": [{"id": "pilot.condition", "input_path": "physical.lattice_temperature",
                                             "phase": "used"}]}],
    }


def index():
    return {"format": FORMATS["index"], "complete": True, "entries": [{
        "path": "result/executions/E-1/P-1/attempt-1/model-help-inputs.json", "bytes": 1024,
        "sha256": SHA256, "execution_id": "E-1", "point_id": "P-1", "attempt": 1,
        "status": "valid", "reason": "ok"}]}


FACTORIES = {"bundle": bundle, "fragment": fragment, "view": view, "snapshot": snapshot, "index": index}


@pytest.fixture(scope="module")
def validator():
    return schema_validator(RESOURCE)


def object_paths(item, prefix=()):
    """Enumerate authored object instances, including every exercised leaf type."""
    if isinstance(item, dict):
        yield prefix
        for key, child in item.items():
            yield from object_paths(child, (*prefix, key))
    elif isinstance(item, list):
        for position, child in enumerate(item):
            yield from object_paths(child, (*prefix, position))


def at(item, path):
    for segment in path:
        item = item[segment]
    return item


def assert_bad(validator, healthy, path, replacement):
    validator.validate(healthy)
    changed = deepcopy(healthy)
    at(changed, path[:-1])[path[-1]] = replacement
    assert not validator.is_valid(changed), (path, replacement)


def test_resource_name_and_offline_local_refs():
    assert RESOURCE in schema_names()
    schema = load_schema(RESOURCE)
    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    for path in object_paths(schema):
        node = at(schema, path)
        for key in ("$ref", "$dynamicRef"):
            if key in node:
                assert node[key].startswith("#"), (path, node[key])
    for name in ("../model-help.schema.json", "schemas/model-help.schema.json"):
        with pytest.raises(ValueError, match="unknown schema resource"):
            load_schema(name)
    # Existing adapter's registry resolves these fixtures without any remote retrieval.
    for factory in FACTORIES.values():
        schema_validator(RESOURCE).validate(factory())


@pytest.mark.parametrize("name", FORMATS)
def test_all_five_complete_authored_formats(validator, name):
    healthy = FACTORIES[name]()
    assert healthy["format"] == FORMATS[name]
    validator.validate(decode(encode(healthy)))
    assert_bad(validator, healthy, ("format",), FORMATS[name] + ".unsupported")
    for invalid in (None, [], True, 1, "document"):
        assert not validator.is_valid(invalid)


@pytest.mark.parametrize("name", FORMATS)
def test_every_exercised_object_is_closed_and_all_fields_required(validator, name):
    healthy = FACTORIES[name]()
    validator.validate(healthy)
    for path in object_paths(healthy):
        extra = deepcopy(healthy)
        at(extra, path)["unexpected_field"] = "must be rejected"
        assert not validator.is_valid(extra), (name, path, "extra")
        for field in at(healthy, path):
            missing = deepcopy(healthy)
            del at(missing, path)[field]
            assert not validator.is_valid(missing), (name, path, field, "required")


@pytest.mark.parametrize("collection", ["inputs", "api"])
@pytest.mark.parametrize("missing", FACT_NAMES)
def test_all_ten_fact_classes_are_required(validator, collection, missing):
    healthy = fragment()
    validator.validate(healthy)
    changed = deepcopy(healthy)
    changed[collection][0]["facts"] = [row for row in changed[collection][0]["facts"] if row["name"] != missing]
    assert not validator.is_valid(changed)


@pytest.mark.parametrize("collection", ["inputs", "api"])
def test_repeated_fact_names_allow_distinct_authored_contexts(validator, collection):
    healthy = fragment()
    healthy[collection][0]["facts"].extend([
        {"name": "default", "status": "known", "text": "Schema default context: synthetic 64.", "sources": [public_ref()]},
        {"name": "default", "status": "known", "text": "Typed-constructor context: synthetic 128.", "sources": [public_ref()]},
        {"name": "default", "status": "known", "text": "Example context: synthetic 32.", "sources": [public_ref()]},
    ])
    validator.validate(healthy)
    assert_bad(validator, healthy, (collection, 0, "facts", 0, "name"), "invented_fact")
    assert_bad(validator, healthy, (collection, 0, "facts", 0, "status"), "pass")


@pytest.mark.parametrize("collection", ["inputs", "api"])
@pytest.mark.parametrize("status", ["known", "partial", "unknown", "not_assigned", "not_applicable"])
def test_all_accepted_fact_statuses(validator, collection, status):
    healthy = fragment()
    healthy[collection][0]["facts"][0]["status"] = status
    validator.validate(healthy)
    assert_bad(validator, healthy, (collection, 0, "facts", 0, "status"), "pass")


@pytest.mark.parametrize("kind,value,unit", [
    ("quantity", 70.0, "K"), ("integer", 64, "1"), ("number", 0.5, None),
    ("boolean", True, None), ("enum", "baseline", None), ("null", None, None),
])
def test_scalar_atom_kinds_and_known_null(validator, kind, value, unit):
    healthy = fragment()
    healthy["inputs"][0]["reference_value_origin"]["atom"] = {"kind": kind, "value": value, "unit": unit}
    validator.validate(healthy)
    for invalid in ([], {}, {"value": 1}):
        assert_bad(validator, healthy, ("inputs", 0, "reference_value_origin", "atom", "value"), invalid)
    if kind == "null":
        # A known null Atom remains an object; it is not the missing-state null.
        known = view()
        known["inputs"][0]["used"]["atom"] = {"kind": "null", "value": None, "unit": None}
        validator.validate(known)


@pytest.mark.parametrize("kind,value,unit", [
    ("quantity", True, "K"), ("quantity", "70", "K"), ("quantity", 70, None),
    ("quantity", 70, ""), ("integer", True, "1"), ("integer", 1.5, "1"),
    ("number", False, None), ("boolean", 1, None), ("enum", 1, None),
    ("null", 0, None), ("array", [], None), ("number", 1, 1),
])
def test_atom_type_cross_pairs_rejected(validator, kind, value, unit):
    assert_bad(validator, fragment(), ("inputs", 0, "reference_value_origin", "atom"),
               {"kind": kind, "value": value, "unit": unit})


@pytest.mark.parametrize("number", [float("nan"), float("inf"), float("-inf")])
def test_finite_python_boundary_precedes_schema(number):
    healthy = fragment()
    assert validate_json(healthy) == healthy
    healthy["inputs"][0]["reference_value_origin"]["atom"]["value"] = number
    with pytest.raises(ContractError, match="finite"):
        validate_json(healthy)
    with pytest.raises(ContractError, match="finite"):
        encode(healthy)


@pytest.mark.parametrize("token", [b"NaN", b"Infinity", b"-Infinity", b"1e400"])
def test_finite_decoded_atom_boundary(token):
    healthy = encode(fragment())
    assert b'"value":70.0' in healthy
    assert decode(healthy)["format"] == FORMATS["fragment"]
    with pytest.raises(ContractError, match="finite"):
        decode(healthy.replace(b'"value":70.0', b'"value":' + token, 1))


@pytest.mark.parametrize("status", ["known", "unknown", "not_applicable"])
def test_origin_status_matrix(validator, status):
    healthy = fragment()
    healthy["inputs"][0]["reference_value_origin"]["origin"] = origin(status)
    validator.validate(healthy)
    path = ("inputs", 0, "reference_value_origin", "origin")
    for other in ({"known", "unknown", "not_applicable"} - {status}):
        assert_bad(validator, healthy, (*path, "status"), other)
    if status == "unknown":
        assert_bad(validator, healthy, (*path, "note"), "")
    if status != "known":
        assert_bad(validator, healthy, (*path, "locators"), origin()["locators"])


def test_known_origin_does_not_require_doi_or_infer_measurement(validator):
    healthy = fragment()
    target = healthy["inputs"][0]["reference_value_origin"]["origin"]
    for kind in ("publication", "measurement", "interpolation", "fit", "code_policy"):
        target.update(status="known", kind=kind, locators=[], note="")
        validator.validate(healthy)
    target.update(kind="research_assumption", note="Explicit synthetic owning assumption.")
    validator.validate(healthy)
    assert_bad(validator, healthy, ("inputs", 0, "reference_value_origin", "origin", "note"), "")


@pytest.mark.parametrize("status,reasons", [
    ("bound", ["ok"]),
    ("unknown", ["origin_not_recorded", "override_unbound", "conditions_unbound", "source_unbound", "value_unavailable"]),
    ("not_applicable", ["not_applicable"]),
])
def test_value_origin_shape_status_reason_matrix(validator, status, reasons):
    all_reasons = {"ok", "origin_not_recorded", "override_unbound", "conditions_unbound",
                   "source_unbound", "value_unavailable", "not_applicable"}
    for phase in ("declared", "used"):
        healthy = view()
        healthy["inputs"][0]["value_origin"][phase] = value_origin(status)
        target = healthy["inputs"][0]["value_origin"][phase]
        path = ("inputs", 0, "value_origin", phase)
        for reason in reasons:
            target["reason"] = reason
            validator.validate(healthy)
        for reason in all_reasons - set(reasons):
            assert_bad(validator, healthy, (*path, "reason"), reason)
        assert_bad(validator, healthy, (*path, "binding"), None if status == "bound" else value_origin_binding())
        for other in {"known", "unknown", "not_applicable"} - {target["origin"]["status"]}:
            assert_bad(validator, healthy, (*path, "origin"), origin(other))


@pytest.mark.parametrize("status,reasons", [
    ("bound", ["ok"]), ("unknown", ["source_binding_missing"]),
    ("incompatible", ["wrong_release", "unsupported_version"]),
    ("unavailable", ["bundle_missing", "fragment_missing"]),
])
def test_documentation_binding_shape_status_reason_null_matrix(validator, status, reasons):
    healthy = view()
    healthy["binding"].update(status=status, reason=reasons[0])
    if status != "bound":
        healthy["fragment"] = None
    all_reasons = {"ok", "source_binding_missing", "wrong_release", "unsupported_version", "bundle_missing", "fragment_missing"}
    for reason in reasons:
        healthy["binding"]["reason"] = reason
        validator.validate(healthy)
    for reason in all_reasons - set(reasons):
        assert_bad(validator, healthy, ("binding", "reason"), reason)
    assert_bad(validator, healthy, ("fragment",), None if status == "bound" else view()["fragment"])
    if status == "bound":
        assert_bad(validator, healthy, ("binding", "release_id"), "")
    for field in ("release_id", "release_manifest_sha256", "source_revision", "bundle_sha256"):
        changed = deepcopy(healthy)
        changed["binding"][field] = None
        if status == "bound":
            assert not validator.is_valid(changed)
        else:
            # Each known retained scalar may survive independently on unbound branches.
            validator.validate(changed)


@pytest.mark.parametrize("status,reasons", [
    ("available", ["ok"]), ("invalid", ["snapshot_invalid"]),
    ("unavailable", ["snapshot_missing", "point_not_executed_by_selected_child", "inventory_unavailable", "inventory_incomplete"]),
])
def test_input_status_shape_matrix(validator, status, reasons):
    healthy = view()
    if status != "available":
        healthy["inputs"][0]["used"] = {"status": "unknown", "atom": None, "evidence": None}
        healthy["inputs"][0]["value_origin"]["used"] = value_origin("unknown")
    healthy["input_status"]["status"] = status
    all_reasons = {"ok", "snapshot_invalid", "snapshot_missing", "point_not_executed_by_selected_child",
                   "inventory_unavailable", "inventory_incomplete"}
    for reason in reasons:
        healthy["input_status"]["reason"] = reason
        validator.validate(healthy)
    for reason in all_reasons - set(reasons):
        assert_bad(validator, healthy, ("input_status", "reason"), reason)
    if status != "available":
        assert_bad(validator, healthy, ("inputs", 0, "used"), view()["inputs"][0]["used"])


def test_available_snapshot_with_empty_projection_and_unbound_docs_is_shape_valid(validator):
    healthy = view()
    healthy["binding"].update(status="unknown", reason="source_binding_missing")
    healthy.update(fragment=None, inputs=[])
    validator.validate(healthy)
    assert healthy["input_status"] == {"status": "available", "reason": "ok"}
    # Exact retained mapping and historical/source proof are C2, not schema inferences.


@pytest.mark.parametrize("name", ["view", "snapshot"])
@pytest.mark.parametrize("phase", ["declared", "used"])
def test_scalar_known_unknown_null_obligations(validator, name, phase):
    healthy = FACTORIES[name]()
    path = ("inputs", 0, phase)
    assert_bad(validator, healthy, (*path, "atom"), None)
    if name == "view":
        assert_bad(validator, healthy, (*path, "evidence"), None)
    healthy["inputs"][0][phase] = {"status": "unknown", "atom": None}
    if name == "view":
        healthy["inputs"][0][phase]["evidence"] = None
    validator.validate(healthy)
    assert_bad(validator, healthy, (*path, "atom"), atom())
    if name == "view":
        assert_bad(validator, healthy, (*path, "evidence"), evidence())


@pytest.mark.parametrize("name", ["view", "snapshot"])
def test_assigning_source_or_rule_unknown_and_redacted_matrix(validator, name):
    healthy = FACTORIES[name]()
    path = ("inputs", 0, "assigning")
    for source, rule in ((public_ref(), None), (None, "runner.config.merge"), (public_ref(), "runner.config.merge")):
        healthy["inputs"][0]["assigning"].update(source=source, rule=rule)
        validator.validate(healthy)
    changed = deepcopy(healthy)
    changed["inputs"][0]["assigning"].update(source=None, rule=None)
    assert not validator.is_valid(changed)
    if name == "view":
        assert_bad(validator, healthy, (*path, "evidence"), None)
    target = {"status": "unknown", "kind": "unknown", "source": None, "rule": None}
    if name == "view":
        target["evidence"] = None
    healthy["inputs"][0]["assigning"] = target
    validator.validate(healthy)
    for field, invalid in (("kind", "typed_constructor"), ("source", public_ref()), ("rule", "runner.config.merge")):
        assert_bad(validator, healthy, (*path, field), invalid)
    if name == "view":
        assert_bad(validator, healthy, (*path, "evidence"), evidence())
    target.update(status="redacted", kind="config_file")
    validator.validate(healthy)
    assert_bad(validator, healthy, (*path, "source"), public_ref())


@pytest.mark.parametrize("name", ["view", "snapshot"])
def test_context_identity_scalar_types(validator, name):
    healthy = FACTORIES[name]()
    for field in ("plan_fingerprint", "scientific_fingerprint", "configuration_hash"):
        assert_bad(validator, healthy, ("context", field), "B" * 64)
    for field in ("execution_id", "point_id"):
        for invalid in ("", "a/b", "a b", ".start", "a" * 129):
            assert_bad(validator, healthy, ("context", field), invalid)
    for invalid in (0, -1, True, "1", 1.5):
        assert_bad(validator, healthy, ("context", "attempt"), invalid)
    assert_bad(validator, healthy, ("context", "model_revision"), "")
    healthy["context"]["configuration_hash"] = None
    validator.validate(healthy)
    if name == "view":
        for field in ("run_uuid", "calcjob_uuid"):
            for invalid in (None, "1234", "12345678123442348234123456789abc", "ABCDEFAB-1234-4234-8234-123456789ABC"):
                assert_bad(validator, healthy, ("context", field), invalid)


def test_snapshot_is_local_closed_and_has_no_api_origin_fields(validator):
    healthy = snapshot()
    healthy["origin_bindings"] = []  # Existing snapshots without capture receipts stay legitimate.
    validator.validate(healthy)
    assert_bad(validator, healthy, ("phase",), "before_restore")
    for field in ("run_uuid", "calcjob_uuid", "release_id", "source_revision", "bundle_sha256"):
        changed = deepcopy(healthy)
        changed["context"][field] = None
        assert not validator.is_valid(changed)
    for field, value in (("value_origin", {"declared": value_origin("unknown"), "used": value_origin("unknown")}),
                         ("evidence", evidence())):
        changed = deepcopy(healthy)
        changed["inputs"][0][field] = value
        assert not validator.is_valid(changed)
    assert_bad(validator, snapshot(), ("origin_bindings", 0, "assignment_receipt", "capture"), "inferred_from_filename")


def test_applicability_unknown_has_explicit_note(validator):
    healthy = fragment()
    healthy["inputs"][0]["reference_value_origin"]["applicability"].update(
        status="unknown", conditions=[], note="Authored applicability conditions are unavailable.")
    validator.validate(healthy)
    assert_bad(validator, healthy, ("inputs", 0, "reference_value_origin", "applicability", "note"), "")


@pytest.mark.parametrize("kind", ["configuration_merge", "point_axis", "execution_strategy", "checkpoint_restore"])
def test_snapshot_effective_step_kinds(validator, kind):
    healthy = snapshot()
    healthy["inputs"][0]["effective_origin"]["steps"][0]["kind"] = kind
    validator.validate(healthy)
    assert_bad(validator, healthy, ("inputs", 0, "effective_origin", "steps", 0, "kind"), "guessed_history")


@pytest.mark.parametrize("status,reason", [
    ("valid", "ok"), ("invalid", "malformed"), ("invalid", "identity_mismatch"),
    ("invalid", "too_large"), ("invalid", "unsupported_version"),
])
def test_index_entry_status_reason_matrix_and_oversized_measurement(validator, status, reason):
    healthy = index()
    healthy["entries"][0].update(status=status, reason=reason)
    if reason == "too_large":
        healthy["entries"][0]["bytes"] = 65537
    validator.validate(healthy)
    assert_bad(validator, healthy, ("entries", 0, "reason"), "malformed" if status == "valid" else "ok")
    assert_bad(validator, healthy, ("entries", 0, "bytes"), True)
    assert_bad(validator, healthy, ("entries", 0, "bytes"), -1)
    assert_bad(validator, healthy, ("complete",), "true")
    healthy.update(complete=False, entries=[])
    validator.validate(healthy)  # No trust/scientific acceptance follows from shape validity.


@pytest.mark.parametrize("path", [
    "result/executions/E-1/P-1/attempt-0/model-help-inputs.json",
    "result/executions/E-1/P-1/attempt-01/model-help-inputs.json",
    "result/executions/E-1/P-1/attempt--1/model-help-inputs.json",
    "result/executions/E-1/P-1/attempt-1/model_help_inputs.json",
    "result/executions/E-1/P-1/attempt-1/model-help-inputs.json/extra",
    "/result/executions/E-1/P-1/attempt-1/model-help-inputs.json",
    "result/executions/../P-1/attempt-1/model-help-inputs.json",
])
def test_index_exact_logical_path_grammar(validator, path):
    assert_bad(validator, index(), ("entries", 0, "path"), path)


@pytest.mark.parametrize("field,invalid", [
    ("title", "x" * 161), ("summary", "x" * 1601), ("related", [doc_ref()] * 13),
    ("assumptions", ["a"] * 13), ("limitations", ["a" * 401]),
    ("id", "Uppercase"), ("id", "a" * 129), ("scope", "enabled"),
    ("source_revision", "a" * 39), ("source_revision", "A" * 40),
])
def test_fragment_explicit_limits_and_identifiers(validator, field, invalid):
    assert_bad(validator, fragment(), (field,), invalid)


def test_unicode_limits_count_characters_and_not_bytes(validator):
    healthy = fragment()
    healthy.update(title="Δ" * 160, summary="Ж" * 1600, assumptions=["λ" * 400] * 12)
    validator.validate(healthy)


def test_declared_array_caps(validator):
    healthy = bundle()
    healthy["fragments"] = [{"id": f"pilot.{i}", "file": f"help/fragments/pilot.{i}.json", "sha256": SHA256}
                            for i in range(256)]
    validator.validate(healthy)
    additional_fragment = {"id": "pilot.256", "file": "help/fragments/pilot.256.json", "sha256": SHA256}
    assert_bad(validator, healthy, ("fragments",), healthy["fragments"] + [additional_fragment])
    healthy = view()
    template = healthy["inputs"][0]
    healthy["inputs"] = [{**deepcopy(template), "path": f"physical.public_leaf_{i}"} for i in range(32)]
    validator.validate(healthy)
    additional_input = {**deepcopy(template), "path": "physical.public_leaf_32"}
    assert_bad(validator, healthy, ("inputs",), healthy["inputs"] + [additional_input])
    healthy = index()
    template = healthy["entries"][0]
    healthy["entries"] = [{**template, "point_id": f"P-{i}",
                           "path": f"result/executions/E-1/P-{i}/attempt-1/model-help-inputs.json"}
                          for i in range(10000)]
    validator.validate(healthy)
    additional_entry = {**template, "point_id": "P-10000",
                        "path": "result/executions/E-1/P-10000/attempt-1/model-help-inputs.json"}
    assert_bad(validator, healthy, ("entries",), healthy["entries"] + [additional_entry])
    healthy = fragment()
    condition = healthy["inputs"][0]["reference_value_origin"]["applicability"]["conditions"][0]
    conditions = [{**deepcopy(condition), "id": f"pilot.condition-{i}"} for i in range(12)]
    healthy["inputs"][0]["reference_value_origin"]["applicability"]["conditions"] = conditions
    validator.validate(healthy)
    assert_bad(validator, healthy, ("inputs", 0, "reference_value_origin", "applicability", "conditions"), conditions + [condition])


def test_reference_shapes_hashes_selectors_and_no_eight_leaf_global_enum(validator):
    healthy = fragment()
    healthy["inputs"][0]["path"] = "physical.future_public_leaf"
    validator.validate(healthy)
    assert_bad(validator, healthy, ("meaning_source", "revision"), "a" * 41)
    for invalid in ("B" * 64, "b" * 63, "b" * 65, None):
        assert_bad(validator, healthy, ("meaning_source", "sha256"), invalid)
    assert_bad(validator, healthy, ("meaning_source", "selector", "value"), "nonempty-file-selector")
    assert_bad(validator, healthy, ("meaning_source", "selector", "kind"), "line_number")
    assert_bad(validator, healthy, ("inputs", 0, "schema_source", "selector", "kind"), "symbol")
    assert_bad(validator, healthy, ("full", "section"), "portal")
    assert_bad(validator, healthy, ("full", "path"), "model.md")
    healthy["full"]["anchor"] = None
    healthy["inputs"][0]["reference_value_origin"]["applicability"].update(conditions=[], note="")
    validator.validate(healthy)  # No universal mandatory material/temperature condition.
    assert_bad(validator, healthy, ("inputs", 0, "reference_value_origin", "applicability", "status"), "pass")


@pytest.mark.parametrize("path", [("sources", "revision"), ("sources", "components", 0, "revision")])
@pytest.mark.parametrize("invalid", ["a" * 39, "a" * 41, "A" * 40, "g" * 40, "a" * 40 + "\n"])
def test_bundle_graph_root_and_component_sha_grammar(validator, path, invalid):
    healthy = bundle()
    validator.validate(healthy)
    assert_bad(validator, healthy, path, invalid)


def test_bundle_pinned_generator_and_inventory_types(validator):
    healthy = bundle()
    for field in ("name", "version", "uuid", "git_tree_sha1", "julia_version"):
        assert_bad(validator, healthy, ("generator", field), "unsupported")
    assert_bad(validator, healthy, ("files", 0, "bytes"), -1)
    assert_bad(validator, healthy, ("files", 0, "bytes"), True)
    healthy["files"][0]["bytes"] = 0
    validator.validate(healthy)
    assert_bad(validator, healthy, ("sources", "format"), "qcl-negf.manual-source-lock.v1")
    assert_bad(validator, view(), ("fragment", "url"), "/docs/current/help/fragments/pilot.temperature.json")


# Independent C1 review regression controls: canonical R3 and exact token grammar.
@pytest.mark.parametrize("status,reason", [
    ("invalid", "snapshot_invalid"),
    ("unavailable", "snapshot_missing"),
    ("unavailable", "point_not_executed_by_selected_child"),
    ("unavailable", "inventory_unavailable"),
    ("unavailable", "inventory_incomplete"),
])
def test_review_unavailable_used_guard_covers_every_input(validator, status, reason):
    healthy = view()
    healthy["input_status"] = {"status": status, "reason": reason}
    healthy["inputs"][0]["used"] = {"status": "unknown", "atom": None, "evidence": None}
    healthy["inputs"][0]["value_origin"]["used"] = value_origin("unknown")
    second = deepcopy(healthy["inputs"][0])
    second["path"] = "physical.lo_temperature"
    healthy["inputs"].append(second)
    validator.validate(healthy)
    assert healthy["inputs"][0]["declared"]["status"] == "known"
    assert_bad(validator, healthy, ("inputs", 1, "used"), view()["inputs"][0]["used"])
    healthy["inputs"] = []
    validator.validate(healthy)


def test_review_unserved_documentation_preserves_available_known_used(validator):
    healthy = view()
    healthy["binding"].update(status="unavailable", reason="bundle_missing")
    healthy["fragment"] = None
    validator.validate(healthy)
    assert healthy["inputs"][0]["used"]["status"] == "known"
    assert healthy["input_status"] == {"status": "available", "reason": "ok"}


@pytest.mark.parametrize("name,path", [
    ("fragment", ("source_revision",)),
    ("fragment", ("meaning_source", "sha256")),
    ("fragment", ("id",)),
    ("snapshot", ("context", "execution_id")),
    ("snapshot", ("context", "point_id")),
    ("view", ("context", "run_uuid")),
    ("view", ("context", "calcjob_uuid")),
    ("fragment", ("inputs", 0, "path")),
    ("bundle", ("fragments", 0, "file")),
    ("view", ("fragment", "url")),
    ("index", ("entries", 0, "path")),
    ("fragment", ("full", "path")),
])
@pytest.mark.parametrize("suffix", ["\n", "\r", "\r\n", "\x00", "\u2028", "\u2029"])
def test_review_exact_tokens_reject_control_suffixes(validator, name, path, suffix):
    healthy = FACTORIES[name]()
    assert_bad(validator, healthy, path, at(healthy, path) + suffix)


@pytest.mark.parametrize("name,path,first", [
    ("fragment", ("id",), "a"),
    ("snapshot", ("context", "execution_id"), "E"),
    ("snapshot", ("context", "point_id"), "7"),
])
def test_review_exact_identifier_length_boundaries(validator, name, path, first):
    for exact in (first, first + "a" * 127):
        healthy = FACTORIES[name]()
        at(healthy, path[:-1])[path[-1]] = exact
        validator.validate(healthy)
        assert_bad(validator, healthy, path, exact + "\n")
    assert_bad(validator, FACTORIES[name](), path, first + "a" * 128)


def test_p10_missing_reference_is_explicit_required_null_not_known_null_or_unknown_origin(validator):
    absent = fragment()
    absent["inputs"][0]["reference_value_origin"] = None
    validator.validate(absent)
    omitted = deepcopy(absent)
    del omitted["inputs"][0]["reference_value_origin"]
    assert not validator.is_valid(omitted)
    known_null = fragment()
    known_null["inputs"][0]["reference_value_origin"]["atom"] = {
        "kind": "null", "value": None, "unit": None}
    unknown_source = fragment()
    unknown_source["inputs"][0]["reference_value_origin"]["origin"] = origin("unknown")
    for value in (known_null, unknown_source):
        validator.validate(value)
        assert value["inputs"][0]["reference_value_origin"] is not None
    for malformed in ({}, False, {"atom": None}):
        changed = deepcopy(absent)
        changed["inputs"][0]["reference_value_origin"] = malformed
        assert not validator.is_valid(changed)


def test_p10_multiple_absent_references_do_not_change_nonnull_shape_obligations(validator):
    healthy = fragment()
    for path in ("physical.unreferenced_one", "physical.unreferenced_two"):
        leaf = deepcopy(healthy["inputs"][0])
        leaf.update(path=path, reference_value_origin=None)
        healthy["inputs"].append(leaf)
    validator.validate(healthy)
    invalid = deepcopy(healthy)
    del invalid["inputs"][0]["reference_value_origin"]["parameter"]
    assert not validator.is_valid(invalid)
