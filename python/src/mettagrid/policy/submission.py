"""Shared constants and utilities for policy submission archives."""

import tempfile
import tomllib
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field

POLICY_SPEC_FILENAME = "policy_spec.json"
POLICY_MANIFEST_FILENAME = "cogames.toml"


class SubmissionPolicySpec(BaseModel):
    """Policy specification as stored in submission archives.

    This is the serialized format written to POLICY_SPEC_FILENAME in submission zips.
    It extends the core PolicySpec fields with submission-specific options like setup_script.
    """

    class_path: str = Field(description="Fully qualified path to policy class")
    data_path: Optional[str] = Field(default=None, description="Relative path to policy data within archive")
    init_kwargs: dict = Field(default_factory=dict, description="Keyword arguments for policy initialization")
    setup_script: Optional[str] = Field(
        default=None,
        description="Relative path to a Python setup script to run once before loading the policy",
    )


def load_policy_manifest(path: Path) -> SubmissionPolicySpec:
    """Read a cogames.toml manifest and build a SubmissionPolicySpec.

    Expected layout:

        [policy]
        class_path = "pkg.module.Class"
        data_path = "relative/path"        # optional
        setup_script = "setup_policy.py"   # optional

        [policy.init_kwargs]               # optional
        key = "value"
    """
    data = tomllib.loads(path.read_text())
    policy = data.get("policy")
    if not isinstance(policy, dict):
        raise ValueError(f"{path} is missing a [policy] table")
    return SubmissionPolicySpec(
        class_path=policy["class_path"],
        data_path=policy.get("data_path"),
        init_kwargs=dict(policy.get("init_kwargs") or {}),
        setup_script=policy.get("setup_script"),
    )


def write_submission_policy_spec(path: Path, spec: SubmissionPolicySpec) -> None:
    with tempfile.NamedTemporaryFile(
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
        delete=False,
    ) as tmp:
        tmp_path = Path(tmp.name)
        tmp.write(spec.model_dump_json().encode("utf-8"))
    tmp_path.replace(path)
