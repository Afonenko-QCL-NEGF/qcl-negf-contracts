import pytest
from qcl_negf_contracts.artifacts import CONTRACT_SET, validate_execution_progress
from qcl_negf_contracts.messages import ContractError


def progress():
    return {"schema": "qcl-negf-execution-progress-v1", "contract_set": CONTRACT_SET,
            "identity": {"execution_id": "e", "point_id": "p2"},
            "execution_id": "e", "active_point_id": "p2", "plan_fingerprint": "a"*64,
            "completed_points": [{"point": {"point_id": "p1"},
                "final_commit": "e/p1/final/commit.json",
                "receipt": {"identity": {"execution_id": "e", "point_id": "p1"},
                            "state_id": "s", "state_sequence": 1, "commit_sha256": "b"*64},
                "files": [{"path": "physics.h5", "sha256": "c"*64, "bytes": 8}]}]}


def test_progress_has_explicit_archive_dependencies():
    assert len(validate_execution_progress(progress())) == 1


@pytest.mark.parametrize("field,value", [("path", "../physics.h5"), ("sha256", "bad"), ("bytes", -1)])
def test_progress_rejects_unsafe_archive_dependencies(field, value):
    document = progress()
    document["completed_points"][0]["files"][0][field] = value
    with pytest.raises(ContractError):
        validate_execution_progress(document)
