import numpy as np
import pytest

from mettagrid.policy.supervisor_actions import split_supervisor_actions_inplace


def test_split_supervisor_actions_maps_compact_primary_indices() -> None:
    teacher_actions = np.array([0, 2], dtype=np.int32)
    vibe_actions = np.zeros_like(teacher_actions)
    supervisor_action_ids = np.array([4, 5, 6], dtype=np.int32)

    split_supervisor_actions_inplace(
        teacher_actions,
        vibe_actions,
        supervisor_action_ids=supervisor_action_ids,
        action_names=["noop", "move_north", "move_south", "change_vibe_default", "change_vibe_miner", "x", "y"],
    )

    np.testing.assert_array_equal(teacher_actions, np.array([4, 6], dtype=np.int32))
    np.testing.assert_array_equal(vibe_actions, np.array([0, 0], dtype=np.int32))


def test_split_supervisor_actions_preserves_full_ids_and_extracts_vibes() -> None:
    teacher_actions = np.array([4, 7, 5], dtype=np.int32)
    vibe_actions = np.zeros_like(teacher_actions)
    supervisor_action_ids = np.array([4, 5, 6], dtype=np.int32)

    split_supervisor_actions_inplace(
        teacher_actions,
        vibe_actions,
        supervisor_action_ids=supervisor_action_ids,
        action_names=["noop", "move_north", "move_south", "change_vibe_default", "a", "b", "c", "change_vibe_x"],
    )

    np.testing.assert_array_equal(teacher_actions, np.array([4, 7, 5], dtype=np.int32))
    np.testing.assert_array_equal(vibe_actions, np.array([0, 7, 0], dtype=np.int32))


def test_split_supervisor_actions_rejects_invalid_full_action_id() -> None:
    teacher_actions = np.array([4, 99], dtype=np.int32)
    vibe_actions = np.zeros_like(teacher_actions)
    supervisor_action_ids = np.array([4, 5, 6], dtype=np.int32)

    with pytest.raises(ValueError, match="invalid action id"):
        split_supervisor_actions_inplace(
            teacher_actions,
            vibe_actions,
            supervisor_action_ids=supervisor_action_ids,
            action_names=[
                "noop",
                "move_north",
                "move_south",
                "change_vibe_default",
                "a",
                "b",
                "c",
                "change_vibe_x",
            ],
        )
