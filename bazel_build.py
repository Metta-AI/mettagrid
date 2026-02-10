# Custom build backend for building mettagrid with Bazel
# This backend compiles the C++ extension using Bazel during package installation
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

from setuptools.build_meta import (
    build_editable as _build_editable,
)
from setuptools.build_meta import (
    build_sdist as _build_sdist,
)
from setuptools.build_meta import (
    build_wheel as _build_wheel,
)
from setuptools.build_meta import (
    get_requires_for_build_editable,
    get_requires_for_build_sdist,
    get_requires_for_build_wheel,
    prepare_metadata_for_build_editable,
    prepare_metadata_for_build_wheel,
)
from setuptools.dist import Distribution

PROJECT_ROOT = Path(__file__).resolve().parent
PYTHON_PACKAGE_DIR = PROJECT_ROOT / "python" / "src" / "mettagrid"
METTASCOPE_DIR = PROJECT_ROOT / "nim" / "mettascope"
VIBESCOPE_DIR = PROJECT_ROOT / "nim" / "vibescope"
METTASCOPE_PACKAGE_DIR = PYTHON_PACKAGE_DIR / "nim" / "mettascope"
VIBESCOPE_PACKAGE_DIR = PYTHON_PACKAGE_DIR / "nim" / "vibescope"
NIM_PACKAGES = {
    "mettascope": (METTASCOPE_DIR, METTASCOPE_PACKAGE_DIR),
    "vibescope": (VIBESCOPE_DIR, VIBESCOPE_PACKAGE_DIR),
}


# Nimby uses a global lock directory at ~/.nimby/nimbylock (created atomically via mkdir).
# The lock path is hardcoded in nimby -- there's no CLI flag or env var to change it.
# When nimby crashes (e.g. "Bad file descriptor" during vibescope's nimby sync), the lock
# is left behind and all subsequent nimby invocations fail with "Nimby is already running".
_NIMBY_LOCK = Path.home() / ".nimby" / "nimbylock"


def _cleanup_nimby_lock() -> None:
    if not _NIMBY_LOCK.exists():
        return
    print(f"Removing nimby lock left behind by crashed process: {_NIMBY_LOCK}")
    # Lock is a directory (mkdir-based), not a file
    shutil.rmtree(_NIMBY_LOCK, ignore_errors=True)


def cmd(args: list[str], *, cwd: Path, max_attempts: int = 1, env: dict | None = None) -> None:
    for attempt in range(1, max_attempts + 1):
        if args[0] == "nimby":
            _cleanup_nimby_lock()
        print(f"Running: {args}")
        result = subprocess.run(args, cwd=cwd, capture_output=True, text=True, env=env)
        print(result.stderr, file=sys.stderr)
        print(result.stdout, file=sys.stderr)

        if result.returncode == 0:
            return

        if attempt < max_attempts:
            wait = 2**attempt
            print(f"Attempt {attempt}/{max_attempts} failed, retrying in {wait}s...")
            time.sleep(wait)

    raise RuntimeError(f"Build failed: {args}")


