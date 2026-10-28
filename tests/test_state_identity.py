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
    from test_results_v2 import manifest
    value = {**manifest(), **state}
    value['identity'] = {**value['identity'], 'state_id': 'other', 'state_sequence': 1}
    with pytest.raises(ContractError):
        validate_commit(value)


def test_old_commit_is_explicitly_unsupported():
    with pytest.raises(ContractError) as caught:
        validate_commit({'schema':'qcl-negf.artifact-commit.v2','contract_set':'qcl-negf.results.v1'})
    assert caught.value.code == 'unsupported_format'
