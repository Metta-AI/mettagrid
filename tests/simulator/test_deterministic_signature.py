from __future__ import annotations

import subprocess
import sys
from pathlib import Path

SCRIPT_PATH = Path(__file__).resolve().parents[2] / "scripts" / "deterministic_episode_signature.py"


def _run_signature() -> str:
    return subprocess.check_output([sys.executable, str(SCRIPT_PATH)], text=True).strip()


def test_deterministic_episode_signature_is_stable_across_fresh_processes() -> None:
    hashes = {_run_signature() for _ in range(12)}

    assert len(hashes) == 1, f"Expected one deterministic signature, got {sorted(hashes)}"
