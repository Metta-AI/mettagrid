from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, NamedTuple, Sequence

from mettagrid.config.id_map import ObservationFeatureSpec
from mettagrid.mettagrid_c import PackedCoordinate

if TYPE_CHECKING:
    from mettagrid.simulator.simulator import Simulation


class Location(NamedTuple):
    row: int
    col: int

    @property
    def x(self) -> int:
        return self.col

    @property
    def y(self) -> int:
        return self.row


@dataclass
class ObservationToken:
    feature: ObservationFeatureSpec
    value: int
    raw_token: tuple[int, int, int]

    @property
    def location(self) -> Location:
        # PackedCoordinate.unpack returns None for 0xFF (the empty token marker).
        # In practice this shouldn't happen: tokens with feature_id=0xFF are filtered
        # out during observation parsing (see SimulationAgent.observation), so we
        # should never have an ObservationToken with an empty location byte.
        unpacked = PackedCoordinate.unpack(self.raw_token[0])
        if unpacked is None:
            return Location(0, 0)
        return Location(*unpacked)

    def row(self) -> int:
        return self.location.row

    def col(self) -> int:
        return self.location.col


@dataclass
class AgentObservation:
    agent_id: int
    tokens: Sequence[ObservationToken]


class SimulatorEventHandler:
    """Handler for Simulator events."""

    def __init__(self):
        self._sim: Simulation

    def set_simulation(self, simulation: Simulation) -> None:
        self._sim = simulation

    def on_episode_start(self) -> None:
        pass

    def on_episode_end(self) -> None:
        pass

    def on_step(self) -> None:
        pass

    def on_close(self) -> None:
        pass
