from __future__ import annotations

from pydantic import BaseModel, Field

from mettagrid.sdk.agent.progress import ProgressSnapshot


class CogsguardLearning(BaseModel):
    learning_id: str
    summary: str
    objectives: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)


_COGSGUARD_LEARNINGS = (
    CogsguardLearning(
        learning_id="single_steering_primitive",
        summary=(
            "Prefer one steering primitive at a time: target_entity_id first, then target_region, then resource_bias."
        ),
        tags=["directive"],
    ),
    CogsguardLearning(
        learning_id="resource_bias_not_lock",
        summary=(
            "resource_bias is only a preference over viable extractors; "
            "use target_entity_id when one exact extractor should stay pinned."
        ),
        tags=["directive"],
    ),
    CogsguardLearning(
        learning_id="coverage_escape_hatch",
        summary=(
            "If resource coverage stalls after partial discovery, "
            "add a time or resource escape hatch instead of waiting forever for all four elements."
        ),
        objectives=["resource_coverage"],
        tags=["stalled", "opening"],
    ),
    CogsguardLearning(
        learning_id="bootstrap_needs_hearts",
        summary=(
            "If economy_bootstrap keeps banking resources while hearts stay at zero, "
            "retarget toward heart production or phase out instead of only waiting longer."
        ),
        objectives=["economy_bootstrap"],
        tags=["stalled", "heart_economy"],
    ),
    CogsguardLearning(
        learning_id="pressure_needs_map_change",
        summary=(
            "If aligner pressure shows no map-control gain, "
            "change target_region, role, or phase instead of pinning one lane forever."
        ),
        objectives=["aligner_pressure"],
        tags=["stalled", "map_control"],
    ),
    CogsguardLearning(
        learning_id="heart_gated_junctions",
        summary=(
            "Aligner and scrambler junction pressure is heart gated; "
            "secure heart supply before committing to neutral or enemy junctions."
        ),
        objectives=["economy_bootstrap", "aligner_pressure"],
        tags=["heart_economy"],
    ),
)


def select_cogsguard_learnings(
    *,
    objective: str,
    progress: ProgressSnapshot | None = None,
    limit: int = 4,
) -> list[CogsguardLearning]:
    stalled = progress is not None and bool(progress.metric("progress_stalled", False))
    scored: list[tuple[int, int, CogsguardLearning]] = []
    for index, learning in enumerate(_COGSGUARD_LEARNINGS):
        if learning.objectives and objective not in learning.objectives:
            if "directive" not in learning.tags:
                continue
        score = 0
        if not learning.objectives:
            score += 2
        if objective in learning.objectives:
            score += 5
        if stalled and "stalled" in learning.tags:
            score += 6
        if not stalled and "stalled" in learning.tags:
            score -= 3
        if (
            progress is not None
            and "heart_economy" in learning.tags
            and int(progress.metric("heart_total", 0) or 0) == 0
        ):
            score += 2
        scored.append((score, index, learning))
    scored.sort(key=lambda item: (-item[0], item[1]))
    return [learning for _, _, learning in scored[:limit]]


def render_cogsguard_learnings(
    *,
    objective: str,
    progress: ProgressSnapshot | None = None,
    limit: int = 4,
) -> str:
    learnings = select_cogsguard_learnings(objective=objective, progress=progress, limit=limit)
    if not learnings:
        return "- none"
    return "\n".join(f"- {learning.summary}" for learning in learnings)
