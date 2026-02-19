from __future__ import annotations

from typing import Sequence

import numpy as np

from mettagrid.mettagrid_c import dtype_actions


def split_supervisor_actions_inplace(
    teacher_actions: np.ndarray,
    vibe_actions: np.ndarray,
    *,
    supervisor_action_ids: np.ndarray,
    action_names: Sequence[str],
) -> None:
    """Split supervisor outputs into primary teacher labels and vibe actions.

    Supported supervisor output formats:
    - Compact primary indices in range [0, len(supervisor_action_ids))
    - Full action ids in range [0, len(action_names))

    For compact outputs, teacher labels are mapped to full primary action ids and
    vibe actions are set to 0.

    For full-id outputs, teacher labels are preserved as-is. Vibe actions are set
    only where the full action id is not in the primary id set.
    """

    zero_action = dtype_actions.type(0)
    teacher_actions_i64 = teacher_actions.astype(np.int64, copy=False)
    action_ids_i64 = supervisor_action_ids.astype(np.int64, copy=False)

    if np.all((teacher_actions_i64 >= 0) & (teacher_actions_i64 < len(action_ids_i64))):
        np.copyto(teacher_actions, action_ids_i64[teacher_actions_i64].astype(dtype_actions, copy=False))
        vibe_actions.fill(zero_action)
        return

    if not action_names:
        raise ValueError("Policy env info must include action names for supervisor action splitting")
    max_action_id = len(action_names) - 1
    invalid_mask = (teacher_actions_i64 < 0) | (teacher_actions_i64 > max_action_id)
    if np.any(invalid_mask):
        invalid_agent = int(np.flatnonzero(invalid_mask)[0])
        raise ValueError(
            f"Supervisor produced invalid action id {int(teacher_actions[invalid_agent])} for agent {invalid_agent}"
        )

    np.copyto(teacher_actions, teacher_actions_i64.astype(dtype_actions, copy=False))
    primary_mask = np.isin(teacher_actions_i64, action_ids_i64)
    vibe_actions.fill(zero_action)
    vibe_actions[~primary_mask] = teacher_actions_i64[~primary_mask].astype(dtype_actions, copy=False)
