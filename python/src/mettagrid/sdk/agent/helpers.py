from __future__ import annotations

from collections import Counter
from typing import Protocol, runtime_checkable

from pydantic import BaseModel

from mettagrid.sdk.agent.state import MettagridState, SemanticEntity


class HelperCapability(BaseModel):
    name: str
    description: str


class HelperCatalog:
    def __init__(self, capabilities: list[HelperCapability]) -> None:
        self._capabilities = capabilities

    def list_capabilities(self) -> list[HelperCapability]:
        return list(self._capabilities)

    def render_capability_summary(self, max_items: int | None = None) -> str:
        capabilities = self.list_capabilities()
        if max_items is not None:
            capabilities = capabilities[:max_items]
        return "none" if not capabilities else "\n".join(f"- {item.name}: {item.description}" for item in capabilities)


_DEFAULT_STATE_HELPER_CAPABILITIES: tuple[tuple[str, str], ...] = (
    ("agent_id", "Return the current agent id."),
    ("shared_inventory", "Return the current team shared inventory."),
    ("shared_objectives", "Return the current team shared objectives."),
    ("seen_resources", "Return resource names recorded in seen_resource:* shared objectives."),
    ("missing_resources", "Return resource names recorded in missing_resource:* shared objectives."),
    ("self_attribute", "Return an attribute from sdk.state.self_state.attributes with an optional default."),
    ("position", "Return the current semantic (x, y) position."),
    ("visible_entity_counts", "Return counts of visible semantic entities by entity_type."),
    ("recent_event_types", "Return recent semantic event types in order of appearance this step window."),
    (
        "visible_entities",
        "Return visible semantic entities filtered by entity_type, label, or max_distance. "
        "Talking agents carry label='talking' plus talk_text/talk_remaining_steps attributes.",
    ),
    ("nearest_visible_entity", "Return the nearest visible semantic entity after optional filtering."),
    ("distance_to_entity", "Return Manhattan distance to one visible entity by entity_id, or None if missing."),
    ("visible_entity_ids", "Return entity ids for visible semantic entities after optional filtering."),
    ("entity_by_id", "Return one currently visible semantic entity by entity_id, or None if it is not visible."),
)


class StateHelperCatalog(HelperCatalog):
    def __init__(self, state: MettagridState, capabilities: list[HelperCapability] | None = None) -> None:
        super().__init__(
            capabilities
            if capabilities is not None
            else [
                HelperCapability(name=name, description=description)
                for name, description in _DEFAULT_STATE_HELPER_CAPABILITIES
            ]
        )
        self._state = state

    def agent_id(self) -> int:
        agent_id = self.self_attribute("agent_id", 0)
        assert isinstance(agent_id, (str, int, bool))
        return int(agent_id)

    def shared_inventory(self) -> dict[str, int]:
        return {} if self._state.team_summary is None else dict(self._state.team_summary.shared_inventory)

    def shared_objectives(self) -> list[str]:
        return [] if self._state.team_summary is None else list(self._state.team_summary.shared_objectives)

    def _objective_values(self, prefix: str) -> list[str]:
        prefix_tag = f"{prefix}:"
        return [
            objective.removeprefix(prefix_tag)
            for objective in self.shared_objectives()
            if objective.startswith(prefix_tag)
        ]

    def seen_resources(self) -> list[str]:
        return self._objective_values("seen_resource")

    def missing_resources(self) -> list[str]:
        return self._objective_values("missing_resource")

    def self_attribute(
        self,
        name: str,
        default: str | int | float | bool | None = None,
    ) -> str | int | float | bool | None:
        return self._state.self_state.attributes.get(name, default)

    def position(self) -> tuple[int, int]:
        return (self._state.self_state.position.x, self._state.self_state.position.y)

    def visible_entity_counts(self) -> dict[str, int]:
        counts = Counter(entity.entity_type for entity in self._state.visible_entities)
        return dict(sorted(counts.items()))

    def recent_event_types(self) -> list[str]:
        return list(dict.fromkeys(event.event_type for event in self._state.recent_events))

    def visible_entities(
        self,
        entity_type: str | None = None,
        label: str | None = None,
        max_distance: int | None = None,
    ) -> list[SemanticEntity]:
        return [
            entity
            for entity in self._state.visible_entities
            if entity_type is None or entity.entity_type == entity_type
            if label is None or label in entity.labels
            if max_distance is None or _entity_distance(self._state, entity) <= max_distance
        ]

    def visible_entity_ids(
        self,
        entity_type: str | None = None,
        label: str | None = None,
        max_distance: int | None = None,
    ) -> list[str]:
        return [
            entity.entity_id
            for entity in self.visible_entities(entity_type=entity_type, label=label, max_distance=max_distance)
        ]

    def entity_by_id(self, entity_id: str) -> SemanticEntity | None:
        return next((entity for entity in self._state.visible_entities if entity.entity_id == entity_id), None)

    def nearest_visible_entity(
        self,
        entity_type: str | None = None,
        label: str | None = None,
        max_distance: int | None = None,
    ) -> SemanticEntity | None:
        candidates = self.visible_entities(entity_type=entity_type, label=label, max_distance=max_distance)
        return min(
            candidates,
            key=lambda entity: (_entity_distance(self._state, entity), entity.entity_id),
            default=None,
        )

    def distance_to_entity(self, entity_id: str) -> int | None:
        return None if (entity := self.entity_by_id(entity_id)) is None else _entity_distance(self._state, entity)


@runtime_checkable
class MettagridHelpers(Protocol):
    def list_capabilities(self) -> list[HelperCapability]: ...
    def render_capability_summary(self, max_items: int | None = None) -> str: ...
    def agent_id(self) -> int: ...
    def shared_inventory(self) -> dict[str, int]: ...
    def shared_objectives(self) -> list[str]: ...
    def seen_resources(self) -> list[str]: ...
    def missing_resources(self) -> list[str]: ...
    def position(self) -> tuple[int, int]: ...
    def visible_entity_counts(self) -> dict[str, int]: ...
    def recent_event_types(self) -> list[str]: ...
    def visible_entities(
        self,
        entity_type: str | None = None,
        label: str | None = None,
        max_distance: int | None = None,
    ) -> list[SemanticEntity]: ...
    def visible_entity_ids(
        self,
        entity_type: str | None = None,
        label: str | None = None,
        max_distance: int | None = None,
    ) -> list[str]: ...
    def entity_by_id(self, entity_id: str) -> SemanticEntity | None: ...
    def nearest_visible_entity(
        self,
        entity_type: str | None = None,
        label: str | None = None,
        max_distance: int | None = None,
    ) -> SemanticEntity | None: ...
    def distance_to_entity(self, entity_id: str) -> int | None: ...
    def self_attribute(
        self,
        name: str,
        default: str | int | float | bool | None = None,
    ) -> str | int | float | bool | None: ...


def _entity_distance(state: MettagridState, entity: SemanticEntity) -> int:
    return abs(entity.position.x - state.self_state.position.x) + abs(entity.position.y - state.self_state.position.y)
