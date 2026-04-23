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


def test_tracer_ignores_reentrant_gc_during_event_write(tmp_path: Path) -> None:
    trace_path = tmp_path / "trace.json"
    tracer = Tracer(trace_path)

    class _ReentrantWriter:
        def __init__(self, tracer: Tracer, delegate) -> None:
            self._tracer = tracer
            self._delegate = delegate
            self._fired = False

        def write(self, payload: str) -> int:
            if not self._fired:
                self._fired = True
                self._tracer._gc_start_ns = time.time_ns()
                self._tracer._gc_callback("stop", {"generation": 0, "collected": 0})
            return self._delegate.write(payload)

        def close(self) -> None:
            self._delegate.close()

    tracer._file = _ReentrantWriter(tracer, tracer._file)
    tracer.record_span("late", time.time_ns(), 1_000, marker="kept")
    tracer.flush()

    events = _load_trace(trace_path)
    assert [event["name"] for event in events] == ["process_name", "process_sort_index", "late"]
