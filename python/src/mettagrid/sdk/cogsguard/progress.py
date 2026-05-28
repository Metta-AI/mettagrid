from __future__ import annotations

from collections.abc import Collection
from dataclasses import dataclass

from mettagrid.sdk.agent.progress import ProgressSnapshot
from mettagrid.sdk.agent.state import MettagridState, SemanticEntity, SemanticEvent

_RESOURCE_TYPES = ("carbon", "oxygen", "germanium", "silicon")
_RESOURCE_STALL_STEPS = 16
_BOOTSTRAP_STALL_STEPS = 24
_PRESSURE_STALL_STEPS = 24


@dataclass(slots=True)
class _ResourceProgressState:
    best_types_seen: int = 0
    best_units: int = 0
    last_progress_step: int | None = None


@dataclass(slots=True)
class _ScalarProgressState:
    best_value: int = 0
    last_progress_step: int | None = None


class CogsguardProgressTracker:
    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        self._current_objective = ""
        self._objective_started_at: int | None = None
        self._last_step: int | None = None
        self._resource_progress = _ResourceProgressState()
        self._heart_progress = _ScalarProgressState()
        self._map_control_progress = _ScalarProgressState()
        self._last_any_progress_step: int | None = None

    def snapshot(
        self,
        state: MettagridState,
        *,
        objective: str,
        seen_resources: Collection[str],
        missing_resources: Collection[str],
    ) -> ProgressSnapshot:
        step = 0 if state.step is None else state.step
        if self._last_step is not None and step < self._last_step:
            self.reset()

        if objective != self._current_objective or self._objective_started_at is None:
            self._current_objective = objective
            self._objective_started_at = step
            self._reset_objective_progress()
        objective_age_steps = step - self._objective_started_at

        resource_types_seen = len(seen_resources)
        resource_types_missing = len(missing_resources)
        team_resource_units = _team_resource_units(state)
        heart_total = _heart_total(state)
        friendly_junctions_visible, neutral_junctions_visible, enemy_junctions_visible = _junction_counts(state)
        enemy_agents_visible = _enemy_agents_visible(state)
        friendly_capture_event = _has_friendly_capture_event(state)

        milestones: list[str] = []
        resource_progress = _update_resource_progress(
            self._resource_progress,
            step=step,
            resource_types_seen=resource_types_seen,
            team_resource_units=team_resource_units,
            milestones=milestones,
        )
        heart_progress = _update_scalar_progress(
            self._heart_progress,
            step=step,
            value=heart_total,
            milestone=f"hearts ready: {heart_total}",
            milestones=milestones,
        )
        map_control_progress = _update_map_control_progress(
            self._map_control_progress,
            step=step,
            friendly_junctions_visible=friendly_junctions_visible,
            friendly_capture_event=friendly_capture_event,
            milestones=milestones,
        )
        any_progress = resource_progress or heart_progress or map_control_progress
        if any_progress or self._last_any_progress_step is None:
            self._last_any_progress_step = step

        (
            steps_since_resource_progress,
            steps_since_heart_progress,
            steps_since_map_control_progress,
            steps_since_any_progress,
        ) = (
            _steps_since(step=step, objective_age_steps=objective_age_steps, last_progress_step=last_progress_step)
            for last_progress_step in (
                self._resource_progress.last_progress_step,
                self._heart_progress.last_progress_step,
                self._map_control_progress.last_progress_step,
                self._last_any_progress_step,
            )
        )

        progress_stalled = _progress_stalled(
            objective=objective,
            resource_types_missing=resource_types_missing,
            heart_total=heart_total,
            steps_since_resource_progress=steps_since_resource_progress,
            steps_since_heart_progress=steps_since_heart_progress,
            steps_since_map_control_progress=steps_since_map_control_progress,
        )
        if progress_stalled:
            milestones.append("objective appears stalled")

        summary = _render_summary(
            objective=objective,
            resource_types_seen=resource_types_seen,
            resource_types_missing=resource_types_missing,
            team_resource_units=team_resource_units,
            heart_total=heart_total,
            friendly_junctions_visible=friendly_junctions_visible,
            neutral_junctions_visible=neutral_junctions_visible,
            enemy_agents_visible=enemy_agents_visible,
            steps_since_resource_progress=steps_since_resource_progress,
            steps_since_heart_progress=steps_since_heart_progress,
            steps_since_map_control_progress=steps_since_map_control_progress,
            progress_stalled=progress_stalled,
        )

        self._last_step = step
        return ProgressSnapshot(
            objective=objective,
            summary=summary,
            milestones=milestones,
            metrics={
                "enemy_agents_visible": enemy_agents_visible,
                "enemy_junctions_visible": enemy_junctions_visible,
                "friendly_junctions_visible": friendly_junctions_visible,
                "heart_total": heart_total,
                "neutral_junctions_visible": neutral_junctions_visible,
                "objective_age_steps": objective_age_steps,
                "progress_stalled": progress_stalled,
                "resource_types_missing": resource_types_missing,
                "resource_types_seen": resource_types_seen,
                "steps_since_any_progress": steps_since_any_progress,
                "steps_since_heart_progress": steps_since_heart_progress,
                "steps_since_map_control_progress": steps_since_map_control_progress,
                "steps_since_resource_progress": steps_since_resource_progress,
                "team_resource_units": team_resource_units,
            },
        )

    def _reset_objective_progress(self) -> None:
        self._resource_progress = _ResourceProgressState()
        self._heart_progress = _ScalarProgressState()
        self._map_control_progress = _ScalarProgressState()
        self._last_any_progress_step = None


