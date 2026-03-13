from __future__ import annotations

from typing import Any


def compute_dialogue_transcript_update(previous_tail: str, current_tail: str) -> tuple[str, bool]:
    """Return the newly appended transcript chunk and whether history should reset."""
    if not current_tail or current_tail == previous_tail:
        return "", False
    if not previous_tail:
        return current_tail, False
    if current_tail.startswith(previous_tail):
        return current_tail[len(previous_tail) :], False

    overlap = _suffix_prefix_overlap(previous_tail, current_tail)
    if overlap > 0:
        return current_tail[overlap:], False
    return current_tail, True


def strip_dialogue_transcript_tail(
    policy_infos: dict[str, Any] | None,
) -> dict[str, Any] | None:
    if not policy_infos:
        return None
    if "__dialogue_transcript_tail" not in policy_infos:
        return policy_infos
    sanitized = dict(policy_infos)
    sanitized.pop("__dialogue_transcript_tail", None)
    return sanitized or None


def _suffix_prefix_overlap(previous_tail: str, current_tail: str) -> int:
    max_overlap = min(len(previous_tail), len(current_tail))
    for overlap in range(max_overlap, 0, -1):
        if previous_tail[-overlap:] == current_tail[:overlap]:
            return overlap
    return 0
