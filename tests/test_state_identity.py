"""New state coordinates cannot contradict their commit identity."""
import pytest
from qcl_negf_contracts.artifacts import CONTRACT_SET, validate_commit
from qcl_negf_contracts.messages import ContractError


@pytest.mark.parametrize("state", [
    {"state_id": "s", "state_sequence": 0},
    {"state_id": "s", "state_sequence": True},
    {"state_id": "" , "state_sequence": 1},
    {"state_id": "s", "state_sequence": 1},
])
def test_invalid_or_conflicting_state_coordinates_are_rejected(state):
    value = {"schema": "qcl-negf.artifact-commit.v2", "contract_set": CONTRACT_SET,
             "generation": 1, "identity": {"state_id": "other", "state_sequence": 1},
             "artifacts": [], **state}
    with pytest.raises(ContractError, match="state identity"):
        validate_commit(value)
