from __future__ import annotations

from typing import Protocol, runtime_checkable

from pydantic import BaseModel, Field


class ActionDescriptor(BaseModel):
    name: str
    description: str
    preconditions: list[str] = Field(default_factory=list)
    terminal_reasons: list[str] = Field(default_factory=list)


class ActionOutcome(BaseModel):
    action: str
    success: bool
    reason: str
    step_started: int
    step_finished: int
    evidence: list[str] = Field(default_factory=list)
    metadata: dict[str, str | int | float | bool] = Field(default_factory=dict)


class ActionCatalog:
    def __init__(self, actions: list[ActionDescriptor]) -> None:
        self._actions = actions

    def list_actions(self) -> list[ActionDescriptor]:
        return list(self._actions)


@runtime_checkable
class MettagridActions(Protocol):
    def list_actions(self) -> list[ActionDescriptor]: ...
