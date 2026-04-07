from __future__ import annotations

import sys
import types
from pathlib import Path

from mettagrid.policy.submission import SubmissionPolicySpec, write_submission_policy_spec


def _write_fake_submission_bundle(submission_dir: Path) -> None:
    write_submission_policy_spec(
        submission_dir / "policy_spec.json",
        SubmissionPolicySpec(class_path="mettagrid.util.module.load_symbol"),
    )

    bundle_pkg = submission_dir / "mettagrid" / "util"
    bundle_pkg.mkdir(parents=True)
    for package_dir in [bundle_pkg.parents[0], bundle_pkg]:
        (package_dir / "__init__.py").write_text("")
    (bundle_pkg / "module.py").write_text("raise RuntimeError('bundle module should not load during audits')\n")


def test_prefer_installed_package_code_uses_current_repo_modules(tmp_path: Path, monkeypatch) -> None:
    from mettagrid.policy.prepare_policy_spec import (  # noqa: PLC0415
        DEFAULT_POLICY_CACHE_DIR,
        load_policy_spec_from_path,
        prefer_installed_package_code,
    )
    from mettagrid.util.module import load_symbol as installed_load_symbol  # noqa: PLC0415

    submission_dir = tmp_path / "submission"
    submission_dir.mkdir()
    _write_fake_submission_bundle(submission_dir)

    stale_root = DEFAULT_POLICY_CACHE_DIR / "stale-bundle"
    stale_util = types.ModuleType("mettagrid.util")
    stale_util.__path__ = [str(stale_root / "mettagrid" / "util")]
    stale_module = types.ModuleType("mettagrid.util.module")
    stale_module.__file__ = str(stale_root / "mettagrid" / "util" / "module.py")
    stale_module.load_symbol = lambda *args, **kwargs: "stale"
    monkeypatch.setitem(sys.modules, "mettagrid.util", stale_util)
    monkeypatch.setitem(sys.modules, "mettagrid.util.module", stale_module)

    with prefer_installed_package_code():
        spec = load_policy_spec_from_path(submission_dir)
        loaded_symbol = installed_load_symbol(spec.class_path)

    assert loaded_symbol.__module__ == "mettagrid.util.module"
    module_file = Path(sys.modules[loaded_symbol.__module__].__file__).resolve()
    assert not module_file.is_relative_to(stale_root)
    assert not module_file.is_relative_to(submission_dir)
