from mettagrid.config.game_value import (
    CollectiveInventory,
    Inventory,
    NumObjects,
    NumTaggedObjects,
    StatsSource,
    StatsValue,
)
from mettagrid.config.reward_config import AgentReward
from mettagrid.config.tag import typeTag


def convert_agent_rewards_to_stat_rewards(
    rewards_config: dict[str, AgentReward],
    resource_name_to_id: dict[str, int],
    tag_name_to_id: dict[str, int] | None = None,
) -> tuple[dict[str, float], dict[str, float], dict[str, int], dict[str, str]]:
    """Convert rewards dict to legacy stat_rewards/stat_reward_max/stat_reward_denoms/stat_reward_stat_denoms.

    Currently supports all GameValue types for both numerators and denominators:

    Numerators (what to reward):
    - StatsValue: maps to stat_rewards with the stat name
    - Inventory: maps to {item}.amount stat
    - CollectiveInventory: maps to collective.{item}.amount stat
    - NumObjects: maps to tagcount:{tag_id} stat (C++ resolves via TagIndex)
    - NumTaggedObjects: maps to tagcount:{tag_id} stat (C++ resolves via TagIndex)

    Denominators (what to normalize by):
    - StatsValue: maps to stat_reward_stat_denoms for stat-based normalization
    - Inventory: maps to stat_reward_stat_denoms with {item}.amount
    - CollectiveInventory: maps to stat_reward_stat_denoms with collective.{item}.amount
    - NumObjects: maps to stat_reward_denoms with tag ID for object count normalization
    - NumTaggedObjects: maps to stat_reward_denoms with tag ID for object count normalization

    Caps:
    - max: maps to stat_reward_max

    Note: Only one denominator per reward is supported (C++ limitation).
    """
    stat_rewards: dict[str, float] = {}
    stat_reward_max: dict[str, float] = {}
    stat_reward_denoms: dict[str, int] = {}
    stat_reward_stat_denoms: dict[str, str] = {}
    tag_name_to_id = tag_name_to_id or {}

    for reward_name, reward in rewards_config.items():
        # Process denominators
        # C++ supports one tag-based denominator (stat_reward_denoms) OR one stat-based denominator
        # (stat_reward_stat_denoms), but not both simultaneously or multiple of either
        denom_tag_id: int | None = None
        denom_stat_name: str | None = None

        if len(reward.denoms) > 1:
            raise ValueError(
                f"Reward '{reward_name}' has {len(reward.denoms)} denominators, "
                "but C++ only supports a single denominator per reward. "
                "Consider splitting into multiple rewards."
            )

        for denom in reward.denoms:
            if isinstance(denom, StatsValue):
                # StatsValue denominator: normalize by stat value
                denom_stat_name = denom.name
                # Note: source (OWN/GLOBAL/COLLECTIVE) is handled automatically by C++
                # which sums values from agent stats, global stats, and collective stats
            elif isinstance(denom, NumObjects):
                # NumObjects denominator: normalize by count of objects with type tag
                type_tag = str(typeTag(denom.object_type))
                if type_tag not in tag_name_to_id:
                    raise ValueError(
                        f"Reward '{reward_name}' uses NumObjects('{denom.object_type}') denominator, "
                        f"but type tag '{type_tag}' is not found. Ensure the object type exists."
                    )
                denom_tag_id = tag_name_to_id[type_tag]
            elif isinstance(denom, NumTaggedObjects):
                # NumTaggedObjects denominator: normalize by count of objects with arbitrary tag
                if denom.tag not in tag_name_to_id:
                    raise ValueError(
                        f"Reward '{reward_name}' uses NumTaggedObjects('{denom.tag}') denominator, "
                        f"but tag '{denom.tag}' is not found in tag mappings."
                    )
                denom_tag_id = tag_name_to_id[denom.tag]
            elif isinstance(denom, Inventory):
                # Inventory denominator: normalize by agent's inventory amount
                item = denom.item
                if item not in resource_name_to_id:
                    raise ValueError(f"Unknown resource '{item}' in reward '{reward_name}' denominator")
                denom_stat_name = f"{item}.amount"
            elif isinstance(denom, CollectiveInventory):
                # CollectiveInventory denominator: normalize by collective's inventory amount
                item = denom.item
                if item not in resource_name_to_id:
                    raise ValueError(f"Unknown resource '{item}' in reward '{reward_name}' denominator")
                denom_stat_name = f"collective.{item}.amount"
            else:
                raise ValueError(f"Unknown GameValue type in denominator for '{reward_name}': {type(denom)}")

        # Process numerators
        for game_value in reward.nums:
            if isinstance(game_value, StatsValue):
                stat_name = game_value.name
                # Prefix with source for collective stats
                if game_value.source == StatsSource.COLLECTIVE:
                    # Collective stats are stored differently in C++
                    # They get looked up from collective->stats
                    pass  # stat_name is used as-is
                elif game_value.source == StatsSource.GLOBAL:
                    # Global stats would need special handling
                    pass  # stat_name is used as-is

                if stat_name in stat_rewards:
                    raise ValueError(f"Duplicate stat reward for '{stat_name}' in reward '{reward_name}'")
                stat_rewards[stat_name] = reward.weight
                if reward.max is not None:
                    stat_reward_max[stat_name] = reward.max
                if denom_tag_id is not None:
                    stat_reward_denoms[stat_name] = denom_tag_id
                if denom_stat_name is not None:
                    stat_reward_stat_denoms[stat_name] = denom_stat_name

            elif isinstance(game_value, Inventory):
                # Inventory rewards map to {item}.amount stats
                item = game_value.item
                if item not in resource_name_to_id:
                    raise ValueError(f"Unknown resource '{item}' in reward '{reward_name}'")
                stat_name = f"{item}.amount"
                if stat_name in stat_rewards:
                    raise ValueError(f"Duplicate inventory reward for '{item}' in reward '{reward_name}'")
                stat_rewards[stat_name] = reward.weight
                if reward.max is not None:
                    stat_reward_max[stat_name] = reward.max
                if denom_tag_id is not None:
                    stat_reward_denoms[stat_name] = denom_tag_id
                if denom_stat_name is not None:
                    stat_reward_stat_denoms[stat_name] = denom_stat_name

            elif isinstance(game_value, CollectiveInventory):
                # CollectiveInventory rewards map to collective's {item}.amount stats
                # C++ stores collective stats with "collective." prefix
                item = game_value.item
                if item not in resource_name_to_id:
                    raise ValueError(f"Unknown resource '{item}' in reward '{reward_name}'")
                stat_name = f"collective.{item}.amount"
                if stat_name in stat_rewards:
                    raise ValueError(f"Duplicate collective inventory reward for '{item}' in reward '{reward_name}'")
                stat_rewards[stat_name] = reward.weight
                if reward.max is not None:
                    stat_reward_max[stat_name] = reward.max
                if denom_tag_id is not None:
                    stat_reward_denoms[stat_name] = denom_tag_id
                if denom_stat_name is not None:
                    stat_reward_stat_denoms[stat_name] = denom_stat_name

            elif isinstance(game_value, NumObjects):
                # NumObjects numerators: reward based on count of objects with type tag
                # Use special stat name format that C++ recognizes: tagcount:{tag_id}
                type_tag = str(typeTag(game_value.object_type))
                if type_tag not in tag_name_to_id:
                    raise ValueError(
                        f"Reward '{reward_name}' uses NumObjects('{game_value.object_type}') numerator, "
                        f"but type tag '{type_tag}' is not found. Ensure the object type exists."
                    )
                tag_id = tag_name_to_id[type_tag]
                stat_name = f"tagcount:{tag_id}"
                if stat_name in stat_rewards:
                    raise ValueError(
                        f"Duplicate NumObjects reward for '{game_value.object_type}' in reward '{reward_name}'"
                    )
                stat_rewards[stat_name] = reward.weight
                if reward.max is not None:
                    stat_reward_max[stat_name] = reward.max
                if denom_tag_id is not None:
                    stat_reward_denoms[stat_name] = denom_tag_id
                if denom_stat_name is not None:
                    stat_reward_stat_denoms[stat_name] = denom_stat_name

            elif isinstance(game_value, NumTaggedObjects):
                # NumTaggedObjects numerators: reward based on count of objects with arbitrary tag
                # Use special stat name format that C++ recognizes: tagcount:{tag_id}
                if game_value.tag not in tag_name_to_id:
                    raise ValueError(
                        f"Reward '{reward_name}' uses NumTaggedObjects('{game_value.tag}') numerator, "
                        f"but tag '{game_value.tag}' is not found in tag mappings."
                    )
                tag_id = tag_name_to_id[game_value.tag]
                stat_name = f"tagcount:{tag_id}"
                if stat_name in stat_rewards:
                    raise ValueError(
                        f"Duplicate NumTaggedObjects reward for tag '{game_value.tag}' in reward '{reward_name}'"
                    )
                stat_rewards[stat_name] = reward.weight
                if reward.max is not None:
                    stat_reward_max[stat_name] = reward.max
                if denom_tag_id is not None:
                    stat_reward_denoms[stat_name] = denom_tag_id
                if denom_stat_name is not None:
                    stat_reward_stat_denoms[stat_name] = denom_stat_name

            else:
                raise ValueError(f"Unknown GameValue type in reward '{reward_name}': {type(game_value)}")

    return stat_rewards, stat_reward_max, stat_reward_denoms, stat_reward_stat_denoms