def _run_bazel_build() -> None:
    """Run Bazel build to compile the C++ extension."""
    # Check if bazel is available
    if shutil.which("bazel") is None:
        raise RuntimeError(
            "Bazel is required to build mettagrid. "
            "Run 'uv run python -m metta.setup.components.system_packages.bootstrap' to install it."
        )

    # Determine build configuration from environment
    debug = os.environ.get("DEBUG", "").lower() in ("1", "true", "yes")

    # Check if running in CI environment (GitHub Actions sets CI=true)
    is_ci = os.environ.get("CI", "").lower() == "true" or os.environ.get("GITHUB_ACTIONS", "") == "true"

    if is_ci:
        # Use CI configuration to avoid root user issues with hermetic Python
        config = "ci"
    else:
        config = "dbg" if debug else "opt"

    # Align Bazel's registered Python toolchain with the active interpreter.
    py_version = f"{sys.version_info.major}.{sys.version_info.minor}"

    env = os.environ.copy()
    env.setdefault("METTAGRID_BAZEL_PYTHON_VERSION", py_version)

    # Provide a writable output root for environments with restricted /var/tmp access.
    output_user_root = env.get(
        "METTAGRID_BAZEL_OUTPUT_ROOT",
        str(PROJECT_ROOT / ".bazel_output"),
    )

    # Ensure the output root exists before invoking Bazel.
    Path(output_user_root).mkdir(parents=True, exist_ok=True)

    # Build the Python extension with auto-detected parallelism
    bazel_cmd = [
        "bazel",
        "--batch",
        f"--output_user_root={output_user_root}",
        "build",
        f"--config={config}",
        "--jobs=auto",
        "--verbose_failures",
        "//cpp:mettagrid_c",  # Build from new cpp location
    ]

    print(f"Running Bazel build: {' '.join(bazel_cmd)}")
    cmd(bazel_cmd, cwd=PROJECT_ROOT, max_attempts=3, env=env)

    # Copy the built extension to the package directory
    bazel_bin = PROJECT_ROOT / "bazel-bin"
    # Try both old and new locations for backward compatibility
    src_dirs = [
        PROJECT_ROOT / "python/src/mettagrid",  # New location
        PROJECT_ROOT / "src/mettagrid",  # Old location (compatibility)
    ]

    # Find the built extension file
    # Bazel outputs the extension at bazel-bin/cpp/mettagrid_c.so or bazel-bin/mettagrid_c.so
    extension_patterns = [
        "cpp/mettagrid_c.so",
        "cpp/mettagrid_c.pyd",
        "cpp/mettagrid_c.dylib",  # New location
        "mettagrid_c.so",
        "mettagrid_c.pyd",
        "mettagrid_c.dylib",  # Old location
    ]
    extension_file = None
    for pattern in extension_patterns:
        file_path = bazel_bin / pattern
        if file_path.exists():
            extension_file = file_path
            break
    if not extension_file:
        raise RuntimeError("mettagrid_c.{so,pyd,dylib} not found in bazel-bin/cpp/ or bazel-bin/")

    # Copy to all source directories that exist
    for src_dir in src_dirs:
        if src_dir.parent.exists():
            # Ensure destination directory exists
            src_dir.mkdir(parents=True, exist_ok=True)
            # Copy the extension to the source directory
            dest = src_dir / extension_file.name
            # Remove existing file if it exists (it might be read-only from previous build)
            if dest.exists():
                dest.unlink()
            shutil.copy2(extension_file, dest)
            print(f"Copied {extension_file} to {dest}")


def _nim_artifacts_up_to_date(nim_dir: Path, module_name: str) -> bool:
    """Check whether Nim outputs are still current."""

    force_rebuild = os.environ.get("METTAGRID_FORCE_NIM_BUILD", "").lower() in {"1", "true", "yes"}
    if force_rebuild:
        return False

    generated_dir = nim_dir / "bindings" / "generated"
    if not generated_dir.exists():
        return False

    output_names = (
        f"{module_name}.py",
        f"lib{module_name}.dylib",
        f"lib{module_name}.so",
        f"lib{module_name}.dll",
    )
    existing_outputs = {generated_dir / name for name in output_names if (generated_dir / name).exists()}
    lib_outputs = [generated_dir / name for name in output_names[1:] if (generated_dir / name).exists()]
    if not existing_outputs or not lib_outputs:
        return False

    source_files = [path for pattern in ("*.nim", "*.nims") for path in nim_dir.rglob(pattern) if path.is_file()]
    if not source_files:
        return False

    latest_source_mtime = max(path.stat().st_mtime for path in source_files)
    oldest_output_mtime = min(path.stat().st_mtime for path in existing_outputs)

    return oldest_output_mtime >= latest_source_mtime


def _copy_nim_python_bindings(nim_dir: Path, package_dir: Path) -> None:
    """Ensure Nim artifacts are vendored inside the Python package."""

    destination_root = package_dir
    destination_root.parent.mkdir(parents=True, exist_ok=True)

    if destination_root.exists():
        shutil.rmtree(destination_root)

    shutil.copytree(
        nim_dir,
        destination_root,
        dirs_exist_ok=True,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "nimbledeps", "dist", "build", "tools"),
    )


def _sanitize_nim_cfg(nim_dir: Path) -> None:
    cfg_path = nim_dir / "nim.cfg"
    if not cfg_path.exists():
        return
    # Nimby writes a Nim config file here. In rare cases we have observed non-config
    # stdout/stderr lines ending up in nim.cfg (e.g. from a crashed/partial run).
    # Keep valid config directives and only drop clearly-invalid noise.
    lines = cfg_path.read_text().splitlines()
    cleaned: list[str] = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            cleaned.append("")
            continue

        # Comments and standard Nim cfg switches.
        if stripped.startswith(("#", "-")):
            cleaned.append(stripped)
            continue

        # If nimby ever writes config directives in "key:value"/"key=value" form,
        # keep them as well (e.g. "path:\"...\"" or "path=\"...\"").
        if stripped.split(":", 1)[0].isidentifier() or stripped.split("=", 1)[0].isidentifier():
            cleaned.append(stripped)
            continue

        # Drop obvious non-config output.
        if stripped.startswith(("Using global packages directory.", "Updated package:", "Took:")):
            continue

        # Default: keep the line. Being permissive here is safer than deleting
        # something Nim actually needs to resolve imports.
        cleaned.append(stripped)

    if cleaned != lines:
        cfg_path.write_text("\n".join(cleaned) + "\n")


