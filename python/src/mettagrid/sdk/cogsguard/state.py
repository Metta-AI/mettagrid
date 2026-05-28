from __future__ import annotations

from mettagrid.sdk.agent import (
    GridPosition,
    MettagridState,
    SelfState,
    SemanticEntity,
    TeamMemberSummary,
    TeamSummary,
)
from mettagrid.sdk.agent.runtime.observation import ObservationCell, ObservationEnvelope, decode_observation
from mettagrid.sdk.base import SemanticStateAdapter
from mettagrid.sdk.cogsguard.constants import COGSGUARD_ROLE_NAMES

_LOCAL_STATUS_FEATURES = {"agent:frozen": "frozen"}


class CogsguardStateAdapter(SemanticStateAdapter):
    def build_state(self, observation: ObservationEnvelope) -> MettagridState:
        decoded = decode_observation(observation)
        self_cell = decoded.self_cell
        self_team = _team_from_tags(self_cell.tags)
        assert self_team is not None
        self_inventory = _inventory_from_features(self_cell.features)
        self_agent_id = int(self_cell.features.get("agent_id", observation.raw_observation.agent_id))
        self_frozen_ticks = int(self_cell.features.get("agent:frozen", 0))
        global_x = _global_axis(decoded.global_features, positive="lp:east", negative="lp:west")
        global_y = _global_axis(decoded.global_features, positive="lp:south", negative="lp:north")
        self_state = SelfState(
            entity_id=f"agent-{self_agent_id}",
            entity_type="agent",
            position=GridPosition(x=global_x, y=global_y),
            labels=["friendly", f"team:{self_team}"],
            attributes={
                "team": self_team,
                "group": int(self_cell.features.get("agent:group", 0)),
                "agent_id": self_agent_id,
                "global_x": global_x,
                "global_y": global_y,
                "frozen": self_frozen_ticks > 0,
                "freeze_remaining": self_frozen_ticks,
                "last_action_move": int(decoded.global_features.get("last_action_move", 0)),
            },
            role=_infer_role(self_inventory),
            inventory=self_inventory,
            status=_status_from_cell(self_cell, self_inventory),
        )

        visible_entities = [
            _build_entity(cell=cell, self_team=self_team, self_global_x=global_x, self_global_y=global_y)
            for cell in decoded.cells
            if (cell.row, cell.col) != (decoded.center_row, decoded.center_col)
            if _has_type_tag(cell.tags)
        ]
        _attach_visible_talk(
            self_state=self_state,
            visible_entities=visible_entities,
            visible_talk=decoded.observation.talk,
            center_col=decoded.center_col,
            center_row=decoded.center_row,
            self_global_x=global_x,
            self_global_y=global_y,
        )
        visible_entities.sort(key=lambda entity: (entity.position.y, entity.position.x, entity.entity_id))

        team_members = [
            TeamMemberSummary(
                entity_id=entity.entity_id,
                role=str(entity.attributes["role"]),
                position=entity.position,
                status=list(entity.labels),
            )
            for entity in visible_entities
            if entity.entity_type == "agent" and entity.attributes.get("team") == self_team
        ]
        team_summary = TeamSummary(
            team_id=self_team,
            members=team_members,
            shared_inventory=_shared_inventory_from_global_features(decoded.global_features),
        )
        return MettagridState(
            game="cogsguard",
            step=decoded.step,
            self_state=self_state,
            visible_entities=visible_entities,
            team_summary=team_summary,
        )


def _build_entity(*, cell: ObservationCell, self_team: str, self_global_x: int, self_global_y: int) -> SemanticEntity:
    entity_type = _entity_type_from_tags(cell.tags)
    team = _team_from_tags(cell.tags)
    owner = (team or "neutral") if entity_type in {"agent", "hub", "junction"} else None
    inventory = _inventory_from_features(cell.features)
    global_x = self_global_x + cell.x
    global_y = self_global_y + cell.y
    labels = _labels_for_entity(entity_type=entity_type, team=team, owner=owner, self_team=self_team)
    attributes = _entity_attributes(
        entity_type=entity_type,
        team=team,
        owner=owner,
        cell=cell,
        inventory=inventory,
        global_x=global_x,
        global_y=global_y,
    )
    entity_id = _entity_id(entity_type=entity_type, cell=cell, global_x=global_x, global_y=global_y)
    return SemanticEntity(
        entity_id=entity_id,
        entity_type=entity_type,
        position=GridPosition(x=cell.x, y=cell.y),
        labels=labels,
        attributes=attributes,
    )


def _entity_id(*, entity_type: str, cell: ObservationCell, global_x: int, global_y: int) -> str:
    if entity_type == "agent" and (agent_id := cell.features.get("agent_id")) is not None:
        return f"agent-{agent_id}"
    if entity_type == "agent":
        return f"agent@{global_x},{global_y}"
    return f"{entity_type}@{global_x},{global_y}"


def _has_type_tag(tags: tuple[str, ...]) -> bool:
    return any(tag.startswith("type:") for tag in tags)


def _entity_type_from_tags(tags: tuple[str, ...]) -> str:
    type_tag = next(tag for tag in tags if tag.startswith("type:"))
    type_name = type_tag.removeprefix("type:")
    if type_name.startswith("c:"):
        type_name = type_name.removeprefix("c:")
    if type_name in {"aligner", "miner", "scout", "scrambler"}:
        return f"{type_name}_station"
    return type_name


