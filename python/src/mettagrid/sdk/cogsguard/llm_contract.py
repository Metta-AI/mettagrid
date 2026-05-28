from __future__ import annotations

import json
from enum import Enum
from typing import Literal, Sequence, TypeVar

from pydantic import BaseModel, ConfigDict, Field, field_validator

_RESOURCE_NAMES = ("carbon", "oxygen", "germanium", "silicon")
ResourceName = Literal["carbon", "oxygen", "germanium", "silicon"]


class StrategyMode(str, Enum):
    BOOTSTRAP_ECONOMY = "bootstrap_economy"
    COVER_MISSING_RESOURCES = "cover_missing_resources"
    FRONTIER_EXPAND = "frontier_expand"
    CONVERT_FRONTIER = "convert_frontier"
    SCRAMBLE_PRESSURE = "scramble_pressure"
    RECOVER_AND_BANK = "recover_and_bank"


class SkillName(str, Enum):
    GEAR_UP_MINER = "gear_up_miner"
    GEAR_UP_ALIGNER = "gear_up_aligner"
    GEAR_UP_SCRAMBLER = "gear_up_scrambler"
    MINE_BIASED_RESOURCE = "mine_biased_resource"
    DEPOSIT_RESOURCES = "deposit_resources"
    GET_HEART = "get_heart"
    ALIGN_FRONTIER = "align_frontier"
    SCRAMBLE_FRONTIER = "scramble_frontier"
    EXPLORE = "explore"
    RETREAT = "retreat"
    UNSTUCK = "unstuck"


class SkillStatus(str, Enum):
    ACTIVE = "active"
    READY = "ready"
    SETUP = "setup"
    BLOCKED = "blocked"


_MODE_DESCRIPTIONS: tuple[tuple[StrategyMode, str], ...] = (
    (StrategyMode.BOOTSTRAP_ECONOMY, "Stabilize hearts and gear before committing heavily to pressure roles."),
    (
        StrategyMode.COVER_MISSING_RESOURCES,
        "Prioritize broad resource collection and suppress pressure until shortages are fixed.",
    ),
    (StrategyMode.FRONTIER_EXPAND, "Favor exploration and neutral-frontier discovery."),
    (StrategyMode.CONVERT_FRONTIER, "Favor turning known frontier junctions into held territory."),
    (StrategyMode.SCRAMBLE_PRESSURE, "Lean into scrambler pressure when enemy junction denial is valuable."),
    (StrategyMode.RECOVER_AND_BANK, "Prefer safety, deposits, and rebuilding after losses or low HP."),
)

_SKILL_DESCRIPTIONS: tuple[tuple[SkillName, str], ...] = (
    (SkillName.GEAR_UP_MINER, "Acquire or fund miner gear."),
    (SkillName.GEAR_UP_ALIGNER, "Acquire or fund aligner gear."),
    (SkillName.GEAR_UP_SCRAMBLER, "Acquire or fund scrambler gear."),
    (SkillName.MINE_BIASED_RESOURCE, "Mine the current deterministic resource target."),
    (SkillName.DEPOSIT_RESOURCES, "Deposit carried resources to a safe friendly depot or hub."),
    (SkillName.GET_HEART, "Acquire a heart or rebuild the shared economy if hearts cannot be refilled yet."),
    (SkillName.ALIGN_FRONTIER, "Move toward the best deterministic alignable frontier junction."),
    (SkillName.SCRAMBLE_FRONTIER, "Move toward the best deterministic enemy scramble target."),
    (SkillName.EXPLORE, "Reveal map area using the current role-specific explore pattern."),
    (SkillName.RETREAT, "Return toward safety when low HP or carrying valuable payload."),
    (SkillName.UNSTUCK, "Use the deterministic unstuck escape pattern."),
)


class JunctionSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    friendly: int
    enemy: int
    neutral: int


