from copy import deepcopy

import pytest

from qcl_negf_contracts import schema_validator


def policy():
    return {"archive": {"full_final": True, "optical": False, "projections": True,
                        "intermediate_history": 16},
            "recovery": {"enabled": True, "interval_seconds": 1800.0,
                         "retain_generations": 2, "byte_budget": 8589934592,
                         "reserve_bytes": 67108864},
            "telemetry": {"enabled": True, "buffer_events": 256}}


def test_definition_accepts_one_output_policy_and_rejects_conflicting_sources():
    validator = schema_validator("scientific-definition.schema.json")
    study = {"schema": "qcl-negf-study-v2", "kind": "study", "id": "fixture",
             "output": policy()}
    validator.validate(study)
    assert not validator.is_valid({**study, "outputs": {"full_state": True}})


@pytest.mark.parametrize("section,field,value", [
    ("archive", "full_final", False), ("recovery", "byte_budget", 0),
    ("recovery", "byte_budget", True), ("recovery", "reserve_bytes", -1),
    ("recovery", "retain_generations", 0), ("recovery", "interval_seconds", 0),
    ("telemetry", "buffer_events", 0), ("archive", "unexpected", True),
])
def test_output_policy_rejects_unbounded_or_unsupported_settings(section, field, value):
    output = deepcopy(policy())
    output[section][field] = value
    validator = schema_validator("scientific-definition.schema.json")
    assert not validator.is_valid({"schema": "qcl-negf-study-v2", "kind": "study",
                                   "id": "fixture", "output": output})


def test_legacy_outputs_remain_valid_for_explicit_runner_migration():
    schema_validator("scientific-definition.schema.json").validate(
        {"schema": "qcl-negf-study-v2", "kind": "study", "id": "legacy",
         "outputs": {"full_state": False, "optical": False}})
