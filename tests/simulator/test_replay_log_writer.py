from __future__ import annotations

import zlib
from pathlib import Path

from mettagrid.config.mettagrid_config import MettaGridConfig, NoopActionConfig
from mettagrid.simulator import Action, Simulation
from mettagrid.simulator.replay_log_writer import EpisodeReplay


def test_write_replay_sorts_nested_mixed_policy_info_keys_without_crashing(tmp_path: Path) -> None:
    cfg = MettaGridConfig.EmptyRoom(num_agents=1)
    cfg.game.actions.noop = NoopActionConfig()
    sim = Simulation(cfg, seed=42)
    replay = EpisodeReplay(sim)

    sim.agent(0).set_action(Action(name="noop"))
    sim.step()
    sim._context["policy_infos"] = {
        0: {
            "debug_map": {
                2: "two",
                "10": "ten",
                1: "one",
            }
        }
    }
    replay.log_step(sim.current_step, sim._c_sim.actions(), sim._c_sim.rewards())  # type: ignore[attr-defined]

    replay_path = tmp_path / "replay.json.z"
    replay.write_replay(str(replay_path))

    replay_data = zlib.decompress(replay_path.read_bytes()).decode("utf-8")

    assert '"debug_map": {"1": "one", "10": "ten", "2": "two"}' in replay_data


def test_write_replay_budgets_large_policy_debug_blobs(tmp_path: Path) -> None:
    cfg = MettaGridConfig.EmptyRoom(num_agents=1)
    cfg.game.actions.noop = NoopActionConfig()
    sim = Simulation(cfg, seed=42)
    replay = EpisodeReplay(sim)

    sim.agent(0).set_action(Action(name="noop"))
    sim.step()
    sim._context["policy_infos"] = {
        0: {
            "policy_name": "debug_policy",
            "skill": "pursue_target",
            "target": [1, 2],
            "memory_hash_after_interpret": "abc123",
            "latency_ms": {"total": 1.5},
            "skill_args": {"static_config": "x" * 4096},
            "wm_after_interpret": {"scratch": "y" * 4096},
            "wm_after_perceive": {"scratch": "z" * 4096},
        }
    }
    replay.log_step(sim.current_step, sim._c_sim.actions(), sim._c_sim.rewards())  # type: ignore[attr-defined]

    replay_path = tmp_path / "replay.json.z"
    replay.write_replay(str(replay_path))

    replay_data = zlib.decompress(replay_path.read_bytes()).decode("utf-8")

    assert '"policy_name": "debug_policy"' in replay_data
    assert '"skill": "pursue_target"' in replay_data
    assert '"target": [1, 2]' in replay_data
    assert '"memory_hash_after_interpret": "abc123"' in replay_data
    assert '"latency_ms": {"total": 1.5}' in replay_data
    assert "skill_args" not in replay_data
    assert "wm_after_interpret" not in replay_data
    assert "wm_after_perceive" not in replay_data
