from pydantic import ValidationError

from mettagrid.runner.episode_subprocess import _classify, _compute_policy_agent_ids
from mettagrid.runner.policy_server.websocket_transport import PolicyStepError


def test_compute_policy_agent_ids_groups_agents_by_policy() -> None:
    assert _compute_policy_agent_ids([0, 2, 0, 1, 2], policy_count=3) == [[0, 2], [3], [1, 4]]


def test_compute_policy_agent_ids_preserves_empty_slots() -> None:
    assert _compute_policy_agent_ids([1, 1], policy_count=3) == [[], [0, 1], []]


def test_classify_marks_policy_step_errors_as_policy_error() -> None:
    assert _classify(PolicyStepError("policy step failed")) == "policy_error"


def test_classify_marks_validation_errors_as_config_error() -> None:
    try:
        raise ValidationError.from_exception_data(
            "EpisodeSpec",
            [{"type": "missing", "loc": ("field",), "input": {}, "msg": "Field required"}],
        )
    except ValidationError as exc:
        assert _classify(exc) == "config_error"


def test_classify_marks_generic_exceptions_as_crash() -> None:
    assert _classify(RuntimeError("segmentation fault")) == "crash"
