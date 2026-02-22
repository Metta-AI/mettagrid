import numpy as np
import pytest

from mettagrid.policy.supervisor_actions import split_supervisor_actions_inplace


def test_split_supervisor_actions_preserves_primary_labels() -> None:
    teacher_actions = np.array([0, 2], dtype=np.int32)
    vibe_actions = np.zeros_like(teacher_actions)
    vibe_action_ids_by_index = np.array([11, 12], dtype=np.int32)

    split_supervisor_actions_inplace(
        teacher_actions,
        vibe_actions,
        num_primary_actions=3,
        vibe_action_ids_by_index=vibe_action_ids_by_index,
    )

    np.testing.assert_array_equal(teacher_actions, np.array([0, 2], dtype=np.int32))
    np.testing.assert_array_equal(vibe_actions, np.array([0, 0], dtype=np.int32))


def test_split_supervisor_actions_maps_vibe_labels_to_sim_action_ids() -> None:
    teacher_actions = np.array([0, 3, 4], dtype=np.int32)
    vibe_actions = np.zeros_like(teacher_actions)
    vibe_action_ids_by_index = np.array([40, 41], dtype=np.int32)

    split_supervisor_actions_inplace(
        teacher_actions,
        vibe_actions,
        num_primary_actions=3,
        vibe_action_ids_by_index=vibe_action_ids_by_index,
    )

    np.testing.assert_array_equal(teacher_actions, np.array([0, 3, 4], dtype=np.int32))
    np.testing.assert_array_equal(vibe_actions, np.array([0, 40, 41], dtype=np.int32))


def test_split_supervisor_actions_rejects_invalid_split_action_id() -> None:
    teacher_actions = np.array([4, 99], dtype=np.int32)
    vibe_actions = np.zeros_like(teacher_actions)
    vibe_action_ids_by_index = np.array([40, 41], dtype=np.int32)

    with pytest.raises(ValueError, match="invalid action id"):
        split_supervisor_actions_inplace(
            teacher_actions,
            vibe_actions,
            num_primary_actions=3,
            vibe_action_ids_by_index=vibe_action_ids_by_index,
        )
