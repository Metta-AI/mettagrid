from mettagrid.config.mettagrid_config import GameConfig, MettaGridConfig
from mettagrid.map_builder.ascii import AsciiMapBuilder
from mettagrid.map_builder.map_builder import HasSeed
from mettagrid.map_builder.random_map import RandomMapBuilder
from mettagrid.mapgen.utils.ascii_grid import DEFAULT_CHAR_TO_NAME
from mettagrid.runner.rollout import resolve_env_for_seed


def test_resolve_env_for_seed_sets_seed_when_missing() -> None:
    env = MettaGridConfig(
        game=GameConfig(
            num_agents=1,
            map_builder=RandomMapBuilder.Config(width=7, height=7, agents=1, seed=None),
        )
    )

    resolved = resolve_env_for_seed(env, seed=47)

    assert resolved is not env
    assert isinstance(resolved.game.map_builder, HasSeed)
    assert resolved.game.map_builder.seed == 47
    assert isinstance(env.game.map_builder, HasSeed)
    assert env.game.map_builder.seed is None


def test_resolve_env_for_seed_keeps_explicit_seed() -> None:
    env = MettaGridConfig(
        game=GameConfig(
            num_agents=1,
            map_builder=RandomMapBuilder.Config(width=7, height=7, agents=1, seed=11),
        )
    )

    resolved = resolve_env_for_seed(env, seed=47)

    assert resolved is env
    assert isinstance(resolved.game.map_builder, HasSeed)
    assert resolved.game.map_builder.seed == 11


def test_resolve_env_for_seed_skips_unseeded_map_builders() -> None:
    env = MettaGridConfig(
        game=GameConfig(
            num_agents=1,
            map_builder=AsciiMapBuilder.Config(
                map_data=[["@", "."]],
                char_to_map_name=DEFAULT_CHAR_TO_NAME,
            ),
        )
    )

    resolved = resolve_env_for_seed(env, seed=47)

    assert resolved is env
