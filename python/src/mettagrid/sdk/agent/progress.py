from __future__ import annotations

from pydantic import BaseModel, Field

ProgressMetricValue = str | int | float | bool


class ProgressSnapshot(BaseModel):
    objective: str = ""
    summary: str = ""
    milestones: list[str] = Field(default_factory=list)
    metrics: dict[str, ProgressMetricValue] = Field(default_factory=dict)

    def metric(self, name: str, default: ProgressMetricValue | None = None) -> ProgressMetricValue | None:
        return self.metrics.get(name, default)

    def render(self, *, max_metrics: int | None = 12) -> str:
        lines = [f"objective: {self.objective}", f"summary: {self.summary or 'none'}"]
        if self.milestones:
            lines.append("milestones:")
            lines.extend(f"- {item}" for item in self.milestones)
        metric_items = sorted(self.metrics.items())
        if max_metrics is not None:
            metric_items = metric_items[:max_metrics]
        if metric_items:
            lines.append("metrics:")
            lines.extend(f"- {name}: {value}" for name, value in metric_items)
        return "\n".join(lines)
