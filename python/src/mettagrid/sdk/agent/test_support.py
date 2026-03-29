from __future__ import annotations

from dataclasses import dataclass, field

from mettagrid.sdk.agent import LogRecord, MemoryQuery, MemoryRecord, RetrievedMemoryRecord


class MemoryStub(dict[str, object]):
    def __init__(
        self,
        *,
        records: list[MemoryRecord] | None = None,
        scratchpad: str = "Hold the east lane.",
    ) -> None:
        super().__init__()
        self._records = (
            [MemoryRecord(record_id="evt-1", kind="event", summary="Picked up a heart.")]
            if records is None
            else records
        )
        self._scratchpad = scratchpad

    def recent_records(self, limit: int = 10) -> list[MemoryRecord]:
        return self._records[:limit]

    def retrieve(self, query: MemoryQuery, limit: int = 10) -> list[RetrievedMemoryRecord]:
        del query
        if not self._records:
            return []
        return [
            RetrievedMemoryRecord(
                record=self._records[0],
                score=0.9,
                relevance_score=0.9,
                recency_score=0.0,
                importance_score=0.0,
            )
        ][:limit]

    def render_prompt_context(self, query: MemoryQuery, limit: int = 6) -> str:
        del query, limit
        if not self._records:
            return ""
        record = self._records[0]
        return f"=== RETRIEVED SEMANTIC MEMORY ===\n  - [{record.kind}] step={record.step} {record.summary}"

    def read_scratchpad(self) -> str:
        return self._scratchpad

    def replace_scratchpad(self, text: str) -> None:
        self._scratchpad = text

    def append_scratchpad(self, text: str) -> None:
        self._scratchpad += text


@dataclass(slots=True)
class LogStub:
    records: list[LogRecord] = field(default_factory=list)

    def write(self, record: LogRecord) -> None:
        self.records.append(record)


@dataclass(slots=True)
class PlanStub:
    text: str = "# Plan\n- Hold the east lane"

    def read_plan(self, max_chars: int = 4000) -> str:
        return self.text[-max_chars:]

    def replace_plan(self, text: str) -> None:
        self.text = text

    def append_plan(self, text: str) -> None:
        self.text += text
