"""Serializable policy specifications."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from pydantic import BaseModel, Field

from mettagrid.policy.policy_env_interface import PolicyEnvInterface


class PolicySpec(BaseModel):
    """Specification for a policy used during evaluation."""

    class_path: str = Field(description="Local path to policy class, or shorthand")

    data_path: Optional[str] = Field(default=None, description="Local file path to policy weights, if applicable")

    init_kwargs: dict[str, Any] = Field(default_factory=dict)

    policy_env_interface: Optional[PolicyEnvInterface] = Field(
        default=None,
        description="Policy-facing environment contract bundled with submitted policy archives",
    )

    @property
    def name(self) -> str:
        parts = [
            self.class_path.split(".")[-1],
        ]
        if self.data_path:
            parts.append(Path(self.data_path).name)
        return "-".join(parts)
