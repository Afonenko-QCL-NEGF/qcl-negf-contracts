from __future__ import annotations

import pytest
from jsonschema import Draft202012Validator

from qcl_negf_contracts import load_schema, schema_names
from qcl_negf_contracts.artifacts import (ARTIFACT_SCHEMA_CONTRACTS, CONTRACT_SET,
    NATIVE_SCHEMA_VERSION, relative_path, validate_commit)
from qcl_negf_contracts.messages import ContractError, decode, encode, scientific_plan


def test_all_schemas_are_valid_and_references_stay_in_bundle():
    names = schema_names()
    for name in names:
        value = load_schema(name)
        if name == "results-contract-set.json":
            continue
        Draft202012Validator.check_schema(value)
        def visit(item):
            if isinstance(item, dict):
                reference = item.get("$ref", "")
                if reference and not reference.startswith("#"):
                    assert reference.split("#")[0] in names
                for child in item.values():
                    visit(child)
            elif isinstance(item, list):
                for child in item:
                    visit(child)
        visit(value)
    with pytest.raises(ValueError):
        load_schema("../pyproject.toml")


def test_result_registry_matches_python_contracts():
    registry = load_schema("results-contract-set.json")
    assert registry["contract_set"] == CONTRACT_SET
    assert registry["native_schema_version"] == NATIVE_SCHEMA_VERSION == "4.0"
    assert {(row["role"], row["media_type"]): frozenset(row["schemas"])
            for row in registry["artifacts"]} == ARTIFACT_SCHEMA_CONTRACTS


def test_single_archive_receipt_validates_unbounded_size_and_confined_filename():
    from qcl_negf_contracts import schema_validator
    from qcl_negf_contracts.artifacts import validate_export_receipt
    value = {"schema": "qcl-negf.science-export.v3", "contract_set": CONTRACT_SET,
             "transport_schema": "qcl-negf.export-archive.v1", "profile": "science",
             "snapshot_identity": "a" * 64, "sha256": "b" * 64,
             "bytes": 300_000_000, "filename": "job-science-a.tar.xz", "archive": "b.tar.xz"}
    assert validate_export_receipt(value) == value
    validator = schema_validator("export-receipt.schema.json")
    validator.validate(value)
    for invalid in ({"bytes": True}, {"bytes": -1}, {"sha256": "missing"},
                    {"filename": "../escape.tar.xz"}, {"filename": "subdir/archive.tar.xz"},
                    {"parts": []}, {"snapshot_identity": None}):
        with pytest.raises(ContractError):
            validate_export_receipt({**value, **invalid})
        assert not validator.is_valid({**value, **invalid})


@pytest.mark.parametrize("payload", [b'{"x":NaN}', b'{"x":Infinity}', b'{"x":1,"x":2}',
    b'[]', b'{"x":', b'\xff', b'{"x":' + b'[' * 70 + b'0' + b']' * 70 + b'}'])
def test_json_boundary_rejects_ambiguous_or_invalid_inputs(payload):
    with pytest.raises(ContractError):
        decode(payload)


def test_json_budget_and_canonical_encoding():
    value = {"unicode": "Δ", "signed": -0.0, "integer": 1}
    assert decode(encode(value)) == value
    with pytest.raises(ContractError, match="budget"):
        decode(encode(value), maximum=2)
    with pytest.raises(ContractError, match="finite"):
        encode({"value": float("nan")})


@pytest.mark.parametrize("value", ["../secret", "/secret", "a/../b", "a//b", "a\\b", "a/./b", "a\x00b"])
def test_artifact_paths_are_confined(value):
    with pytest.raises(ContractError):
        relative_path(value)


def test_commit_checks_inventory_and_dependency_closure():
    item = {"path": "model.json", "role": "model", "bytes": 4, "sha256": "a" * 64,
            "media_type": "application/json", "profile": "science",
            "schema": "qcl-negf-resolved-configuration-v3"}
    commit = {"schema": "qcl-negf.artifact-commit.v2", "contract_set": CONTRACT_SET,
              "identity": {"point_id": "p1"}, "generation": 1, "artifacts": [item]}
    assert validate_commit(commit)[0].path == "model.json"
    with pytest.raises(ContractError, match="dependency"):
        validate_commit({**commit, "artifacts": [{**item, "dependencies": ["missing.json"]}]})
    with pytest.raises(ContractError, match="duplicate"):
        validate_commit({**commit, "artifacts": [item, item]})
    with pytest.raises(ContractError, match="contract set"):
        validate_commit({**commit, "contract_set": "unsupported"})


def test_scientific_plan_requires_unique_ids_and_matching_count():
    plan = {"schema": "qcl-negf-scientific-plan-v2", "root_definition_id": "study",
            "name": "study", "fingerprint": "a" * 64, "root_kind": "study",
            "computation_count": 1, "inclusions": [{"id": "i1"}],
            "executions": [{"id": "e1"}], "points": [{"id": "p1"}]}
    assert scientific_plan(plan) == plan
    with pytest.raises(ContractError, match="count"):
        scientific_plan({**plan, "computation_count": 2})
    with pytest.raises(ContractError, match="duplicate"):
        scientific_plan({**plan, "points": [{"id": "p1"}, {"id": "p1"}]})


def test_offline_validator_resolves_bundled_schema_references():
    from qcl_negf_contracts import schema_validator
    validator = schema_validator("scientific-series-result.schema.json")
    errors = list(validator.iter_errors({}))
    assert any(error.validator == "required" for error in errors)
    with pytest.raises(ValueError, match="validation schema"):
        schema_validator("results-contract-set.json")
    for name in schema_names():
        if name != "results-contract-set.json":
            list(schema_validator(name).iter_errors({}))


@pytest.mark.parametrize("unsupported", ["campaign", "admission"])
def test_definitions_reject_unimplemented_scheduler_policies(unsupported):
    from qcl_negf_contracts import schema_validator
    validator = schema_validator("scientific-definition.schema.json")
    value = {"schema": "qcl-negf-study-v2", "kind": "study", "id": "example"}
    validator.validate(value)
    assert not validator.is_valid({**value, unsupported: {}})


def test_plan_retains_only_fixed_scheduler_metadata():
    schema = load_schema("scientific-plan.schema.json")
    validator = Draft202012Validator(schema["properties"]["campaign"])
    validator.validate(None)
    assert not validator.is_valid({})
    properties = schema["properties"]["nodes"]["items"]["properties"]
    assert not Draft202012Validator(properties["depends_on"]).is_valid(["other"])
    assert not Draft202012Validator(properties["reserve"]).is_valid(True)


@pytest.mark.parametrize("collection", ["points", "attempt_history"])
def test_result_coordinates_have_the_same_types_as_plan(collection):
    schema = load_schema("scientific-worker-result.schema.json")
    validator = Draft202012Validator(schema["properties"][collection]["items"]["properties"]["coordinates"])
    value = {"temperature_K": 70.0, "voltage_per_period_V": 0.055, "branch": "forward", "order": 1}
    validator.validate(value)
    for key, invalid in [("temperature_K", "70"), ("voltage_per_period_V", "0.055"),
                         ("branch", 1), ("order", 0), ("order", True)]:
        assert not validator.is_valid({**value, key: invalid})
