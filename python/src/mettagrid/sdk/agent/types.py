from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from pydantic import BaseModel, Field

from mettagrid.sdk.agent.actions import MettagridActions
from mettagrid.sdk.agent.helpers import MettagridHelpers
from mettagrid.sdk.agent.log import LogSink
from mettagrid.sdk.agent.progress import ProgressSnapshot
from mettagrid.sdk.agent.state import GridPosition, MettagridState


class MemoryRecord(BaseModel):
    record_id: str
    kind: str
    summary: str = ""
    tags: list[str] = Field(default_factory=list)
    game: str | None = None
    step: int | None = None
    location: GridPosition | None = None
    region_id: str | None = None
    role_context: str | None = None
    importance: float = 0.0
    source: str = ""
    evidence_ids: list[str] = Field(default_factory=list)


class EventMemoryRecord(MemoryRecord):
    # These typed wrappers are for retrieval/reflection internals. Policies can
    # usually just treat memory as MemoryRecord plus plain `kind`/`tags`.
    kind: str = "event"
    event_type: str


class PlanMemoryRecord(MemoryRecord):
    kind: str = "plan"
    plan_type: str
    status: str = "active"


class BeliefMemoryRecord(MemoryRecord):
    kind: str = "belief"
    belief_type: str
    confidence: float = 0.0


class MemoryQuery(BaseModel):
    game: str | None = None
    step: int | None = None
    role_context: str | None = None
    target_tags: list[str] = Field(default_factory=list)
    active_plan: str | None = None
    text: str = ""

    @classmethod
    def from_state(
        cls,
        state: MettagridState,
        *,
        active_plan: str | None = None,
        extra_tags: list[str] | None = None,
    ) -> "MemoryQuery":
        target_tags = set()
        if state.self_state.role is not None:
            target_tags.add(state.self_state.role)
        target_tags.update(state.self_state.status)
        for entity in state.visible_entities:
            target_tags.add(entity.entity_type)
            target_tags.update(entity.labels)
        if extra_tags is not None:
            target_tags.update(extra_tags)
        return cls(
            game=state.game,
            step=state.step,
            role_context=state.self_state.role,
            target_tags=sorted(target_tags),
            active_plan=active_plan,
        )


class RetrievedMemoryRecord(BaseModel):
    record: MemoryRecord
    score: float
    relevance_score: float
    recency_score: float
    importance_score: float


@runtime_checkable
class PlanView(Protocol):
    def read_plan(self, max_chars: int = 4000) -> str: ...
    def replace_plan(self, text: str) -> None: ...
    def append_plan(self, text: str) -> None: ...


@runtime_checkable
class MemoryView(Protocol):
    def recent_records(self, limit: int = 10) -> list[MemoryRecord]: ...
    def retrieve(self, query: MemoryQuery, limit: int = 10) -> list[RetrievedMemoryRecord]: ...
    def render_prompt_context(self, query: MemoryQuery, limit: int = 6) -> str: ...
    def read_scratchpad(self) -> str: ...
    def replace_scratchpad(self, text: str) -> None: ...
    def append_scratchpad(self, text: str) -> None: ...
    def get(self, key: str, default: object = None) -> object: ...
    def __contains__(self, key: object) -> bool: ...
    def __getitem__(self, key: str) -> object: ...
    def __setitem__(self, key: str, value: object) -> None: ...


@dataclass(slots=True)
class MettagridSDK:
    state: MettagridState
    actions: MettagridActions
    helpers: MettagridHelpers
    memory: MemoryView
    log: LogSink
    plan: PlanView | None = None
    progress: ProgressSnapshot | None = None

    @property
    def scratchpad(self) -> str:
        return self.memory.read_scratchpad()

    def read_scratchpad(self) -> str:
        return self.memory.read_scratchpad()

    def replace_scratchpad(self, text: str) -> None:
        self.memory.replace_scratchpad(text)

    def append_scratchpad(self, text: str) -> None:
        self.memory.append_scratchpad(text)

    def read_plan(self, max_chars: int = 4000) -> str:
        return "" if self.plan is None else self.plan.read_plan(max_chars=max_chars)

    def replace_plan(self, text: str) -> None:
        if self.plan is not None:
            self.plan.replace_plan(text)

    def append_plan(self, text: str) -> None:
        if self.plan is not None:
            self.plan.append_plan(text)
