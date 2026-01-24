"""Attack mutation configuration."""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from pydantic import Field

from mettagrid.config.mutation.mutation import Mutation

if TYPE_CHECKING:
    from mettagrid.config.mutation.mutation import AnyMutation


class AttackMutation(Mutation):
    """Combat mutation with weapon/armor/defense mechanics.

    Defense calculation:
    - weapon_power = sum(attacker_inventory[item] * weapon_weight)
    - armor_power = sum(target_inventory[item] * armor_weight) + vibe_bonus if vibing
    - damage_bonus = max(weapon_power - armor_power, 0)
    - cost_to_defend = defense_resources + damage_bonus

    If target can defend, defense resources are consumed and attack is blocked.
    Otherwise, on_success mutations are applied.
    """

    mutation_type: Literal["attack"] = "attack"
    defense_resources: dict[str, int] = Field(
        default_factory=dict,
        description="Resources target needs to block the attack",
    )
    armor_resources: dict[str, int] = Field(
        default_factory=dict,
        description="Target resources that reduce damage (resource -> weight)",
    )
    weapon_resources: dict[str, int] = Field(
        default_factory=dict,
        description="Attacker resources that increase damage (resource -> weight)",
    )
    vibe_bonus: dict[str, int] = Field(
        default_factory=dict,
        description="Per-vibe armor bonus when vibing a matching resource",
    )
    on_success: list["AnyMutation"] = Field(
        default_factory=list,
        description="Mutations to apply when attack succeeds",
    )


# Note: model_rebuild() is called in __init__.py after AnyMutation is defined
