#!/usr/bin/env python3
"""Generate Python protobuf bindings from .proto files.

Proto source files live in proto/ at the repo root. Each package mapping
specifies which proto subdirectory to compile and where to write the
generated Python files. For example:

    proto/mettagrid/protobuf/sim/policy_v1/policy.proto
      -> packages/mettagrid/python/src/mettagrid/protobuf/sim/policy_v1/policy_pb2.py
"""

import subprocess
import sys
from pathlib import Path
from typing import Annotated, Optional

import typer


def _find_repo_root() -> Path:
    current = Path.cwd().resolve()
    for parent in [current, *current.parents]:
        if (parent / ".repo-root").exists():
            return parent
    raise SystemExit("Repository root not found")


REPO_ROOT = _find_repo_root()
PROTO_ROOT = REPO_ROOT / "proto"


def get_proto_mappings(root_dir: Path = REPO_ROOT) -> list[dict]:
    return [
        {
            "subdir": Path("mettagrid"),
            "output_root": root_dir / "packages/mettagrid/python/src",
        },
    ]


def find_proto_files(subdir: Path) -> list[Path]:
    return sorted((PROTO_ROOT / subdir).rglob("*.proto"))


def generate_protos(subdir: Path, output_root: Path) -> bool:
    proto_files = find_proto_files(subdir)
    if not proto_files:
        print(f"No .proto files found in {PROTO_ROOT / subdir}")
        return True

    output_root.mkdir(parents=True, exist_ok=True)

    cmd = [
        sys.executable,
        "-m",
        "grpc_tools.protoc",
        f"--proto_path={PROTO_ROOT}",
        f"--python_out={output_root}",
        f"--pyi_out={output_root}",
        *[str(f.relative_to(PROTO_ROOT)) for f in proto_files],
    ]

    print(f"Generating protos: {PROTO_ROOT / subdir} -> {output_root}")
    for f in proto_files:
        print(f"  {f.relative_to(PROTO_ROOT)}")

    result = subprocess.run(cmd, cwd=PROTO_ROOT, capture_output=True, text=True)

    if result.returncode != 0:
        print(f"protoc failed:\n{result.stderr}", file=sys.stderr)
        return False

    if result.stderr:
        print(result.stderr)

    return True


def ensure_init_files(subdir: Path, output_root: Path) -> None:
    subdir_root = output_root / subdir
    for proto_file in find_proto_files(subdir):
        rel_path = proto_file.relative_to(PROTO_ROOT)
        for parent in (output_root / rel_path).parents:
            if parent == subdir_root or parent == output_root:
                break
            init_file = parent / "__init__.py"
            if not init_file.exists():
                init_file.touch()
                print(f"  Created {init_file.relative_to(output_root)}")


def main(
    output: Annotated[Optional[Path], typer.Option(help="Output directory (default: repo root)")] = None,
) -> None:
    root_dir = output or REPO_ROOT
    success = True

    for mapping in get_proto_mappings(root_dir):
        subdir = mapping["subdir"]
        output_root = mapping["output_root"]

        if not (PROTO_ROOT / subdir).exists():
            print(f"Proto path does not exist: {PROTO_ROOT / subdir}")
            continue

        if not generate_protos(subdir, output_root):
            success = False
            continue

        ensure_init_files(subdir, output_root)

    if not success:
        raise typer.Exit(1)


if __name__ == "__main__":
    typer.run(main)
