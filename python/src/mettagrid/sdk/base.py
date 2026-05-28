from __future__ import annotations

from typing import Protocol, runtime_checkable

from mettagrid.sdk.agent import MettagridState, SemanticEvent
from mettagrid.sdk.agent.runtime.observation import ObservationEnvelope


@runtime_checkable
class SemanticStateAdapter(Protocol):
    def build_state(self, observation: ObservationEnvelope) -> MettagridState: ...


@runtime_checkable
class SemanticEventExtractor(Protocol):
    def extract_events(
        self,
        previous_state: MettagridState | None,
        current_state: MettagridState,
    ) -> list[SemanticEvent]: ...