class PlannerSkillOption(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: SkillName
    status: SkillStatus
    reason: str
    preferred_role: str | None = None


class PlannerSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    step: int
    agent_id: int
    hp: int
    position: tuple[int, int]
    role: str
    strategy_mode: StrategyMode | None = None
    active_skill: SkillName | None = None
    resource_bias: ResourceName
    team_resources: dict[str, int]
    inventory: dict[str, int]
    junctions: JunctionSnapshot
    safe_distance: int
    stalled: bool
    oscillating: bool
    has_gear: bool
    emergency_mining: bool
    roles: str = ""
    active_skill_steps: int = 0
    last_skill_exit_reason: str = ""
    recent_events: list[str] = Field(default_factory=list)
    skill_options: list[PlannerSkillOption] = Field(default_factory=list)
    visible_talk: list[str] = Field(default_factory=list)
    talk_enabled: bool = False
    talk_cooldown_steps: int = 0


class PlannerDirective(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: StrategyMode
    skill: SkillName
    resource_bias: ResourceName | None = None
    talk: str | None = None
    analysis: str = ""

    @field_validator("talk")
    @classmethod
    def _normalize_talk(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = " ".join(value.split()).strip()
        return normalized[:140] or None

    @field_validator("analysis")
    @classmethod
    def _normalize_analysis(cls, value: str) -> str:
        return " ".join(value.split()).strip()[:280]


def render_planner_library() -> str:
    mode_lines = [f"- {mode.value}: {description}" for mode, description in _MODE_DESCRIPTIONS]
    skill_lines = [f"- {skill.value}: {description}" for skill, description in _SKILL_DESCRIPTIONS]
    return "\n".join(
        [
            "STRATEGY_MODES",
            *mode_lines,
            "SKILLS",
            *skill_lines,
            "COMMUNICATION",
            (
                "- talk: optional short coordination message for nearby teammates; "
                "omit it when there is nothing new to say"
            ),
            "SKILL_STATUS",
            "- active: currently running; usually let it finish unless the situation changed",
            "- ready: can do the main job immediately",
            "- setup: valid pick, but the runtime will first handle prerequisites",
            "- blocked: avoid this choice right now",
        ]
    )


def render_skill_options(options: Sequence[PlannerSkillOption]) -> str:
    lines = ["SKILL_OPTIONS"]
    if not options:
        lines.append("- none")
        return "\n".join(lines)
    for option in options:
        role_suffix = "" if option.preferred_role is None else f", role={option.preferred_role}"
        lines.append(f"- {option.name.value} [{option.status.value}{role_suffix}]: {option.reason}")
    return "\n".join(lines)


def preferred_role_for_skill(skill: SkillName | None) -> str | None:
    if skill in {SkillName.GEAR_UP_ALIGNER, SkillName.GET_HEART, SkillName.ALIGN_FRONTIER}:
        return "aligner"
    if skill in {SkillName.GEAR_UP_MINER, SkillName.MINE_BIASED_RESOURCE, SkillName.DEPOSIT_RESOURCES}:
        return "miner"
    if skill in {SkillName.GEAR_UP_SCRAMBLER, SkillName.SCRAMBLE_FRONTIER}:
        return "scrambler"
    return None


def resource_names() -> tuple[str, ...]:
    return _RESOURCE_NAMES


def _default_skill_for_mode(mode: StrategyMode) -> SkillName:
    if mode is StrategyMode.BOOTSTRAP_ECONOMY:
        return SkillName.GEAR_UP_MINER
    if mode is StrategyMode.COVER_MISSING_RESOURCES:
        return SkillName.MINE_BIASED_RESOURCE
    if mode is StrategyMode.CONVERT_FRONTIER:
        return SkillName.ALIGN_FRONTIER
    if mode is StrategyMode.SCRAMBLE_PRESSURE:
        return SkillName.SCRAMBLE_FRONTIER
    if mode is StrategyMode.RECOVER_AND_BANK:
        return SkillName.DEPOSIT_RESOURCES
    return SkillName.EXPLORE


def _default_mode_for_skill(skill: SkillName) -> StrategyMode:
    if skill in {SkillName.GEAR_UP_MINER, SkillName.GEAR_UP_ALIGNER, SkillName.GEAR_UP_SCRAMBLER}:
        return StrategyMode.BOOTSTRAP_ECONOMY
    if skill in {SkillName.MINE_BIASED_RESOURCE, SkillName.GET_HEART}:
        return StrategyMode.COVER_MISSING_RESOURCES
    if skill is SkillName.ALIGN_FRONTIER:
        return StrategyMode.CONVERT_FRONTIER
    if skill is SkillName.SCRAMBLE_FRONTIER:
        return StrategyMode.SCRAMBLE_PRESSURE
    if skill in {SkillName.DEPOSIT_RESOURCES, SkillName.RETREAT, SkillName.UNSTUCK}:
        return StrategyMode.RECOVER_AND_BANK
    return StrategyMode.FRONTIER_EXPAND


def _extract_first_json_object(text: str) -> dict | None:
    normalized = text.replace("```json", "").replace("```JSON", "").replace("```", "")
    decoder = json.JSONDecoder()
    for index, char in enumerate(normalized):
        if char != "{":
            continue
        try:
            parsed, _ = decoder.raw_decode(normalized[index:])
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return parsed
    return None


E = TypeVar("E", bound=Enum)


def _extract_enum_value(text: str, enum_type: type[E]) -> E | None:
    for member in enum_type:
        if member.value in text:
            return member
    return None


def _extract_resource_bias(text: str) -> ResourceName | None:
    for resource_name in _RESOURCE_NAMES:
        if f'"resource_bias":"{resource_name}"' in text or f'"resource_bias": "{resource_name}"' in text:
            return resource_name
    return None


def _fallback_planner_directive(text: str) -> PlannerDirective:
    mode = _extract_enum_value(text, StrategyMode)
    skill = _extract_enum_value(text, SkillName)
    if mode is None and skill is not None:
        mode = _default_mode_for_skill(skill)
    if skill is None and mode is not None:
        skill = _default_skill_for_mode(mode)
    if mode is None:
        mode = StrategyMode.FRONTIER_EXPAND
    if skill is None:
        skill = _default_skill_for_mode(mode)
    return PlannerDirective(
        mode=mode,
        skill=skill,
        resource_bias=_extract_resource_bias(text),
        analysis=text,
    )


def build_planner_prompt(summary: PlannerSummary) -> str:
    current_mode = "default" if summary.strategy_mode is None else summary.strategy_mode.value
    current_skill = "none" if summary.active_skill is None else summary.active_skill.value
    talk_text = "none" if not summary.visible_talk else "; ".join(summary.visible_talk[:4])
    recent_events_text = (
        "none" if not summary.recent_events else "\n".join(f"- {event}" for event in summary.recent_events)
    )
    active_exit_text = summary.last_skill_exit_reason or "none"
    lines = [
        f"CvC game step {summary.step}/10000. 88x88 map, variable same-policy team size in tournament pods.",
        "Score = junctions held over time. MAXIMIZE friendly junctions held.",
        "",
        (
            f"Agent {summary.agent_id}: HP={summary.hp}, "
            f"Hearts={int(summary.inventory.get('heart', 0))}, Role={summary.role}"
        ),
        f"Position: {summary.position}",
        f"Current mode: {current_mode}",
        f"Current active skill: {current_skill} (steps={summary.active_skill_steps})",
        f"Last skill exit: {active_exit_text}",
        f"Current resource bias: {summary.resource_bias}",
        f"Inventory: {summary.inventory}",
        f"Team resources: {summary.team_resources}",
        f"Observed same-team roles: {summary.roles or 'unknown'}",
        (
            f"Junctions: friendly={summary.junctions.friendly} "
            f"enemy={summary.junctions.enemy} neutral={summary.junctions.neutral}"
        ),
        f"Stalled: {summary.stalled}, Oscillating: {summary.oscillating}",
        f"Safe distance to hub: {summary.safe_distance}",
        f"Has role gear: {summary.has_gear}, Emergency mining: {summary.emergency_mining}",
        f"Visible teammate talk: {talk_text}",
        f"Talk enabled: {summary.talk_enabled}, talk cooldown steps: {summary.talk_cooldown_steps}",
        "",
        "RECENT_EVENTS",
        recent_events_text,
        "",
        render_skill_options(summary.skill_options),
        "",
        render_planner_library(),
    ]
    lines.append(
        "\nChoose one bounded strategy mode and one bounded skill."
        "\nThe runtime owns navigation, targeting, claims, and safety checks."
        "\nDo not invent mode names, skill names, raw coordinates, or policy code."
        "\nStart your response with { and end it with }. No prose before or after. No markdown fences."
        "\nRespond with ONLY a JSON object like:"
        '\n{"mode":"frontier_expand","skill":"align_frontier","resource_bias":"oxygen",'
        '"talk":"claim east frontier","analysis":"..."}'
        "\nRules:"
        "\n- Pick exactly one mode and one skill from the library."
        "\n- Prefer READY skills. SETUP skills are allowed when you intentionally want the runtime "
        "to handle prerequisites."
        "\n- Avoid BLOCKED skills."
        "\n- Use talk only for short coordination intent. Leave it null when there is nothing new to say."
        "\n- Prefer local, communication-based coordination that still works with unknown teammates."
        "\n- resource_bias is optional; omit it unless changing the mining priority helps."
    )
    return "\n".join(lines)


def parse_planner_response(text: str) -> PlannerDirective:
    candidate = text.strip()
    parsed = _extract_first_json_object(candidate)
    if isinstance(parsed, dict):
        try:
            return PlannerDirective.model_validate(parsed)
        except Exception:
            pass
    return _fallback_planner_directive(candidate)
