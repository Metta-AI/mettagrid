import io
from pathlib import Path

from mettagrid.runner import bitworld_runner


def test_find_bitworld_binary_uses_container_layout(monkeypatch):
    expected = Path("/opt/bitworld/among_them/among_them")
    monkeypatch.setattr(Path, "exists", lambda path: path == expected)

    assert bitworld_runner._find_bitworld_binary(bitworld_runner.BitWorldConfig()) == expected


class _FakeProc:
    def __init__(self, alive: bool):
        self._alive = alive
        self.stderr = io.BytesIO(b"address already in use")

    def poll(self) -> int | None:
        return None if self._alive else 1


def test_start_server_on_free_port_retries_after_failed_bind(monkeypatch):
    ports = iter([1001, 1002])
    started_ports: list[int] = []

    monkeypatch.setattr(bitworld_runner, "_pick_free_port", lambda: next(ports))
    monkeypatch.setattr(bitworld_runner.time, "sleep", lambda _seconds: None)

    def fake_start_server(_binary_path: Path, config: bitworld_runner.BitWorldConfig) -> _FakeProc:
        started_ports.append(config.port)
        return _FakeProc(alive=len(started_ports) == 2)

    monkeypatch.setattr(bitworld_runner, "_start_server", fake_start_server)

    config = bitworld_runner.BitWorldConfig()
    server_proc = bitworld_runner._start_server_on_free_port(Path("/tmp/bitworld"), config)

    assert server_proc.poll() is None
    assert started_ports == [1001, 1002]
    assert config.port == 1002
