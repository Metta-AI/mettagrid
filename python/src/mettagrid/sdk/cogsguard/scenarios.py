from __future__ import annotations

from pydantic import BaseModel, Field

from mettagrid.sdk.agent import (
    GridPosition,
    KnownWorldState,
    MettagridState,
    SelfState,
    SemanticEntity,
    SemanticEvent,
    TeamSummary,
)

_DEFAULT_SHARED_INVENTORY = {
    "carbon": 10,
    "oxygen": 10,
    "germanium": 10,
    "silicon": 10,
}
_FRIENDLY_TEAM = "cogs"
_ENEMY_TEAM = "clips"


class CogsguardScenario(BaseModel):
    name: str
    states: list[MettagridState] = Field(default_factory=list)


class CogsguardScenarioBuilder:
    def scenario(self, name: str, *states: MettagridState) -> CogsguardScenario:
        return CogsguardScenario(name=name, states=list(states))

    def state(
        self,
        *,
        step: int,
        role: str,
        heart: int,
        position: tuple[int, int] = (0, 0),
        visible_entities: list[SemanticEntity] | None = None,
        extra_inventory: dict[str, int] | None = None,
        shared_inventory: dict[str, int] | None = None,
        recent_events: list[SemanticEvent] | None = None,
        known_world: KnownWorldState | None = None,
    ) -> MettagridState:
        position_x, position_y = position
        inventory = {"energy": 90, role: 1, "heart": heart, "hp": 100}
        inventory.update(extra_inventory or {})
        resolved_shared_inventory = dict(_DEFAULT_SHARED_INVENTORY)
        resolved_shared_inventory.update(shared_inventory or {})
        return MettagridState(
            game="cogsguard",
            step=step,
            self_state=SelfState(
                entity_id="agent-0",
                entity_type="agent",
                position=GridPosition(x=position_x, y=position_y),
                role=role,
                inventory=inventory,
                labels=["friendly", f"team:{_FRIENDLY_TEAM}"],
                status=[] if int(inventory["heart"]) == 0 else ["has_heart"],
                attributes={
                    "agent_id": 0,
                    "team": _FRIENDLY_TEAM,
                    "global_x": position_x,
                    "global_y": position_y,
                },
            ),
            visible_entities=list(visible_entities or []),
            known_world=known_world or KnownWorldState(frontier_regions=[]),
            team_summary=TeamSummary(team_id=_FRIENDLY_TEAM, shared_inventory=resolved_shared_inventory),
            recent_events=list(recent_events or []),
        )

    def friendly_hub(self, *, x: int = 0, y: int = 1) -> SemanticEntity:
        return self._entity(
            entity_type="hub",
            x=x,
            y=y,
            labels=["hub", "friendly"],
            attributes={"owner": _FRIENDLY_TEAM, "team": _FRIENDLY_TEAM},
        )

    def neutral_junction(self, *, x: int = 1, y: int = 0) -> SemanticEntity:
        return self._entity(
            entity_type="junction",
            x=x,
            y=y,
            labels=["junction", "neutral"],
            attributes={"owner": "neutral"},
        )

    def enemy_junction(self, *, x: int = 2, y: int = 0) -> SemanticEntity:
        return self._entity(
            entity_type="junction",
            x=x,
            y=y,
            labels=["junction", "enemy"],
            attributes={"owner": _ENEMY_TEAM},
        )

    def extractor(self, *, resource: str, x: int, y: int, friendly: bool = True) -> SemanticEntity:
        team = _FRIENDLY_TEAM if friendly else _ENEMY_TEAM
        disposition = "friendly" if friendly else "enemy"
        entity_type = f"{resource}_extractor"
        return self._entity(
            entity_type=entity_type,
            x=x,
            y=y,
            labels=[entity_type, disposition],
            attributes={"team": team},
        )

    def friendly_agent(
        self,
        *,
        entity_id: str,
        x: int,
        y: int,
        role: str,
        resources: dict[str, int] | None = None,
    ) -> SemanticEntity:
        return self._entity(
            entity_id=entity_id,
            entity_type="agent",
            x=x,
            y=y,
            labels=["agent", "friendly"],
            attributes={
                "team": _FRIENDLY_TEAM,
                "role": role,
                "agent_id": _agent_id_from_entity_id(entity_id),
                **(resources or {}),
            },
        )

    def _entity(
        self,
        *,
        entity_type: str,
        x: int,
        y: int,
        labels: list[str],
        attributes: dict[str, str | int],
        entity_id: str | None = None,
    ) -> SemanticEntity:
        return SemanticEntity(
            entity_id=f"{entity_type}@{x},{y}" if entity_id is None else entity_id,
            entity_type=entity_type,
            position=GridPosition(x=x, y=y),
            labels=list(labels),
            attributes={"global_x": x, "global_y": y, **attributes},
        )


class CogsguardScenarioPresets:
    @staticmethod
    def library() -> tuple[tuple[str, str], ...]:
        return (
            ("aligner-heart-capture", "Aligner secures heart supply before aligning a neutral junction."),
            ("miner-gather-deposit", "Miner gathers from a productive extractor, then deposits to a friendly hub."),
            ("scrambler-neutralize", "Scrambler secures a heart, then neutralizes pressure on an enemy junction."),
        )

    @staticmethod
    def aligner_heart_capture() -> CogsguardScenario:
        builder = CogsguardScenarioBuilder()
        return builder.scenario(
            "aligner-heart-capture",
            builder.state(
                step=10,
                role="aligner",
                heart=0,
                shared_inventory={"heart": 1},
                visible_entities=[builder.friendly_hub(), builder.neutral_junction()],
            ),
            builder.state(
                step=11,
                role="aligner",
                heart=1,
                position=(2, 0),
                shared_inventory={"heart": 0},
                visible_entities=[builder.friendly_hub(), builder.neutral_junction()],
            ),
        )

    @staticmethod
    def miner_gather_and_deposit(*, resource: str = "oxygen") -> CogsguardScenario:
        builder = CogsguardScenarioBuilder()
        return builder.scenario(
            "miner-gather-deposit",
            builder.state(
                step=20,
                role="miner",
                heart=0,
                visible_entities=[builder.friendly_hub(), builder.extractor(resource=resource, x=2, y=1)],
            ),
            builder.state(
                step=21,
                role="miner",
                heart=0,
                extra_inventory={resource: 40},
                visible_entities=[builder.friendly_hub(), builder.extractor(resource=resource, x=2, y=1)],
            ),
            builder.state(
                step=22,
                role="miner",
                heart=0,
                shared_inventory={resource: 50},
                visible_entities=[builder.friendly_hub(), builder.extractor(resource=resource, x=2, y=1)],
            ),
        )

    @staticmethod
    def scrambler_neutralize_enemy_junction() -> CogsguardScenario:
        builder = CogsguardScenarioBuilder()
        return builder.scenario(
            "scrambler-neutralize",
            builder.state(
                step=30,
                role="scrambler",
                heart=0,
                shared_inventory={"heart": 1},
                visible_entities=[builder.friendly_hub(), builder.enemy_junction()],
            ),
            builder.state(
                step=31,
                role="scrambler",
                heart=1,
                position=(3, 0),
                visible_entities=[builder.friendly_hub(), builder.enemy_junction()],
            ),
        )


def _agent_id_from_entity_id(entity_id: str) -> int:
    if entity_id.startswith("agent-") and entity_id.removeprefix("agent-").isdigit():
        return int(entity_id.removeprefix("agent-"))
    return 0
