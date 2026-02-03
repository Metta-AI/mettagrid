"""Test that generated protobuf files are up to date with .proto sources."""

import hashlib
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

GENERATED_PATTERNS = ["*_pb2.py", "*_pb2.pyi"]

_PKG_ROOT = Path(__file__).resolve().parent.parent
GEN_SCRIPT = _PKG_ROOT / "scripts" / "generate_protos.py"
PROTO_OUTPUT_DIR = _PKG_ROOT / "python" / "src"


def _hash_file(path: Path) -> str:
    with path.open("rb") as f:
        return hashlib.file_digest(f, "sha256").hexdigest()


def _collect_hashes(scan_dir: Path) -> dict[str, str]:
    hashes = {}
    if not scan_dir.exists():
        return hashes
    for pattern in GENERATED_PATTERNS:
        for path in scan_dir.rglob(pattern):
            rel_path = str(path.relative_to(scan_dir))
            hashes[rel_path] = _hash_file(path)
    return hashes


def test_proto_files_up_to_date():
    assert GEN_SCRIPT.exists(), f"Proto generation script not found: {GEN_SCRIPT}"

    with tempfile.TemporaryDirectory() as tmpdir:
        result = subprocess.run(
            [sys.executable, str(GEN_SCRIPT), "--output", tmpdir],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, f"Proto generation failed:\n{result.stderr}\n{result.stdout}"

        fresh_output_dir = Path(tmpdir) / "packages" / "mettagrid" / "python" / "src"
        fresh = _collect_hashes(fresh_output_dir)
        committed = _collect_hashes(PROTO_OUTPUT_DIR)

        if fresh == committed:
            return

        errors = []
        for path, fresh_hash in sorted(fresh.items()):
            committed_hash = committed.pop(path, None)
            if committed_hash is None:
                errors.append(f"  missing: {path}")
            elif committed_hash != fresh_hash:
                errors.append(f"  outdated: {path}")

        for path in sorted(committed.keys()):
            errors.append(f"  orphaned: {path}")

        pytest.fail(
            "Generated proto files need updating. Run: python packages/mettagrid/scripts/generate_protos.py\n"
            + "\n".join(errors)
        )
