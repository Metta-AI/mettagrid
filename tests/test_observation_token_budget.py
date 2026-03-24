import pytest

from mettagrid.config.mettagrid_config import ActionsConfig, GameConfig, MettaGridConfig, NoopActionConfig, ObsConfig
from mettagrid.simulator import Simulation
from mettagrid.test_support.map_builders import ObjectNameMapBuilder


def test_observation_token_budget_overflow_raises() -> None:
    cfg = MettaGridConfig(
        game=GameConfig(
            num_agents=1,
            max_steps=2,
            obs=ObsConfig(width=3, height=3, num_tokens=1),
            actions=ActionsConfig(noop=NoopActionConfig()),
        )
    )
    cfg.game.map_builder = ObjectNameMapBuilder.Config(
        map_data=[
            ["empty", "empty", "empty"],
            ["empty", "agent.default", "empty"],
            ["empty", "empty", "empty"],
        ]
    )

    with pytest.raises(RuntimeError, match=r"Observation token budget exceeded.*budget=1.*attempted="):
        Simulation(cfg, seed=0)
