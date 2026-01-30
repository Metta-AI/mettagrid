"""MettaGrid Simulator - Core simulation interface and implementation.

This module provides the main simulation interface for MettaGrid environments.
"""

from mettagrid.simulator.interface import (
    AgentObservation,
    Location,
    ObservationToken,
    SimulatorEventHandler,
)
from mettagrid.simulator.replay_log_writer import ReplayLogWriter
from mettagrid.simulator.simulator import (
    BoundingBox,
    Simulation,
    SimulationAgent,
    Simulator,
)
from mettagrid.types import Action

__all__ = [
    # From interface
    "Action",
    "AgentObservation",
    "Location",
    "ObservationToken",
    "SimulatorEventHandler",
    # From replay_log_writer
    "ReplayLogWriter",
    # From simulator
    "BoundingBox",
    "Simulation",
    "SimulationAgent",
    "Simulator",
]