def _ensure_nim_cfg_has_nimby_paths(nim_dir: Path) -> None:
    """Make sure nim.cfg contains --path entries for packages in nimby.lock.

    This is a guardrail for cases where nimby generates an incomplete nim.cfg,
    which can lead to import errors like "cannot open file: genny".
    """

    lock_path = nim_dir / "nimby.lock"
    cfg_path = nim_dir / "nim.cfg"
    if not lock_path.exists() or not cfg_path.exists():
        return

    try:
        lock_lines = lock_path.read_text().splitlines()
        cfg_text = cfg_path.read_text()
    except OSError:
        return

    pkgs_dir = Path.home() / ".nimby" / "pkgs"
    if not pkgs_dir.exists():
        return

    # Match either /name/ or /name" or /name$ in an existing path line.
    def _has_pkg_path(pkg: str) -> bool:
        return re.search(rf"/{re.escape(pkg)}(?:/|\"|$)", cfg_text) is not None

    missing: list[str] = []
    for line in lock_lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        pkg = stripped.split()[0]
        if _has_pkg_path(pkg):
            continue

        # Prefer ~/.nimby/pkgs/<pkg>/src when present, otherwise ~/.nimby/pkgs/<pkg>.
        candidates: list[Path] = []
        direct = pkgs_dir / pkg
        if direct.exists():
            candidates.append(direct)
        candidates.extend(sorted(p for p in pkgs_dir.glob(f"{pkg}*") if p.is_dir()))

        chosen: Path | None = None
        for base in candidates:
            src = base / "src"
            if src.is_dir():
                chosen = src
                break
            if base.is_dir():
                chosen = base
                break

        if chosen is not None:
            missing.append(f'--path:"{chosen}"')

    if not missing:
        return

    print(f"nim.cfg missing {len(missing)} nimby paths; appending.")
    cfg_path.write_text(cfg_text.rstrip() + "\n" + "\n".join(missing) + "\n")


def _run_nim_build(name: str, nim_dir: Path, package_dir: Path, *, copy_bindings: bool = False) -> None:
    """Build Nim artifacts when cache misses."""

    if _nim_artifacts_up_to_date(nim_dir, name):
        print(f"Skipping Nim build for {name}; artifacts up to date.")
        if not copy_bindings:
            _copy_nim_python_bindings(nim_dir, package_dir)
        return

    for x in ["nim", "nimby"]:
        if shutil.which(x) is None:
            raise RuntimeError(f"{x} not found! Install from https://github.com/treeform/nimby.")

    print(f"Building {name} from {nim_dir}")

    cmd(["nimby", "sync", "-g", "nimby.lock"], cwd=nim_dir, max_attempts=3)
    _sanitize_nim_cfg(nim_dir)
    _ensure_nim_cfg_has_nimby_paths(nim_dir)
    cmd(["nim", "c", "--skipProjCfg:on", "bindings/bindings.nim"], cwd=nim_dir)

    print(f"Successfully built {name}")
    if not copy_bindings:
        _copy_nim_python_bindings(nim_dir, package_dir)


def build_wheel(wheel_directory, config_settings=None, metadata_directory=None):
    """Build a wheel, compiling the C++ extension with Bazel first, then Nim renderers."""
    _run_bazel_build()
    for name, (nim_dir, package_dir) in NIM_PACKAGES.items():
        _run_nim_build(name, nim_dir, package_dir)
    # Ensure wheel is tagged as non-pure (platform-specific) since we bundle a native extension
    # Setuptools/wheel derive purity from Distribution.has_ext_modules(). Monkeypatch to force True.
    original_has_ext_modules = Distribution.has_ext_modules
    try:
        Distribution.has_ext_modules = lambda self: True  # type: ignore[assignment]
        return _build_wheel(wheel_directory, config_settings, metadata_directory)
    finally:
        Distribution.has_ext_modules = original_has_ext_modules


def build_editable(wheel_directory, config_settings=None, metadata_directory=None):
    """Build an editable install, compiling the C++ extension with Bazel first, then Nim renderers."""
    _run_bazel_build()
    for name, (nim_dir, package_dir) in NIM_PACKAGES.items():
        _run_nim_build(name, nim_dir, package_dir, copy_bindings=True)  # Editable installs use source directly
    return _build_editable(wheel_directory, config_settings, metadata_directory)


def build_sdist(sdist_directory, config_settings=None):
    """Build a source distribution without compiling the extension."""
    return _build_sdist(sdist_directory, config_settings)


__all__ = [
    "build_wheel",
    "build_editable",
    "build_sdist",
    "get_requires_for_build_wheel",
    "get_requires_for_build_editable",
    "get_requires_for_build_sdist",
    "prepare_metadata_for_build_wheel",
    "prepare_metadata_for_build_editable",
]
