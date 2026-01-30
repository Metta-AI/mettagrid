"""Observation feature ID mapping for MettaGrid.

This module provides the IdMap class which manages observation feature IDs
and their mappings, along with the ObservationFeatureSpec class.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict

from mettagrid.config.game_value import InventoryValue, NumObjectsValue, Scope, StatValue, TagCountValue
from mettagrid.config.tag import typeTag

# This breaks a circular dependency: id_map <-> mettagrid_config
# Pythonic resolutions (require refactor):
# a. move IdMap, ObservationFeatureSpec to mettagrid_config
# b. move IdMap, GameConfig, ObservationFeatureSpec to package-level types.py
if TYPE_CHECKING:
    from mettagrid.config.mettagrid_config import GameConfig, GridObjectConfig


def num_inventory_tokens_needed(max_inventory_value: int, token_value_base: int) -> int:
    """Calculate how many tokens are needed to encode max_inventory_value with given base.

    Args:
        max_inventory_value: Maximum inventory value to encode (e.g., 65535 for uint16_t)
        token_value_base: Base for encoding (value per token: 0 to base-1)

    Returns:
        Number of tokens needed
    """
    if max_inventory_value == 0:
        return 1
    # Need ceil(log_base(max_value + 1)) tokens
    return math.ceil(math.log(max_inventory_value + 1, token_value_base))


class ObservationFeatureSpec(BaseModel):
    """Specification for an observation feature."""

    model_config = ConfigDict(protected_namespaces=())

    id: int
    name: str
    normalization: float


def make_token_feature(name: str, feature_id: int, normalization: float) -> tuple[ObservationFeatureSpec, int]:
    """Create a single observation feature token.

    Args:
        name: Feature name (e.g. "vibe", "tag", "cooldown_remaining")
        feature_id: Current feature ID
        normalization: Normalization value for this feature

    Returns:
        Tuple of (feature spec, next available feature_id)
    """
    return ObservationFeatureSpec(id=feature_id, normalization=normalization, name=name), feature_id + 1


def make_multi_token_features(
    name: str, feature_id: int, normalization: float, num_tokens: int
) -> tuple[list[ObservationFeatureSpec], int]:
    """Create a multi-token feature set (base + power tokens).

    Args:
        name: Base feature name (e.g. "inv:gold", "stat:own:health:delta")
        feature_id: Starting feature ID
        normalization: Normalization value for all tokens
        num_tokens: Total number of tokens (1 base + N-1 power tokens)

    Returns:
        Tuple of (list of feature specs, next available feature_id)
    """
    features = []
    feat, feature_id = make_token_feature(name, feature_id, normalization)
    features.append(feat)
    for power in range(1, num_tokens):
        feat, feature_id = make_token_feature(f"{name}:p{power}", feature_id, normalization)
        features.append(feat)
    return features, feature_id


class IdMap:
    """Manages observation feature IDs and mappings for a MettaGrid configuration."""

    def __init__(self, config: GameConfig):
        self._config = config
        self._features_list: list[ObservationFeatureSpec] | None = None

    def features(self) -> list[ObservationFeatureSpec]:
        """Get the list of observation features, computing them once on first access."""
        if self._features_list is None:
            self._features_list = self._compute_features()
        return self._features_list

    def feature_id(self, name: str) -> int:
        """Get the ID for a named feature."""
        feature_ids = self._feature_ids_map()
        if name not in feature_ids:
            raise KeyError(f"Unknown observation feature: {name}")
        return feature_ids[name]

    def feature(self, name: str) -> ObservationFeatureSpec:
        """Get the feature spec for a named feature."""
        for feat in self.features():
            if feat.name == name:
                return feat
        raise KeyError(f"Unknown observation feature: {name}")

    def _feature_ids_map(self) -> dict[str, int]:
        """Get mapping of feature names to IDs."""
        return {feature.name: feature.id for feature in self.features()}

    def _all_grid_objects(self) -> list["GridObjectConfig"]:
        """Get all grid objects including agents.

        Returns objects from the objects dict plus agents. If agents list is empty
        but num_agents > 0, includes the default agent template since default agents
        will be created during conversion.
        """
        result: list["GridObjectConfig"] = list(self._config.objects.values())
        if self._config.agents:
            result.extend(self._config.agents)
        elif self._config.num_agents > 0:
            result.append(self._config.agent)
        return result

    def tag_names(self) -> list[str]:
        """Get all tag names in alphabetical order.

        Collects tags from:
        - GameConfig.tags (explicit tags)
        - Object/agent tags (obj.tags)
        - Auto-generated type tags (typeTag(dict_key) for objects, typeTag(name) for agents)

        Note: Must match the logic in mettagrid_c_config.py to ensure tag IDs are consistent
        between Python and C++.
        """
        all_tags = set(self._config.tags)

        # Objects: use dict key for type tag (matches C++ conversion)
        for obj_key, obj_config in self._config.objects.items():
            all_tags.update(obj_config.tags)
            all_tags.add(typeTag(obj_key))

        # Agents: use agent.name for type tag (matches C++ conversion)
        if self._config.agents:
            for agent in self._config.agents:
                all_tags.update(agent.tags)
                all_tags.add(typeTag(agent.name))
        elif self._config.num_agents > 0:
            # Default agent template
            all_tags.update(self._config.agent.tags)
            all_tags.add(typeTag(self._config.agent.name))

        return sorted(all_tags)

    def _compute_features(self) -> list[ObservationFeatureSpec]:
        """Compute observation features from the game configuration."""

        features: list[ObservationFeatureSpec] = []
        feature_id = 0

        def add_feature(name: str, normalization: float) -> None:
            nonlocal feature_id
            feat, feature_id = make_token_feature(name, feature_id, normalization)
            features.append(feat)

        # Core features (fixed set)
        add_feature("agent:group", 10.0)
        add_feature("agent:frozen", 1.0)

        # Global observation features (always included for feature_ids, config controls if populated)
        add_feature("episode_completion_pct", 255.0)
        add_feature("last_action", 10.0)
        add_feature("last_reward", 100.0)

        # Goal feature (for indicating rewarding resources)
        add_feature("goal", 100.0)

        # Agent-specific features
        add_feature("vibe", 255.0)

        # Compass direction toward hub
        add_feature("agent:compass", 1.0)

        # Tag feature (always included)
        add_feature("tag", 10.0)

        # Object features
        add_feature("cooldown_remaining", 255.0)
        add_feature("remaining_uses", 255.0)

        # Collective ID (for aligned objects)
        add_feature("collective", 10.0)

        # Local position features (directional offset from spawn)
        add_feature("lp:east", 255.0)
        add_feature("lp:west", 255.0)
        add_feature("lp:north", 255.0)
        add_feature("lp:south", 255.0)

        # Inventory features using multi-token encoding with configurable base
        # inv:{resource} = amount % token_value_base (always emitted)
        # inv:{resource}:p1 = (amount / token_value_base) % token_value_base (emitted if amount >= token_value_base)
        # inv:{resource}:p2 = (amount / token_value_base^2) % token_value_base (emitted if amount >= token_value_base^2)
        # etc.
        # Number of tokens is computed based on max uint16_t value (65535)
        token_value_base = self._config.obs.token_value_base
        num_inv_tokens = num_inventory_tokens_needed(65535, token_value_base)
        normalization = float(token_value_base)
        for resource_name in self._config.resource_names:
            token_features, feature_id = make_multi_token_features(
                f"inv:{resource_name}", feature_id, normalization, num_inv_tokens
            )
            features.extend(token_features)

        # Protocol details features (if enabled)
        if self._config.protocol_details_obs:
            for resource_name in self._config.resource_names:
                add_feature(f"protocol_input:{resource_name}", 100.0)

            for resource_name in self._config.resource_names:
                add_feature(f"protocol_output:{resource_name}", 100.0)

        # Game value observation features (multi-token encoding like inventory)
        for game_value in self._config.obs.global_obs.obs:
            if isinstance(game_value, StatValue):
                source_str = {Scope.AGENT: "own", Scope.GAME: "global", Scope.COLLECTIVE: "collective"}[
                    game_value.scope
                ]
                prefix = f"stat:{source_str}:{game_value.name}"
                if game_value.delta:
                    prefix += ":delta"
            elif isinstance(game_value, InventoryValue):
                source_str = {Scope.AGENT: "own", Scope.COLLECTIVE: "collective"}[game_value.scope]
                prefix = f"inv:{source_str}:{game_value.item}"
            elif isinstance(game_value, NumObjectsValue):
                prefix = f"num_objects:{game_value.object_type}"
            elif isinstance(game_value, TagCountValue):
                prefix = f"tag_count:{game_value.tag}"
            else:
                raise ValueError(f"Unknown GameValue type in obs: {type(game_value)}")

            token_features, feature_id = make_multi_token_features(prefix, feature_id, normalization, num_inv_tokens)
            features.extend(token_features)

        return features
