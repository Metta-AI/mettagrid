from __future__ import annotations

from pathlib import Path


def test_mettascope_vibe_assets_are_only_pngs() -> None:
    mettagrid_root = Path(__file__).resolve().parents[2]
    vibe_dir = mettagrid_root / "nim" / "mettascope" / "data" / "vibe"

    assert [path.name for path in vibe_dir.iterdir() if path.is_file() and path.suffix != ".png"] == []
