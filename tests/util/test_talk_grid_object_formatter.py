from __future__ import annotations

import numpy as np

from mettagrid.util.grid_object_formatter import format_grid_object


def test_format_grid_object_includes_active_talk_state() -> None:
    formatted = format_grid_object(
        {
            "id": 1,
            "type_name": "agent",
            "location": [2, 3],
            "agent_id": 0,
            "group_id": 0,
            "talk_text": "scouting north",
            "talk_remaining_steps": 12,
        },
        actions=np.zeros((1, 2), dtype=np.int32),
        env_action_success=[True],
        rewards=np.zeros(1, dtype=np.float32),
        total_rewards=np.zeros(1, dtype=np.float32),
    )

    assert formatted["talk_text"] == "scouting north"
    assert formatted["talk_remaining_steps"] == 12


def test_format_grid_object_omits_inactive_talk_state() -> None:
    formatted = format_grid_object(
        {
            "id": 1,
            "type_name": "agent",
            "location": [2, 3],
            "agent_id": 0,
            "group_id": 0,
        },
        actions=np.zeros((1, 2), dtype=np.int32),
        env_action_success=[True],
        rewards=np.zeros(1, dtype=np.float32),
        total_rewards=np.zeros(1, dtype=np.float32),
        talk_text="",
        talk_remaining_steps=0,
    )

    assert "talk_text" not in formatted
    assert "talk_remaining_steps" not in formatted
