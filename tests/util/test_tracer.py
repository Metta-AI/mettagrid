from __future__ import annotations

import json
import time
from pathlib import Path

from mettagrid.util.tracer import Tracer


def _load_trace(path: Path) -> list[dict]:
    return json.loads(path.read_text())


def test_tracer_ignores_recorded_spans_after_flush(tmp_path: Path) -> None:
    trace_path = tmp_path / "trace.json"
    tracer = Tracer(trace_path)

    tracer.flush()
    tracer.record_span("late", time.time_ns(), 1_000, marker="ignored")

    events = _load_trace(trace_path)
    assert [event["name"] for event in events] == ["process_name", "process_sort_index"]


def test_tracer_ignores_inflight_gc_stop_after_flush(tmp_path: Path) -> None:
    trace_path = tmp_path / "trace.json"
    tracer = Tracer(trace_path)

    tracer._gc_callback("start", {"generation": 0, "collected": 0})
    tracer.flush()
    tracer._gc_callback("stop", {"generation": 0, "collected": 0})

    events = _load_trace(trace_path)
    assert [event["name"] for event in events] == ["process_name", "process_sort_index"]
