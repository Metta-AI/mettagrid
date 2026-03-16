"""Base renderer classes for game rendering."""

from abc import abstractmethod
from typing import Literal

from typing_extensions import override

from mettagrid.simulator.interface import SimulatorEventHandler
from mettagrid.types import Action

RenderMode = Literal["gui", "vibescope", "unicode", "log", "none"]


class Renderer(SimulatorEventHandler):
    """Abstract base class for game renderers."""

    def __init__(self):
        super().__init__()
        self._deferred_user_actions: list[tuple[int, Action]] = []

    def defer_user_action(self, agent_id: int, action: Action) -> None:
        """Store a user action to be applied after the next policy step."""
        self._deferred_user_actions.append((agent_id, action))

    def apply_deferred_user_actions(self) -> None:
        """Apply all deferred user actions (overriding policy actions), then clear."""
        for agent_id, action in self._deferred_user_actions:
            self._sim.agent(agent_id).set_action(action)
        self._deferred_user_actions.clear()

    @override
    def on_episode_start(self) -> None:
        """Initialize the renderer for a new episode."""
        pass

    def render(self) -> None:
        """Render the current state. Override this for interactive renderers that need to handle input."""
        pass

    def render_pending(self) -> None:
        """Render one pending frame while rollout is waiting on a policy step."""
        self.render()

    def supports_pending_render(self) -> bool:
        """Whether rollout should keep repainting while a policy step is blocked."""
        return False

    @override
    def on_step(self) -> None:
        """Called after each simulator step. Subclasses can access simulator state."""
        pass

    @abstractmethod
    def on_episode_end(self) -> None:
        """Clean up renderer resources."""
        pass


class NoRenderer(Renderer):
    """Renderer for headless mode (no rendering)."""

    def on_episode_start(self) -> None:
        pass

    @override
    def render(self) -> None:
        pass

    def on_step(self) -> None:
        pass

    def on_episode_end(self) -> None:
        pass


def create_renderer(render_mode: RenderMode, autostart: bool = False) -> Renderer:
    """Create the appropriate renderer based on render_mode."""
    if render_mode == "unicode":
        # Text-based interactive rendering
        from mettagrid.renderer.miniscope.miniscope import MiniscopeRenderer  # noqa: PLC0415

        return MiniscopeRenderer()
    elif render_mode == "gui":
        # GUI-based interactive rendering
        from mettagrid.renderer.mettascope import MettascopeRenderer  # noqa: PLC0415

        return MettascopeRenderer(autostart=autostart)
    elif render_mode == "vibescope":
        # GUI-based interactive rendering (vibescope)
        from mettagrid.renderer.vibescope import VibescopeRenderer  # noqa: PLC0415

        return VibescopeRenderer(autostart=autostart)
    elif render_mode == "log":
        # Logger-based rendering for debugging
        from mettagrid.renderer.log_renderer import LogRenderer  # noqa: PLC0415

        return LogRenderer()
    elif render_mode == "none":
        # No rendering
        return NoRenderer()
    raise ValueError(f"Invalid render_mode: {render_mode}")
