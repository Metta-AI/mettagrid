import json

import numpy as np
import pytest

from mettagrid.config.mettagrid_config import (
    ActionsConfig,
    GameConfig,
    MettaGridConfig,
    MoveActionConfig,
    NoopActionConfig,
    ObsConfig,
    TalkConfig,
    WallConfig,
)
from mettagrid.map_builder.random_map import RandomMapBuilder
from mettagrid.policy.policy_env_interface import PolicyEnvInterface


def test_policy_env_interface_round_trip_serialization():
    config = MettaGridConfig(
        game=GameConfig(
            num_agents=4,
            obs=ObsConfig(width=5, height=5, num_tokens=100),
            max_steps=100,
            resource_names=["ore", "wood"],
            actions=ActionsConfig(noop=NoopActionConfig(), move=MoveActionConfig()),
            talk=TalkConfig(enabled=True, max_length=140, cooldown_steps=50),
            objects={"wall": WallConfig()},
            map_builder=RandomMapBuilder.Config(width=10, height=10, agents=4, seed=42),
        )
    )

    original = PolicyEnvInterface.from_mg_cfg(config)
    dumped = original.model_dump(mode="json")
    restored = PolicyEnvInterface.model_validate(dumped)

    assert restored.num_agents == original.num_agents
    assert restored.obs_width == original.obs_width
    assert restored.obs_height == original.obs_height
    assert restored.tags == original.tags
    assert restored.tag_id_to_name == original.tag_id_to_name

    assert restored.observation_space.shape == original.observation_space.shape
    assert restored.observation_space.dtype == original.observation_space.dtype
    assert np.array_equal(restored.observation_space.low, original.observation_space.low)
    assert np.array_equal(restored.observation_space.high, original.observation_space.high)

    assert restored.action_space.n == original.action_space.n
    assert restored.action_space.start == original.action_space.start
    assert restored.talk == original.talk

    assert len(restored.obs_features) == len(original.obs_features)
    for r, o in zip(restored.obs_features, original.obs_features, strict=True):
        assert r.id == o.id
        assert r.name == o.name
        assert r.normalization == o.normalization

    assert restored.action_names == original.action_names


@pytest.mark.parametrize("observation_kind", ["token", "tokens"])
def test_policy_env_interface_accepts_legacy_token_observation_kind(observation_kind: str):
    config = MettaGridConfig(
        game=GameConfig(
            num_agents=4,
            obs=ObsConfig(width=5, height=5, num_tokens=100),
            max_steps=100,
            resource_names=["ore", "wood"],
            actions=ActionsConfig(noop=NoopActionConfig(), move=MoveActionConfig()),
            talk=TalkConfig(enabled=True, max_length=140, cooldown_steps=50),
            objects={"wall": WallConfig()},
            map_builder=RandomMapBuilder.Config(width=10, height=10, agents=4, seed=42),
        )
    )

    payload = PolicyEnvInterface.from_mg_cfg(config).model_dump(mode="json")
    payload["observation_kind"] = observation_kind

    restored = PolicyEnvInterface.model_validate_json(json.dumps(payload))

    assert restored.observation_kind == "token"


def test_policy_env_interface_to_json_includes_talk():
    config = MettaGridConfig(
        game=GameConfig(
            num_agents=4,
            obs=ObsConfig(width=5, height=5, num_tokens=100),
            max_steps=100,
            resource_names=["ore", "wood"],
            actions=ActionsConfig(noop=NoopActionConfig(), move=MoveActionConfig()),
            talk=TalkConfig(enabled=True, max_length=140, cooldown_steps=50),
            objects={"wall": WallConfig()},
            map_builder=RandomMapBuilder.Config(width=10, height=10, agents=4, seed=42),
        )
    )

    payload = json.loads(PolicyEnvInterface.from_mg_cfg(config).to_json())

    assert payload["talk"] == {
        "enabled": True,
        "max_length": 140,
        "cooldown_steps": 50,
    }


def test_policy_env_interface_proto_round_trip_preserves_talk():
    config = MettaGridConfig(
        game=GameConfig(
            num_agents=4,
            obs=ObsConfig(width=5, height=5, num_tokens=100),
            max_steps=100,
            resource_names=["ore", "wood"],
            actions=ActionsConfig(noop=NoopActionConfig(), move=MoveActionConfig()),
            talk=TalkConfig(enabled=True, max_length=140, cooldown_steps=50),
            objects={"wall": WallConfig()},
            map_builder=RandomMapBuilder.Config(width=10, height=10, agents=4, seed=42),
        )
    )

    original = PolicyEnvInterface.from_mg_cfg(config)
    restored = PolicyEnvInterface.from_proto(original.to_proto())

    assert restored.talk == original.talk


def test_policy_env_interface_to_proto_omits_disabled_talk():
    config = MettaGridConfig(
        game=GameConfig(
            num_agents=4,
            obs=ObsConfig(width=5, height=5, num_tokens=100),
            max_steps=100,
            resource_names=["ore", "wood"],
            actions=ActionsConfig(noop=NoopActionConfig(), move=MoveActionConfig()),
            objects={"wall": WallConfig()},
            map_builder=RandomMapBuilder.Config(width=10, height=10, agents=4, seed=42),
        )
    )

    proto = PolicyEnvInterface.from_mg_cfg(config).to_proto()

    assert not proto.HasField("talk")


def test_policy_env_interface_from_proto_without_talk_disables_talk():
    config = MettaGridConfig(
        game=GameConfig(
            num_agents=4,
            obs=ObsConfig(width=5, height=5, num_tokens=100),
            max_steps=100,
            resource_names=["ore", "wood"],
            actions=ActionsConfig(noop=NoopActionConfig(), move=MoveActionConfig()),
            objects={"wall": WallConfig()},
            map_builder=RandomMapBuilder.Config(width=10, height=10, agents=4, seed=42),
        )
    )

    proto = PolicyEnvInterface.from_mg_cfg(config).to_proto()
    restored = PolicyEnvInterface.from_proto(proto)

    assert restored.talk == TalkConfig()
