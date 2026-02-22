from __future__ import annotations

import numpy as np

from mettagrid.mettagrid_c import dtype_actions


def split_supervisor_actions_inplace(
    teacher_actions: np.ndarray,
    vibe_actions: np.ndarray,
    *,
    num_primary_actions: int,
    vibe_action_ids_by_index: np.ndarray,
) -> None:
    """Split canonical split-action labels into primary teacher labels and simulator vibe actions.

    Canonical teacher labels are in split-action id space:
    - Primary action labels are in [0, num_primary_actions)
    - Vibe action labels are in [num_primary_actions, num_primary_actions + num_vibe_actions)
    where num_vibe_actions = len(vibe_action_ids_by_index).
    """

    zero_action = dtype_actions.type(0)
    teacher_actions_i64 = teacher_actions.astype(np.int64, copy=False)
    num_vibe_actions = int(vibe_action_ids_by_index.size)
    max_action_id = (num_primary_actions + num_vibe_actions) - 1
    invalid_mask = (teacher_actions_i64 < 0) | (teacher_actions_i64 > max_action_id)
    if np.any(invalid_mask):
        invalid_agent = int(np.flatnonzero(invalid_mask)[0])
        raise ValueError(
            f"Supervisor produced invalid action id {int(teacher_actions[invalid_agent])} for agent {invalid_agent}"
        )

    np.copyto(teacher_actions, teacher_actions_i64.astype(dtype_actions, copy=False))
    primary_mask = teacher_actions_i64 < num_primary_actions
    vibe_actions.fill(zero_action)
    vibe_indices = teacher_actions_i64[~primary_mask] - num_primary_actions
    vibe_actions[~primary_mask] = vibe_action_ids_by_index[vibe_indices].astype(dtype_actions, copy=False)
