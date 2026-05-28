from __future__ import annotations

from collections.abc import Mapping

from mettagrid.sdk.agent import MettagridState
from mettagrid.sdk.agent.progress import ProgressSnapshot
from mettagrid.sdk.cogsguard.learnings import render_cogsguard_learnings
from mettagrid.sdk.cogsguard.scenarios import CogsguardScenarioPresets

_COGSGUARD_SKILLS = (
    (
        "resource_coverage",
        "Mine missing elements, then deposit before overcarrying. "
        "resource_bias only prefers a resource type; it does not hard-lock one extractor.",
    ),
    (
        "focused_extractor_lock",
        "When one exact extractor is productive or oscillation is detected, "
        "set target_entity_id to pin that extractor until facts change.",
    ),
    (
        "teammate_shadowing",
        "If coordination requires staying together, set target_entity_id to a visible friendly agent like "
        "agent-1 to shadow them until the local situation changes.",
    ),
    (
        "region_reanchor",
        "Use target_region for west/east/frontier steering when you want lane pressure "
        "or exploration without pinning one entity yet.",
    ),
    (
        "heart_gated_alignment",
        "Aligners and scramblers should secure a heart before committing to junction pressure.",
    ),
    ("safe_deposit_cycle", "If carrying payload under pressure or low HP, route back toward a friendly hub."),
    ("lane_pressure", "Once hearts are online, convert spare pressure into aligner or scrambler lane control."),
)

_COGSGUARD_BEST_PRACTICES = (
    "Prefer one strong steering primitive at a time: target_entity_id first, then target_region, then resource_bias.",
    (
        'Use sdk.helpers.nearest_visible_entity(entity_type="junction", label="neutral") '
        "to choose one decisive focus target."
    ),
    (
        'Use sdk.helpers.visible_entities(entity_type="junction", label="enemy") '
        "to inspect lane pressure without pinning one id yet."
    ),
    (
        "Use sdk.helpers.shared_inventory() and sdk.helpers.recent_event_types() "
        "as progress signals before escalating phases or rewriting plans."
    ),
    (
        "Only use sdk.state fields and helpers that are explicitly documented; do not invent convenience flags such "
        "as sdk.state.just_deposited."
    ),
    (
        "If talk mode is enabled, the talk directive field is live: set talk to emit a short speech bubble over "
        "your cog, and nearby talking agents show up directly in visible_entities with label=talking plus "
        "talk_text/talk_remaining_steps attributes."
    ),
    (
        "If you must stay in observation range for coordination, set target_entity_id to a visible teammate "
        "entity_id such as agent-1 instead of hoping the baseline wanders nearby."
    ),
    (
        "Keep step(sdk) short and strategic; let the semantic baseline handle movement, mining, "
        "deposits, and junction actions."
    ),
    "If a target stops being productive, change directive fields or phase instead of layering more timeout ladders.",
)

_CONTROL_PRIMITIVES = (
    "role: choose miner, aligner, or scrambler to switch the semantic baseline behavior family",
    "objective: choose resource_coverage, economy_bootstrap, or aligner_pressure for the current phase",
    "target_entity_id: strongest focus primitive; use it for one exact extractor, junction, "
    "or visible entity such as a teammate agent-1 when you need to shadow them",
    "target_region: broader lane or region bias when you do not want to pin one exact entity yet",
    "resource_bias: resource-type preference among viable extractors; not a hard lock on one extractor",
    "talk: optional <=140-char coordination message; this is the canonical communication "
    "field when talk mode is enabled",
)


class CogsguardPromptAdapter:
    def render_state(self, state: MettagridState) -> str:
        self_state = state.self_state
        team_summary = state.team_summary
        assert team_summary is not None
        inventory_text = _format_mapping(self_state.inventory)
        status_text = ", ".join(self_state.status) if self_state.status else "none"
        lines = [
            "SELF",
            f"step: {state.step}",
            f"team: {team_summary.team_id}",
            f"role: {self_state.role}",
            f"position: ({self_state.position.x}, {self_state.position.y})",
            f"inventory: {inventory_text}",
            f"status: {status_text}",
            f"talk: {_format_talk(self_state.attributes)}",
            f"shared_inventory: {_format_mapping(team_summary.shared_inventory)}",
            f"shared_objectives: {', '.join(team_summary.shared_objectives) or 'none'}",
            "VISIBLE",
        ]
        for entity in state.visible_entities:
            attribute_text = _format_mapping(entity.attributes)
            label_text = ", ".join(entity.labels)
            lines.append(
                f"- {entity.entity_type} at ({entity.position.x}, {entity.position.y}) [{label_text}] {attribute_text}"
            )
        if state.recent_events:
            lines.append("RECENT_EVENTS")
            for event in state.recent_events:
                lines.append(f"- {event.event_type}: {event.summary}")
        return "\n".join(lines)

    def render_skill_library(self) -> str:
        return "\n".join(
            [
                "SKILLS",
                *_render_pairs(_COGSGUARD_SKILLS),
                "CONTROL_PRIMITIVES",
                *_render_lines(_CONTROL_PRIMITIVES),
                "BEST_PRACTICES",
                *_render_lines(_COGSGUARD_BEST_PRACTICES),
            ]
        )

    def render_reference_notes(self, *, objective: str, progress: ProgressSnapshot | None = None) -> str:
        return "\n".join(
            [
                "SCENARIO_PRESETS",
                *_render_pairs(CogsguardScenarioPresets.library()),
                "TACTICAL_LEARNINGS",
                render_cogsguard_learnings(objective=objective, progress=progress, limit=4),
            ]
        )


def _format_mapping(values: Mapping[str, str | int | float | bool]) -> str:
    if not values:
        return "none"
    return ", ".join(f"{key}={values[key]}" for key in sorted(values))


def _format_talk(attributes: Mapping[str, str | int | float | bool]) -> str:
    talk_text = attributes.get("talk_text")
    if not isinstance(talk_text, str) or not talk_text:
        return "none"
    remaining_steps = attributes.get("talk_remaining_steps", 0)
    return f"{talk_text} (ttl={remaining_steps})"


def _render_lines(lines: tuple[str, ...]) -> list[str]:
    return [f"- {line}" for line in lines]


def _render_pairs(lines: tuple[tuple[str, str], ...]) -> list[str]:
    return [f"- {name}: {description}" for name, description in lines]
