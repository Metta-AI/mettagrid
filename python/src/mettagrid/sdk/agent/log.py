from __future__ import annotations

from typing import Any, Literal, Protocol, runtime_checkable

from pydantic import BaseModel, Field


class ReviewRequest(BaseModel):
    trigger_name: str
    prompt: str = ""
    target: Literal["memory", "policy"] = "policy"
    step: int | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class LogRecord(BaseModel):
    level: Literal["debug", "info", "warning", "error"]
    message: str
    step: int | None = None
    review: ReviewRequest | None = None
    data: dict[str, Any] = Field(default_factory=dict)


@runtime_checkable
class LogSink(Protocol):
    def write(self, record: LogRecord) -> None: ...
