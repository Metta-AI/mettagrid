from __future__ import annotations

from typing import Sequence

class VibescopeAction:
    action_name: str | bytes
    agent_id: int


class VibescopeResponse:
    should_close: bool
    actions: Sequence[VibescopeAction] | None


def init(data_dir: str, replay: str, autostart: bool = ...) -> VibescopeResponse: ...


def render(step: int, replay_step: str) -> VibescopeResponse: ...


class VibescopeError(Exception): ...