def _update_resource_progress(
    progress: _ResourceProgressState,
    *,
    step: int,
    resource_types_seen: int,
    team_resource_units: int,
    milestones: list[str],
) -> bool:
    if progress.last_progress_step is None:
        progress.best_types_seen = resource_types_seen
        progress.best_units = team_resource_units
        progress.last_progress_step = step
        return False

    changed = False
    if resource_types_seen > progress.best_types_seen:
        progress.best_types_seen = resource_types_seen
        changed = True
        milestones.append(f"resource types touched: {resource_types_seen}")
    if team_resource_units > progress.best_units:
        progress.best_units = team_resource_units
        changed = True
        milestones.append(f"team resource units: {team_resource_units}")
    if changed:
        progress.last_progress_step = step
    return changed


def _update_scalar_progress(
    progress: _ScalarProgressState,
    *,
    step: int,
    value: int,
    milestone: str,
    milestones: list[str],
) -> bool:
    if progress.last_progress_step is None:
        progress.best_value = value
        progress.last_progress_step = step
        return False

    if value <= progress.best_value:
        return False
    progress.best_value = value
    progress.last_progress_step = step
    milestones.append(milestone)
    return True


def _update_map_control_progress(
    progress: _ScalarProgressState,
    *,
    step: int,
    friendly_junctions_visible: int,
    friendly_capture_event: bool,
    milestones: list[str],
) -> bool:
    if progress.last_progress_step is None:
        progress.best_value = friendly_junctions_visible
        progress.last_progress_step = step
        return False

    if friendly_junctions_visible <= progress.best_value and not friendly_capture_event:
        return False
    progress.best_value = max(progress.best_value, friendly_junctions_visible)
    progress.last_progress_step = step
    milestones.append(f"friendly junctions visible: {friendly_junctions_visible}")
    return True


def _steps_since(*, step: int, objective_age_steps: int, last_progress_step: int | None) -> int:
    if last_progress_step is None:
        return objective_age_steps
    return min(step - last_progress_step, objective_age_steps)


def _progress_stalled(
    *,
    objective: str,
    resource_types_missing: int,
    heart_total: int,
    steps_since_resource_progress: int,
    steps_since_heart_progress: int,
    steps_since_map_control_progress: int,
) -> bool:
    return {
        "resource_coverage": resource_types_missing > 0 and steps_since_resource_progress >= _RESOURCE_STALL_STEPS,
        "economy_bootstrap": (
            heart_total == 0
            and steps_since_heart_progress >= _BOOTSTRAP_STALL_STEPS
            and steps_since_resource_progress >= _BOOTSTRAP_STALL_STEPS
        ),
        "aligner_pressure": steps_since_map_control_progress >= _PRESSURE_STALL_STEPS,
    }.get(objective, False)


