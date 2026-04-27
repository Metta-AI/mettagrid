import pytest

from mettagrid.config.mettagrid_config import (
    ActionsConfig,
    GameConfig,
    MettaGridConfig,
    MoveActionConfig,
    NoopActionConfig,
    ObsConfig,
    WallConfig,
)
from mettagrid.map_builder.random_map import RandomMapBuilder
from mettagrid.policy.game_interface import ActionSpaceSpec, FeatureSpec, GameInterface, ObservationSpec, TalkSpec
from mettagrid.policy.policy_env_interface import PolicyEnvInterface


def _mettagrid_policy_env_info() -> PolicyEnvInterface:
    return PolicyEnvInterface.from_mg_cfg(
        MettaGridConfig(
            game=GameConfig(
                num_agents=4,
                obs=ObsConfig(width=5, height=5, num_tokens=100),
                max_steps=100,
                resource_names=["energy", "ore", "wood"],
                actions=ActionsConfig(noop=NoopActionConfig(), move=MoveActionConfig(consumed_resources={"energy": 1})),
                objects={"wall": WallConfig()},
                map_builder=RandomMapBuilder.Config(width=10, height=10, agents=4, seed=42),
            )
        )
    )


def test_game_interface_models_mettagrid_policy_contract() -> None:
    policy_env = _mettagrid_policy_env_info()

    game_interface = GameInterface(
        engine_id="mettagrid",
        game_id="arena",
        num_agents=policy_env.num_agents,
        observation=ObservationSpec(
            kind="token",
            wire_format="mettagrid_triplet_v1",
            shape=policy_env.observation_shape,
            dtype=policy_env.observation_dtype,
            low=policy_env.observation_low,
            high=policy_env.observation_high,
            egocentric_shape=policy_env.egocentric_shape,
            features=[FeatureSpec.model_validate(feature.model_dump()) for feature in policy_env.obs_features],
            tags=list(policy_env.tags),
        ),
        action=ActionSpaceSpec(kind="discrete", names=list(policy_env.action_names)),
        move_energy_cost=policy_env.move_energy_cost,
        talk=TalkSpec.model_validate(policy_env.talk.model_dump()),
    )

    assert game_interface.protocol_version == "game_interface.v1"
    assert game_interface.engine_id == "mettagrid"
    assert game_interface.game_id == "arena"
    assert game_interface.num_agents == policy_env.num_agents
    assert game_interface.observation.kind == "token"
    assert game_interface.observation.wire_format == "mettagrid_triplet_v1"
    assert game_interface.observation.shape == policy_env.observation_shape
    assert [feature.name for feature in game_interface.observation.features] == [
        feature.name for feature in policy_env.obs_features
    ]
    assert game_interface.action.kind == "discrete"
    assert game_interface.action.discrete_action_names() == policy_env.action_names
    assert game_interface.move_energy_cost == 1


def test_game_interface_models_external_box_policy_contract() -> None:
    game_interface = GameInterface(
        engine_id="bitworld",
        game_id="among_them",
        num_agents=5,
        observation=ObservationSpec(
            kind="box",
            wire_format="bitworld_packed_4bit",
            shape=(8192,),
            dtype="uint8",
            low=0,
            high=15,
        ),
        action=ActionSpaceSpec(kind="discrete", names=[f"button_mask_{mask}" for mask in range(128)]),
    )

    assert game_interface.observation.kind == "box"
    assert game_interface.observation.wire_format == "bitworld_packed_4bit"
    assert game_interface.observation.shape == (8192,)
    assert game_interface.observation.dtype == "uint8"
    assert game_interface.action.discrete_action_names()[127] == "button_mask_127"


def test_game_interface_models_bitworld_button_bitmask_actions() -> None:
    game_interface = GameInterface(
        engine_id="bitworld",
        game_id="among_them",
        num_agents=5,
        observation=ObservationSpec(
            kind="box",
            wire_format="bitworld_packed_4bit",
            shape=(8192,),
            dtype="uint8",
            low=0,
            high=255,
        ),
        action=ActionSpaceSpec(
            kind="bitmask",
            names=["up", "down", "left", "right", "select", "a", "b"],
        ),
    )

    assert game_interface.action.bit_count == 7
    assert len(game_interface.action.discrete_action_names()) == 128
    assert game_interface.action.discrete_action_names()[0] == "none"
    assert game_interface.action.discrete_action_names()[3] == "up+down"
    action_names = game_interface.action.discrete_action_names()
    assert action_names[0] == "none"
    assert action_names[127] == "up+down+left+right+select+a+b"


def test_bitmask_actions_reject_mismatched_button_count() -> None:
    with pytest.raises(ValueError, match="bit_count must match"):
        ActionSpaceSpec(kind="bitmask", names=["up", "down"], bit_count=7)
