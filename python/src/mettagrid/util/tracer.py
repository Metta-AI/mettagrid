"""Simple tracer for timing policy-engine interactions.

Outputs Chrome Trace Format: https://docs.google.com/document/d/1CvAClvFfyA5R-PhYUmn5OOQtYMH4h6I0nSsKchNAySU

TODO (tracer work in progress):
- Clean up metadata handling: don't pass arbitrary kwargs from rollout through to JSON;
  explicitly define what fields we support
- Add type annotations to __init__ methods
- Add tests (write to real temp dir, inspect output)
- Clearer typing on calls from rollout to tracer (Span.set() kwargs)
- Multi-episode rollout: run_multi_episode_rollout doesn't wire through obs_dir yet
"""

import gc
import json
import time
from pathlib import Path
from types import TracebackType
from typing import IO, Self


class Span:
    """A timed span that records start/end times and metadata."""

    def __init__(self, tracer: "Tracer", name: str, **initial_metadata):
        self._tracer = tracer
        self._name = name
        self._metadata = initial_metadata
        self._start_ns: int = 0

    def set(self, **metadata) -> None:
        """Add metadata to this span."""
        self._metadata.update(metadata)

    def __enter__(self) -> Self:
        self._start_ns = time.perf_counter_ns()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        end_ns = time.perf_counter_ns()
        self._tracer._write_span(self._name, self._start_ns, end_ns - self._start_ns, self._metadata)


class NullSpan(Span):
    """No-op span for when tracing is disabled."""

    def __init__(self):
        pass

    def set(self, **metadata) -> None:
        pass

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        pass


_NULL_SPAN = NullSpan()


class Tracer:
    """Lightweight tracer that streams spans to Chrome Trace Format JSON."""

    def __init__(self, output_path: Path | str):
        self._file: IO[str] = open(output_path, "w")
        self._file.write("[")
        self._first = True
        self._flushed = False
        self._gc_start_ns: int = 0
        gc.callbacks.append(self._gc_callback)

    def _gc_callback(self, phase: str, info: dict) -> None:
        """Record GC events in the trace."""
        if phase == "start":
            self._gc_start_ns = time.perf_counter_ns()
        elif self._gc_start_ns != 0:  # "stop", but only if we saw the start
            self._write_span(
                "gc",
                self._gc_start_ns,
                time.perf_counter_ns() - self._gc_start_ns,
                {"generation": info["generation"], "collected": info["collected"]},
            )
            self._gc_start_ns = 0

    def span(self, name: str, **metadata) -> Span:
        """Create a span context manager for timing a block of code."""
        return Span(self, name, **metadata)

    def _write_span(self, name: str, ts_ns: int, dur_ns: int, metadata: dict) -> None:
        """Write a completed span in Chrome Trace Format."""

        pid, tid = 0, 0
        if name == "env_step":
            pass
            # pid, tid = 1, 1
        elif name == "agent_step":
            pass
            # pid, tid = 2, 1+metadata.get("agent", 0)

        event = {
            "name": name,
            "ph": "X",  # Complete event
            "ts": ts_ns // 1000,  # Chrome Trace uses microseconds
            "dur": dur_ns // 1000,
            "pid": pid,
            "tid": tid,
            "args": metadata,
        }
        if not self._first:
            self._file.write(",")
        self._first = False
        json.dump(event, self._file)
        self._file.write("\n")

    def flush(self) -> None:
        """Close the JSON array and ensure everything is written to disk.

        Safe to call multiple times; only the first call has effect.
        """
        if self._flushed:
            return
        self._flushed = True
        gc.callbacks.remove(self._gc_callback)
        self._file.write("]\n")
        self._file.close()

    def __del__(self) -> None:
        """Ensure cleanup if flush() was never called."""
        self.flush()


class NullTracer(Tracer):
    """No-op tracer for when tracing is disabled."""

    def __init__(self):
        pass

    def span(self, name: str, **metadata) -> Span:
        return _NULL_SPAN

    def _write_span(self, name: str, ts_ns: int, dur_ns: int, metadata: dict) -> None:
        pass

    def flush(self) -> None:
        pass
