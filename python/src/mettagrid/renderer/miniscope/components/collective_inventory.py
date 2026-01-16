"""Collective inventory panel component for miniscope renderer."""

from collections import defaultdict
from typing import Dict

from mettagrid.renderer.miniscope.components.base import MiniscopeComponent
from mettagrid.renderer.miniscope.miniscope_panel import PanelLayout
from mettagrid.renderer.miniscope.miniscope_state import MiniscopeState
from mettagrid.simulator.simulator import Simulation


class CollectiveInventoryComponent(MiniscopeComponent):
    """Component for displaying collective inventory."""

    def __init__(
        self,
        sim: Simulation,
        state: MiniscopeState,
        panels: PanelLayout,
    ):
        """Initialize the collective inventory component.

        Args:
            sim: MettaGrid simulator reference
            state: Miniscope state reference
            panels: Panel layout containing all panels
        """
        super().__init__(sim=sim, state=state, panels=panels)
        sidebar_panel = panels.get_sidebar_panel("collective_inventory")
        assert sidebar_panel is not None
        self._set_panel(sidebar_panel)

    def update(self) -> None:
        """Render the collective inventory panel."""
        panel = self._panel
        assert panel is not None
        if not self.state.is_sidebar_visible("collective_inventory"):
            panel.clear()
            return

        inventories = self._get_collective_inventories()
        grid_objects = self._sim.grid_objects()
        collective_names = list(self._sim.config.game.collectives.keys())
        lines = self._build_lines(inventories, grid_objects, collective_names)
        panel.set_content(lines)

    def _get_collective_inventories(self) -> Dict[str, Dict[str, int]]:
        """Fetch collective inventories from the simulator, if available."""
        c_sim = getattr(self._sim, "_c_sim", None)
        if c_sim is None or not hasattr(c_sim, "get_collective_inventories"):
            return {}

        inventories = c_sim.get_collective_inventories()
        if not isinstance(inventories, dict):
            return {}

        normalized: Dict[str, Dict[str, int]] = {}
        for name, inv in inventories.items():
            if isinstance(inv, dict):
                normalized[str(name)] = {str(k): int(v) for k, v in inv.items()}
            else:
                normalized[str(name)] = {}
        return normalized

    def _build_lines(
        self,
        inventories: Dict[str, Dict[str, int]],
        grid_objects: Dict[int, dict],
        collective_names: list[str],
    ) -> list[str]:
        """Build lines for the collective inventory panel."""
        width = self._width if self._width else 40
        width = max(24, width)

        lines: list[str] = []
        lines.append("Collective Inventory")
        lines.append("-" * min(width, 40))

        building_counts: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
        for obj in grid_objects.values():
            if "agent_id" in obj:
                continue
            collective_name = obj.get("collective_name")
            if not isinstance(collective_name, str) or not collective_name:
                continue
            type_name = obj.get("type_name")
            if not type_name:
                continue
            building_counts[collective_name][type_name] += 1

        if not inventories and not building_counts:
            lines.append("(none)")
            return self._pad_lines(lines, width)

        for name in collective_names:
            lines.append(f"{name}:")

            inv = inventories.get(name, {})
            if inv:
                lines.append("  Inventory:")
                for resource, amount in sorted(inv.items(), key=lambda item: (-item[1], item[0])):
                    lines.append(f"    {resource}: {amount}")
            else:
                lines.append("  Inventory: (empty)")

            buildings = building_counts.get(name, {})
            if buildings:
                lines.append("  Buildings:")
                for type_name, count in sorted(buildings.items(), key=lambda item: (-item[1], item[0])):
                    lines.append(f"    {type_name}: {count}")
            else:
                lines.append("  Buildings: (none)")

            lines.append("")

        extra_collectives = sorted(name for name in building_counts.keys() if name not in collective_names)
        for name in extra_collectives:
            lines.append(f"{name}:")
            lines.append("  Inventory: (empty)")
            buildings = building_counts.get(name, {})
            if buildings:
                lines.append("  Buildings:")
                for type_name, count in sorted(buildings.items(), key=lambda item: (-item[1], item[0])):
                    lines.append(f"    {type_name}: {count}")
            else:
                lines.append("  Buildings: (none)")
            lines.append("")

        return self._pad_lines(lines, width)
