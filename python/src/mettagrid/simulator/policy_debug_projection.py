from __future__ import annotations

from typing import Any


def project_policy_debug_infos(
    debug_infos: dict[str, Any],
) -> dict[str, str | int]:
    projected: dict[str, str | int] = {}
    transcript_tail = _string_field(debug_infos, "transcript_tail")
    if transcript_tail:
        projected["__dialogue_transcript_tail"] = transcript_tail
    return projected


def _string_field(payload: dict[str, Any], key: str) -> str:
    if key not in payload:
        return ""
    value = payload[key]
    if not isinstance(value, str):
        return ""
    return value