def _entity_attributes(
    *,
    entity_type: str,
    team: str | None,
    owner: str | None,
    cell: ObservationCell,
    inventory: dict[str, int],
    global_x: int,
    global_y: int,
) -> dict[str, str | int | float | bool]:
    attributes: dict[str, str | int | float | bool] = {}
    if owner is not None:
        attributes["owner"] = owner
    if team is not None:
        attributes["team"] = team
    attributes["global_x"] = global_x
    attributes["global_y"] = global_y
    for feature_name, value in cell.features.items():
        if feature_name.startswith("inv:"):
            continue
        if feature_name == "agent:frozen":
            attributes["frozen"] = bool(value)
            attributes["freeze_remaining"] = int(value)
            continue
        attributes[feature_name] = value
    if entity_type == "agent":
        agent_id = cell.features.get("agent_id")
        if agent_id is not None:
            attributes["agent_id"] = agent_id
        attributes["role"] = _infer_role(inventory)
    for name, value in inventory.items():
        attributes[name] = value
    return attributes


def _labels_for_entity(*, entity_type: str, team: str | None, owner: str | None, self_team: str) -> list[str]:
    labels = [entity_type]
    disposition = owner if owner is not None else team
    if disposition is None or disposition == "neutral":
        labels.append("neutral")
    elif disposition == self_team:
        labels.append("friendly")
    else:
        labels.append("enemy")
    return labels


def _attach_visible_talk(
    *,
    self_state: SelfState,
    visible_entities: list[SemanticEntity],
    visible_talk,
    center_col: int,
    center_row: int,
    self_global_x: int,
    self_global_y: int,
) -> None:
    agents_by_id: dict[int, SemanticEntity] = {}
    agents_by_position: dict[tuple[int, int], SemanticEntity] = {}
    for entity in visible_entities:
        if entity.entity_type != "agent":
            continue
        agent_id = entity.attributes.get("agent_id")
        if isinstance(agent_id, int):
            agents_by_id[agent_id] = entity
        agents_by_position[(entity.position.x, entity.position.y)] = entity

    self_agent_id = self_state.attributes.get("agent_id")
    for talk in visible_talk:
        rel_x = talk.location.col - center_col
        rel_y = talk.location.row - center_row
        if isinstance(self_agent_id, int) and talk.agent_id == self_agent_id and rel_x == 0 and rel_y == 0:
            _attach_talk_fields(self_state, text=talk.text, remaining_steps=talk.remaining_steps)
            continue

        entity = agents_by_id.get(talk.agent_id) or agents_by_position.get((rel_x, rel_y))
        if entity is None:
            entity = SemanticEntity(
                entity_id=f"agent-{talk.agent_id}",
                entity_type="agent",
                position=GridPosition(x=rel_x, y=rel_y),
                labels=["agent", "talking"],
                attributes={
                    "agent_id": talk.agent_id,
                    "global_x": self_global_x + rel_x,
                    "global_y": self_global_y + rel_y,
                },
            )
            visible_entities.append(entity)
            agents_by_position[(rel_x, rel_y)] = entity
        entity.attributes["agent_id"] = talk.agent_id
        entity.entity_id = f"agent-{talk.agent_id}"
        agents_by_id[talk.agent_id] = entity
        _attach_talk_fields(entity, text=talk.text, remaining_steps=talk.remaining_steps)


def _attach_talk_fields(entity: SemanticEntity, *, text: str, remaining_steps: int) -> None:
    entity.attributes["talk_text"] = text
    entity.attributes["talk_remaining_steps"] = remaining_steps
    if "talking" not in entity.labels:
        entity.labels.append("talking")


def _team_from_tags(tags: tuple[str, ...]) -> str | None:
    for prefix in ("team:", "net:"):
        for tag in tags:
            if tag.startswith(prefix):
                return tag.removeprefix(prefix)
    return None


def _inventory_from_features(features: dict[str, int]) -> dict[str, int]:
    return {
        feature_name.removeprefix("inv:"): value
        for feature_name, value in sorted(features.items())
        if feature_name.startswith("inv:")
    }


def _shared_inventory_from_global_features(features: dict[str, int]) -> dict[str, int]:
    return {
        feature_name.removeprefix("team:"): value
        for feature_name, value in sorted(features.items())
        if feature_name.startswith("team:")
    }


def _status_from_cell(cell: ObservationCell, inventory: dict[str, int]) -> list[str]:
    status: list[str] = []
    if "heart" in inventory and inventory["heart"] > 0:
        status.append("has_heart")
    for feature_name, label in _LOCAL_STATUS_FEATURES.items():
        if feature_name in cell.features and cell.features[feature_name] > 0:
            status.append(label)
    return status


def _infer_role(inventory: dict[str, int]) -> str:
    for role in COGSGUARD_ROLE_NAMES:
        if role in inventory and inventory[role] > 0:
            return role
    return "unknown"


def _global_axis(features: dict[str, int], *, positive: str, negative: str) -> int:
    return int(features.get(positive, 0)) - int(features.get(negative, 0))