def _render_summary(
    *,
    objective: str,
    resource_types_seen: int,
    resource_types_missing: int,
    team_resource_units: int,
    heart_total: int,
    friendly_junctions_visible: int,
    neutral_junctions_visible: int,
    enemy_agents_visible: int,
    steps_since_resource_progress: int,
    steps_since_heart_progress: int,
    steps_since_map_control_progress: int,
    progress_stalled: bool,
) -> str:
    if objective == "resource_coverage":
        if progress_stalled:
            return (
                f"coverage stalled: {resource_types_missing} resources still missing; "
                f"no resource gain for {steps_since_resource_progress} steps."
            )
        if resource_types_missing == 0:
            return "coverage complete: all resource types have been touched."
        return f"coverage active: {resource_types_seen} resources touched; {resource_types_missing} still missing."
    if objective == "economy_bootstrap":
        if progress_stalled:
            return (
                "bootstrap stalled: no hearts ready and no new economy progress for "
                f"{max(steps_since_heart_progress, steps_since_resource_progress)} steps."
            )
        return f"bootstrap active: hearts ready={heart_total}; team resources={team_resource_units}."
    if objective == "aligner_pressure":
        if progress_stalled:
            return f"pressure stalled: no map-control gain for {steps_since_map_control_progress} steps."
        return (
            "pressure active: "
            f"friendly junctions={friendly_junctions_visible}; "
            f"neutral targets={neutral_junctions_visible}; "
            f"enemy agents visible={enemy_agents_visible}."
        )
    return f"{objective}: no progress summary available."


def _team_resource_units(state: MettagridState) -> int:
    team_inventory = {} if state.team_summary is None else state.team_summary.shared_inventory
    return sum(int(team_inventory[resource]) for resource in _RESOURCE_TYPES if resource in team_inventory) + sum(
        int(state.self_state.inventory[resource])
        for resource in _RESOURCE_TYPES
        if resource in state.self_state.inventory
    )


def _heart_total(state: MettagridState) -> int:
    team_inventory = {} if state.team_summary is None else state.team_summary.shared_inventory
    return (int(state.self_state.inventory["heart"]) if "heart" in state.self_state.inventory else 0) + (
        int(team_inventory["heart"]) if "heart" in team_inventory else 0
    )


def _junction_counts(state: MettagridState) -> tuple[int, int, int]:
    team_id = _team_id(state)
    junction_owners = [_entity_owner(entity) for entity in state.visible_entities if entity.entity_type == "junction"]
    return (
        sum(owner == team_id for owner in junction_owners),
        sum(owner in {"", "neutral"} for owner in junction_owners),
        sum(owner not in {"", "neutral", team_id} for owner in junction_owners),
    )


def _enemy_agents_visible(state: MettagridState) -> int:
    team_id = _team_id(state)
    return sum(
        entity.entity_type == "agent"
        and (("team" in entity.attributes and str(entity.attributes["team"]) != team_id) or "enemy" in entity.labels)
        for entity in state.visible_entities
    )


def _has_friendly_capture_event(state: MettagridState) -> bool:
    team_id = _team_id(state)
    return any(
        event.event_type == "junction_owner_changed" and _event_evidence_value(event, "current_owner") == team_id
        for event in state.recent_events
    )


def _event_evidence_value(event: SemanticEvent, key: str) -> str | None:
    prefix = f"{key}="
    return next((item.removeprefix(prefix) for item in event.evidence if item.startswith(prefix)), None)


def _entity_owner(entity: SemanticEntity) -> str:
    return str(entity.attributes["owner"]) if "owner" in entity.attributes else "neutral"


def _team_id(state: MettagridState) -> str:
    if state.team_summary is not None:
        return state.team_summary.team_id
    return str(state.self_state.attributes["team"]) if "team" in state.self_state.attributes else ""
