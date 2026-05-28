from __future__ import annotations

from mettagrid.sdk.agent import GridPosition, MettagridState, SemanticEntity, SemanticEvent
from mettagrid.sdk.base import SemanticEventExtractor

_GEAR_ITEMS = ("aligner", "miner", "scrambler", "scout")


class CogsguardEventExtractor(SemanticEventExtractor):
    def extract_events(
        self,
        previous_state: MettagridState | None,
        current_state: MettagridState,
    ) -> list[SemanticEvent]:
        if previous_state is None:
            return []

        step = current_state.step or 0
        location = current_state.self_state.position
        events: list[SemanticEvent] = []

        previous_hearts = _inventory_count(previous_state, "heart")
        current_hearts = _inventory_count(current_state, "heart")
        if previous_hearts == 0 and current_hearts > 0:
            events.append(
                _event(
                    event_id=f"heart_acquired:{step}",
                    event_type="heart_acquired",
                    step=step,
                    location=location,
                    importance=0.9,
                    summary="Agent acquired a heart.",
                    evidence=[f"heart={current_hearts}"],
                )
            )
        if current_hearts < previous_hearts:
            events.append(
                _event(
                    event_id=f"heart_lost:{step}",
                    event_type="heart_lost",
                    step=step,
                    location=location,
                    importance=0.8,
                    summary="Agent lost or spent a heart.",
                    evidence=[f"previous_heart={previous_hearts}", f"current_heart={current_hearts}"],
                )
            )

        for gear in _GEAR_ITEMS:
            previous_count = _inventory_count(previous_state, gear)
            current_count = _inventory_count(current_state, gear)
            if current_count == previous_count:
                continue
            acquired = current_count > previous_count
            action = "acquired" if acquired else "lost"
            event_type = f"gear_{action}"
            events.append(
                _event(
                    event_id=f"{event_type}:{gear}:{step}",
                    event_type=event_type,
                    step=step,
                    location=location,
                    importance=0.7,
                    summary=f"Agent {action} {gear} gear.",
                    evidence=[f"gear={gear}", f"count={current_count}"],
                )
            )

        previous_enemy_ids = {entity.entity_id for entity in _enemy_entities(previous_state)}
        events.extend(
            _event(
                event_id=f"enemy_seen:{entity.entity_id}:{step}",
                event_type="enemy_seen",
                step=step,
                location=entity.position,
                importance=0.7,
                summary=f"Enemy {entity.entity_id} became visible.",
                evidence=[
                    f"team={entity.attributes.get('team', 'unknown')}",
                    f"role={entity.attributes.get('role', 'unknown')}",
                ],
            )
            for entity in _enemy_entities(current_state)
            if entity.entity_id not in previous_enemy_ids
        )

        previous_visible_ids = {entity.entity_id for entity in previous_state.visible_entities}
        new_entities = [
            entity for entity in current_state.visible_entities if entity.entity_id not in previous_visible_ids
        ]
        events.extend(
            _event(
                event_id=f"extractor_seen:{entity.entity_id}:{step}",
                event_type="extractor_seen",
                step=step,
                location=entity.position,
                importance=0.6,
                summary=f"Extractor {entity.entity_id} became visible.",
                evidence=[f"type={entity.entity_type}"],
            )
            for entity in new_entities
            if entity.entity_type.endswith("_extractor")
        )
        events.extend(
            _event(
                event_id=f"neutral_junction_seen:{entity.entity_id}:{step}",
                event_type="neutral_junction_seen",
                step=step,
                location=entity.position,
                importance=0.6,
                summary=f"Neutral junction {entity.entity_id} became visible.",
                evidence=[f"owner={entity.attributes.get('owner', 'unknown')}"],
            )
            for entity in new_entities
            if entity.entity_type == "junction" and entity.attributes.get("owner") == "neutral"
        )

        previous_junction_owners = {
            entity.entity_id: str(entity.attributes["owner"])
            for entity in previous_state.visible_entities
            if entity.entity_type == "junction"
        }
        for entity in current_state.visible_entities:
            if entity.entity_type != "junction":
                continue
            previous_owner = previous_junction_owners.get(entity.entity_id)
            if previous_owner is None:
                continue
            current_owner = str(entity.attributes["owner"])
            if previous_owner == current_owner:
                continue
            events.append(
                _event(
                    event_id=f"junction_owner_changed:{entity.entity_id}:{step}",
                    event_type="junction_owner_changed",
                    step=step,
                    location=entity.position,
                    importance=0.8,
                    summary=f"Junction ownership changed from {previous_owner} to {current_owner}.",
                    evidence=[f"previous_owner={previous_owner}", f"current_owner={current_owner}"],
                )
            )
        return events


def _enemy_entities(state: MettagridState) -> list[SemanticEntity]:
    team_summary = state.team_summary
    assert team_summary is not None
    return [
        entity
        for entity in state.visible_entities
        if entity.entity_type == "agent" and entity.attributes.get("team") != team_summary.team_id
    ]


def _inventory_count(state: MettagridState, item: str) -> int:
    return int(state.self_state.inventory.get(item, 0))


def _event(
    *,
    event_id: str,
    event_type: str,
    step: int,
    location: GridPosition,
    importance: float,
    summary: str,
    evidence: list[str],
) -> SemanticEvent:
    return SemanticEvent(
        event_id=event_id,
        event_type=event_type,
        step=step,
        location=location,
        importance=importance,
        summary=summary,
        evidence=evidence,
    )
