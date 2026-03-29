from __future__ import annotations

from pydantic import BaseModel, Field


class MacroDirective(BaseModel):
    role: str | None = None
    target_entity_id: str | None = None
    target_region: str | None = None
    resource_bias: str | None = None
    objective: str | None = None
    note: str = ""
    metadata: dict[str, str | int | float | bool] = Field(default_factory=dict)

    def is_empty(self) -> bool:
        return not any(
            (
                self.role,
                self.target_entity_id,
                self.target_region,
                self.resource_bias,
                self.objective,
                self.note,
                self.metadata,
            )
        )
