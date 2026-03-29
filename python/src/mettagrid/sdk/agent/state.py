from __future__ import annotations

from pydantic import BaseModel, Field


class GridPosition(BaseModel):
    x: int
    y: int

    def __getitem__(self, key: int | str) -> int:
        if key == 0 or key == "x":
            return self.x
        if key == 1 or key == "y":
            return self.y
        raise (IndexError if isinstance(key, int) else KeyError)(key)


class SemanticEntity(BaseModel):
    entity_id: str
    entity_type: str
    position: GridPosition
    labels: list[str] = Field(default_factory=list)
    attributes: dict[str, str | int | float | bool] = Field(default_factory=dict)

    def __getitem__(self, key: str) -> str | GridPosition | list[str] | dict[str, str | int | float | bool]:
        if key in {"entity_id", "entity_type", "position", "labels", "attributes"}:
            return getattr(self, key)
        raise KeyError(key)


class SelfState(SemanticEntity):
    role: str | None = None
    inventory: dict[str, int] = Field(default_factory=dict)
    status: list[str] = Field(default_factory=list)


class KnownWorldState(BaseModel):
    explored_regions: list[str] = Field(default_factory=list)
    frontier_regions: list[str] = Field(default_factory=list)
    contested_regions: list[str] = Field(default_factory=list)


class TeamMemberSummary(BaseModel):
    entity_id: str
    role: str
    position: GridPosition
    status: list[str] = Field(default_factory=list)


class TeamSummary(BaseModel):
    team_id: str
    members: list[TeamMemberSummary] = Field(default_factory=list)
    shared_inventory: dict[str, int] = Field(default_factory=dict)
    shared_objectives: list[str] = Field(default_factory=list)


class SemanticEvent(BaseModel):
    event_id: str
    event_type: str
    step: int
    location: GridPosition | None = None
    importance: float = 0.0
    summary: str
    evidence: list[str] = Field(default_factory=list)


class MettagridState(BaseModel):
    game: str
    step: int | None = None
    self_state: SelfState
    visible_entities: list[SemanticEntity] = Field(default_factory=list)
    known_world: KnownWorldState = Field(default_factory=KnownWorldState)
    team_summary: TeamSummary | None = None
    recent_events: list[SemanticEvent] = Field(default_factory=list)
