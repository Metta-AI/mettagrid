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
