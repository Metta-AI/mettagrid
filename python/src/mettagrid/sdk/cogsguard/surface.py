from __future__ import annotations

from dataclasses import dataclass, field

from mettagrid.policy.policy_env_interface import PolicyEnvInterface
from mettagrid.sdk.agent import (
    LogSink,
    MemoryView,
    MettagridActions,
    MettagridSDK,
    MettagridState,
    PlanView,
    SemanticEvent,
    StateHelperCatalog,
    TeamSummary,
)
from mettagrid.sdk.agent.runtime.observation import ObservationEnvelope
from mettagrid.sdk.cogsguard.events import CogsguardEventExtractor
from mettagrid.sdk.cogsguard.prompt_adapter import CogsguardPromptAdapter
from mettagrid.sdk.cogsguard.state import CogsguardStateAdapter
from mettagrid.simulator import AgentObservation


@dataclass(slots=True)
class CogsguardSemanticSurface:
    """Stateless adapter that composes Cogsguard state, event, and prompt surfaces."""

    state_adapter: CogsguardStateAdapter = field(default_factory=CogsguardStateAdapter)
    event_extractor: CogsguardEventExtractor = field(default_factory=CogsguardEventExtractor)
    prompt_adapter: CogsguardPromptAdapter = field(default_factory=CogsguardPromptAdapter)

    def build_state(
        self,
        raw_observation: AgentObservation,
        *,
        policy_env_info: PolicyEnvInterface,
        step: int | None = None,
    ) -> MettagridState:
        return self.state_adapter.build_state(
            ObservationEnvelope(raw_observation=raw_observation, policy_env_info=policy_env_info, step=step)
        )

    def build_state_with_events(
        self,
        raw_observation: AgentObservation,
        *,
        policy_env_info: PolicyEnvInterface,
        step: int | None = None,
        previous_state: MettagridState | None = None,
    ) -> MettagridState:
        state = self.build_state(raw_observation, policy_env_info=policy_env_info, step=step)
        state.recent_events = self.extract_events(previous_state, state)
        return state

    def extract_events(
        self,
        previous_state: MettagridState | None,
        current_state: MettagridState,
    ) -> list[SemanticEvent]:
        return self.event_extractor.extract_events(previous_state, current_state)

    def render_state(self, state: MettagridState) -> str:
        return self.prompt_adapter.render_state(state)

    def render_skill_library(self) -> str:
        return self.prompt_adapter.render_skill_library()

    def with_shared_objectives(
        self,
        state: MettagridState,
        *,
        shared_objectives: list[str] | None = None,
    ) -> MettagridState:
        if not shared_objectives:
            return state
        team_summary = state.team_summary or TeamSummary(team_id=str(state.self_state.attributes.get("team", "")))
        return state.model_copy(
            update={
                "team_summary": team_summary.model_copy(
                    update={
                        "shared_objectives": list(dict.fromkeys([*team_summary.shared_objectives, *shared_objectives])),
                    }
                ),
            }
        )

    def build_sdk(
        self,
        state: MettagridState,
        *,
        actions: MettagridActions,
        memory: MemoryView,
        log: LogSink,
        plan: PlanView | None = None,
        shared_objectives: list[str] | None = None,
    ) -> MettagridSDK:
        augmented_state = self.with_shared_objectives(state, shared_objectives=shared_objectives)
        return MettagridSDK(
            state=augmented_state,
            actions=actions,
            helpers=StateHelperCatalog(augmented_state),
            memory=memory,
            log=log,
            plan=plan,
        )
