"""Map component for miniscope renderer."""

from typing import Dict

from rich.text import Text

from mettagrid.renderer.miniscope.buffer import MapBuffer
from mettagrid.renderer.miniscope.components.base import MiniscopeComponent
from mettagrid.renderer.miniscope.miniscope_panel import PanelLayout
from mettagrid.renderer.miniscope.miniscope_state import MiniscopeState, RenderMode
from mettagrid.simulator.simulator import Simulation


class MapComponent(MiniscopeComponent):
    """Component for rendering the game map."""

    _AOE_STYLE_BY_KEY = {
        "aoe.cogs": "green dim",
        "aoe.clips": "red dim",
        "aoe.neutral": "yellow dim",
        "aoe.other": "magenta dim",
        "aoe": "white dim",
    }

    def __init__(
        self,
        sim: Simulation,
        state: MiniscopeState,
        panels: PanelLayout,
    ):
        """Initialize the map component.

        Args:
            sim: MettaGrid simulator reference
            state: Miniscope state reference
            panels: Panel layout containing all panels
        """
        super().__init__(sim=sim, state=state, panels=panels)
        self._set_panel(panels.map_view)

        # Create map buffer - will be initialized with data from state
        self._map_buffer = MapBuffer(
            symbol_map=state.symbol_map or {},
            initial_height=sim.map_height,
            initial_width=sim.map_width,
        )
        self._aoe_type_ranges = self._build_aoe_type_ranges()

    def _update_buffer_config(self) -> None:
        """Update buffer configuration from state."""
        self._map_buffer._symbol_map = self.state.symbol_map or {}

    def _build_aoe_type_ranges(self) -> dict[str, int]:
        """Build a map of object type -> max AOE radius for rendering."""
        ranges: dict[str, int] = {}
        objects = self._sim.config.game.objects
        for type_name, obj_cfg in objects.items():
            max_range = 0
            for aoe in obj_cfg.aoes.values():
                max_range = max(max_range, aoe.radius)
            if max_range > 0:
                ranges[type_name] = max_range
        return ranges

    def _collect_aoe_sources(self, grid_objects: Dict[int, dict]) -> list[tuple[int, int, int, str]]:
        """Collect AOE sources for overlay rendering."""
        if not self._aoe_type_ranges or not self._state.show_aoe:
            return []

        sources: list[tuple[int, int, int, str]] = []
        for obj in grid_objects.values():
            type_name = obj.get("type_name")
            if not type_name:
                continue
            radius = self._aoe_type_ranges.get(type_name)
            if radius is None:
                continue
            collective_name = obj.get("collective_name")
            if not isinstance(collective_name, str) or not collective_name:
                style_key = "aoe.neutral"
            elif collective_name == "cogs":
                style_key = "aoe.cogs"
            elif collective_name == "clips":
                style_key = "aoe.clips"
            else:
                style_key = "aoe.other"
            sources.append((obj["r"], obj["c"], radius, style_key))
        return sources

    def _build_rich_map(
        self,
        grid: list[list[str]],
        overlay_styles: dict[tuple[int, int], str],
    ) -> Text:
        """Build a Rich Text renderable for the map with colored overlays."""
        text = Text()
        for row_index, row in enumerate(grid):
            for col_index, cell in enumerate(row):
                style_key = overlay_styles.get((row_index, col_index))
                if style_key:
                    style = self._AOE_STYLE_BY_KEY.get(style_key, "white dim")
                    text.append(cell, style=style)
                else:
                    text.append(cell)
            if row_index < len(grid) - 1:
                text.append("\n")
        return text

    def handle_input(self, ch: str) -> bool:
        """Handle map-specific inputs (cursor movement in SELECT mode).

        Args:
            ch: The character input from the user

        Returns:
            True if the input was handled
        """
        # Only handle cursor movement when in SELECT mode
        # Camera panning is now handled by SimControlComponent
        if self._state.mode != RenderMode.SELECT:
            return False

        # Handle cursor movement with shift-key acceleration
        if ch == "i":
            self._state.move_cursor(-1, 0)
            return True
        elif ch == "I":
            self._state.move_cursor(-10, 0)
            return True
        elif ch == "k":
            self._state.move_cursor(1, 0)
            return True
        elif ch == "K":
            self._state.move_cursor(10, 0)
            return True
        elif ch == "j":
            self._state.move_cursor(0, -1)
            return True
        elif ch == "J":
            self._state.move_cursor(0, -10)
            return True
        elif ch == "l":
            self._state.move_cursor(0, 1)
            return True
        elif ch == "L":
            self._state.move_cursor(0, 10)
            return True

        return False

    def update(self) -> None:
        """Update the map display."""
        panel = self._panel
        assert panel is not None
        # Update buffer configuration from state
        self._update_buffer_config()

        # Get grid objects from environment
        grid_objects = self._sim.grid_objects()

        # Update AOE overlays
        self._map_buffer.set_aoe_sources(self._collect_aoe_sources(grid_objects))

        # Get viewport size from panel
        panel_width, panel_height = panel.size()
        # Each map cell takes 2 chars in width
        viewport_width = panel_width // 2 if panel_width else self.state.viewport_width
        viewport_height = panel_height if panel_height else self.state.viewport_height

        # Update viewport with computed size
        self._map_buffer.set_viewport(
            self.state.camera_row,
            self.state.camera_col,
            viewport_height,
            viewport_width,
        )

        # Set cursor if in select mode
        if self.state.mode == RenderMode.SELECT:
            self._map_buffer.set_cursor(self.state.cursor_row, self.state.cursor_col)
        else:
            self._map_buffer.set_cursor(None, None)

        # Highlight selected agent if in vibe picker mode
        if self.state.mode == RenderMode.VIBE_PICKER:
            self._map_buffer.set_highlighted_agent(self.state.selected_agent)
        else:
            self._map_buffer.set_highlighted_agent(None)

        # Render with viewport and set panel content
        buffer = self._map_buffer.render(grid_objects, use_viewport=True)
        overlay_styles = self._map_buffer.get_aoe_overlay_styles()
        grid = self._map_buffer.get_last_grid()
        if overlay_styles and grid is not None:
            panel.set_content(self._build_rich_map(grid, overlay_styles))
        else:
            panel.set_content(buffer.split("\n"))
