from __future__ import annotations

from dataclasses import dataclass, field

from mettagrid.config.mettagrid_config import TalkConfig
from mettagrid.simulator.interface import Location, VisibleTalk


def _within_observation_shape(row_offset: int, col_offset: int, *, obs_height: int, obs_width: int) -> bool:
    row_radius = obs_height >> 1
    col_radius = obs_width >> 1

    if row_radius == 0 and col_radius == 0:
        return row_offset == 0 and col_offset == 0
    if row_radius == 0:
        return row_offset == 0 and abs(col_offset) <= col_radius
    if col_radius == 0:
        return col_offset == 0 and abs(row_offset) <= row_radius

    row_sq = row_offset * row_offset
    col_sq = col_offset * col_offset
    if row_radius == col_radius:
        radius_sq = row_radius * row_radius
        dist_sq = row_sq + col_sq
        return dist_sq <= radius_sq or (
            row_radius >= 2
            and dist_sq == radius_sq + 1
            and (abs(row_offset) == row_radius or abs(col_offset) == col_radius)
        )

    return row_sq * (col_radius * col_radius) + col_sq * (row_radius * row_radius) <= (
        row_radius * row_radius * col_radius * col_radius
    )


@dataclass(frozen=True)
class ActiveTalk:
    text: str
    expires_after_step: int
    replace_after_step: int

    def remaining_steps(self, current_step: int) -> int:
        return max(0, self.expires_after_step - current_step)

    def can_replace(self, current_step: int) -> bool:
        return (current_step + 1) >= self.replace_after_step


@dataclass(frozen=True)
class TalkState:
    text: str
    remaining_steps: int


@dataclass
class TalkChannel:
    config: TalkConfig
    _active_by_agent: dict[int, ActiveTalk] = field(default_factory=dict)
    _pending_by_agent: dict[int, str] = field(default_factory=dict)

    def reset(self) -> None:
        self._active_by_agent.clear()
        self._pending_by_agent.clear()

    def queue(self, agent_id: int, text: str, *, current_step: int) -> None:
        if not self.config.enabled:
            raise ValueError("talk is not enabled for this game")
        if not text:
            raise ValueError("talk must be non-empty")
        if len(text) > self.config.max_length:
            raise ValueError(f"talk exceeds max_length {self.config.max_length}")
        active_talk = self._active_by_agent.get(agent_id)
        if active_talk is not None and not active_talk.can_replace(current_step):
            raise ValueError("talk cooldown has not expired")
        self._pending_by_agent[agent_id] = text

    def apply_pending(self, *, current_step: int) -> None:
        if not self._pending_by_agent:
            return
        display_steps = max(1, self.config.cooldown_steps)
        cooldown_steps = self.config.cooldown_steps
        for agent_id, text in self._pending_by_agent.items():
            self._active_by_agent[agent_id] = ActiveTalk(
                text=text,
                expires_after_step=current_step + display_steps,
                replace_after_step=current_step + cooldown_steps,
            )
        self._pending_by_agent.clear()

    def expire(self, *, current_step: int) -> None:
        expired_agent_ids = [
            agent_id
            for agent_id, active_talk in self._active_by_agent.items()
            if current_step >= active_talk.expires_after_step
        ]
        for agent_id in expired_agent_ids:
            del self._active_by_agent[agent_id]

    def render_states(self, *, current_step: int) -> dict[int, TalkState]:
        return {
            agent_id: TalkState(text=active_talk.text, remaining_steps=active_talk.remaining_steps(current_step))
            for agent_id, active_talk in self._active_by_agent.items()
        }

    def visible_talk(
        self,
        observer_agent_id: int,
        *,
        current_step: int,
        agent_locations: dict[int, Location],
        obs_height: int,
        obs_width: int,
    ) -> list[VisibleTalk]:
        if not self.config.enabled or not self._active_by_agent:
            return []

        observer_location = agent_locations.get(observer_agent_id)
        if observer_location is None:
            return []

        row_radius = obs_height >> 1
        col_radius = obs_width >> 1
        visible_talk: list[VisibleTalk] = []
        for agent_id, active_talk in sorted(self._active_by_agent.items()):
            talk_location = agent_locations.get(agent_id)
            if talk_location is None:
                continue
            row_offset = talk_location.row - observer_location.row
            col_offset = talk_location.col - observer_location.col
            if not _within_observation_shape(row_offset, col_offset, obs_height=obs_height, obs_width=obs_width):
                continue
            visible_talk.append(
                VisibleTalk(
                    agent_id=agent_id,
                    text=active_talk.text,
                    location=Location(row=row_offset + row_radius, col=col_offset + col_radius),
                    remaining_steps=active_talk.remaining_steps(current_step),
                )
            )
        return visible_talk
