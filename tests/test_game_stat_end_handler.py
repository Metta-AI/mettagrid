from mettagrid.config.event_config import EventConfig
from mettagrid.config.mettagrid_config import ActionsConfig, GameConfig, MettaGridConfig, NoopActionConfig
from mettagrid.config.mutation import logStatToGame
from mettagrid.config.query import query
from mettagrid.config.tag import typeTag
from mettagrid.simulator import Simulation


def test_simulation_ends_when_game_stat_threshold_is_met() -> None:
    cfg = MettaGridConfig(
        game=GameConfig(
            num_agents=1,
            max_steps=50,
            actions=ActionsConfig(noop=NoopActionConfig()),
            events={
                "trigger_win": EventConfig(
                    name="trigger_win",
                    target_query=query(typeTag("agent")),
                    timesteps=[1],
                    mutations=[logStatToGame("winner_declared")],
                    max_targets=1,
                )
            },
            end_episode_on_game_stats={"winner_declared": 1},
        )
    )

    sim = Simulation(cfg, seed=3)
    sim.agent(0).set_action("noop")
    sim.step()

    assert sim.current_step == 1
    assert sim.episode_stats["game"].get("winner_declared", 0) == 1
    assert sim.is_done() is True

    sim.close()
