from mettagrid.config.game_value import inv, stat
from mettagrid.config.mettagrid_config import (
    AgentConfig,
    GameConfig,
    GridObjectConfig,
    InventoryConfig,
    MettaGridConfig,
)
from mettagrid.config.obs_config import ObsConfig
from mettagrid.simulator.simulator import Simulation
from mettagrid.test_support.map_builders import ObjectNameMapBuilder

VISION_RADIUS_STAT = stat("vision_radius")
VISION_RADIUS_INVENTORY = inv("vision_radius")


def _token_names(sim: Simulation, agent_id: int = 0) -> set[str]:
    return {token.feature.name for token in sim.agent(agent_id).observation.tokens}


def _signal_sim(
    *,
    vision_radius: float,
    observation_radius_value=VISION_RADIUS_STAT,
    obs_width: int = 13,
    obs_height: int = 13,
    map_data: list[list[str]] | None = None,
) -> Simulation:
    game_config = GameConfig(
        num_agents=1,
        max_steps=10,
        resource_names=["signal"],
        agents=[
            AgentConfig(
                inventory=InventoryConfig(initial={}, limits={}),
                rewards={},
                on_tick={},
                initial_stats={"vision_radius": vision_radius},
            )
        ],
        objects={
            "signal_beacon": GridObjectConfig(
                name="signal_beacon",
                inventory=InventoryConfig(initial={"signal": 1}, limits={}),
            )
        },
        obs=ObsConfig(
            width=obs_width,
            height=obs_height,
            num_tokens=64,
            observation_radius_value=observation_radius_value,
        ),
    )
    cfg = MettaGridConfig(game=game_config)
    cfg.game.map_builder = ObjectNameMapBuilder.Config(
        map_data=map_data
        or [
            ["empty", "empty", "empty", "empty", "empty"],
            ["empty", "empty", "empty", "empty", "empty"],
            ["agent.red.0", "empty", "empty", "signal_beacon", "empty"],
            ["empty", "empty", "empty", "empty", "empty"],
            ["empty", "empty", "empty", "empty", "empty"],
        ]
    )
    return Simulation(cfg, seed=7)


def _inventory_signal_sim(*, vision_radius: int, observation_radius_value=VISION_RADIUS_INVENTORY) -> Simulation:
    game_config = GameConfig(
        num_agents=1,
        max_steps=10,
        resource_names=["signal", "vision_radius"],
        agents=[
            AgentConfig(
                inventory=InventoryConfig(initial={"vision_radius": vision_radius}, limits={}),
                rewards={},
                on_tick={},
            )
        ],
        objects={
            "signal_beacon": GridObjectConfig(
                name="signal_beacon",
                inventory=InventoryConfig(initial={"signal": 1}, limits={}),
            )
        },
        obs=ObsConfig(
            width=13,
            height=13,
            num_tokens=64,
            observation_radius_value=observation_radius_value,
        ),
    )
    cfg = MettaGridConfig(game=game_config)
    cfg.game.map_builder = ObjectNameMapBuilder.Config(
        map_data=[
            ["empty", "empty", "empty", "empty", "empty"],
            ["empty", "empty", "empty", "empty", "empty"],
            ["agent.red.0", "empty", "empty", "signal_beacon", "empty"],
            ["empty", "empty", "empty", "empty", "empty"],
            ["empty", "empty", "empty", "empty", "empty"],
        ]
    )
    return Simulation(cfg, seed=7)


def test_observation_radius_value_zero_hides_far_objects() -> None:
    sim = _signal_sim(vision_radius=0.0)
    assert "inv:signal" not in _token_names(sim)
    sim.close()


def test_observation_radius_value_nonzero_restores_far_objects() -> None:
    sim = _signal_sim(vision_radius=4.0)
    assert "inv:signal" in _token_names(sim)
    sim.close()


def test_unset_observation_radius_value_uses_full_window() -> None:
    sim = _signal_sim(vision_radius=0.0, observation_radius_value=None)
    assert "inv:signal" in _token_names(sim)
    sim.close()


def test_observation_radius_value_expands_rectangular_windows_to_full_size() -> None:
    sim = _signal_sim(
        vision_radius=6.0,
        obs_width=13,
        obs_height=7,
        map_data=[
            ["empty", "empty", "empty", "empty", "empty", "empty", "empty"],
            ["empty", "empty", "empty", "empty", "empty", "empty", "empty"],
            ["empty", "empty", "empty", "empty", "empty", "empty", "empty"],
            ["agent.red.0", "empty", "empty", "empty", "empty", "empty", "signal_beacon"],
            ["empty", "empty", "empty", "empty", "empty", "empty", "empty"],
            ["empty", "empty", "empty", "empty", "empty", "empty", "empty"],
            ["empty", "empty", "empty", "empty", "empty", "empty", "empty"],
        ],
    )
    assert "inv:signal" in _token_names(sim)
    sim.close()


def test_observation_radius_value_accepts_inventory_values() -> None:
    sim = _inventory_signal_sim(vision_radius=4)
    assert "inv:signal" in _token_names(sim)
    sim.close()
