from mettagrid.runner.episode_subprocess import _compute_policy_agent_ids


def test_compute_policy_agent_ids_groups_agents_by_policy() -> None:
    assert _compute_policy_agent_ids([0, 2, 0, 1, 2], policy_count=3) == [[0, 2], [3], [1, 4]]


def test_compute_policy_agent_ids_preserves_empty_slots() -> None:
    assert _compute_policy_agent_ids([1, 1], policy_count=3) == [[], [0, 1], []]
