from __future__ import annotations

from typing import Any


def compute_monologue_transcript_update(previous_tail: str, current_tail: str) -> tuple[str, bool]:
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


def strip_monologue_transcript_tail(
    policy_infos: dict[str, Any] | None,
) -> dict[str, Any] | None:
    if not policy_infos:
        return None
    if "__monologue_transcript_tail" not in policy_infos:
        return policy_infos
    sanitized = dict(policy_infos)
    sanitized.pop("__monologue_transcript_tail", None)
    return sanitized or None


def _suffix_prefix_overlap(previous_tail: str, current_tail: str) -> int:
    if not previous_tail or not current_tail:
        return 0

    pattern = current_tail
    prefix = [0] * len(pattern)
    for index in range(1, len(pattern)):
        match = prefix[index - 1]
        while match > 0 and pattern[index] != pattern[match]:
            match = prefix[match - 1]
        if pattern[index] == pattern[match]:
            match += 1
        prefix[index] = match

    match = 0
    for char in previous_tail[-len(pattern) :]:
        while match > 0 and (match == len(pattern) or char != pattern[match]):
            match = prefix[match - 1]
        if char == pattern[match]:
            match += 1
    return match
