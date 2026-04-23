from __future__ import annotations

import numpy as np

from mettagrid.mapgen.scene import Scene, SceneConfig


class PerimeterPlacementsConfig(SceneConfig):
    """Place objects randomly on the map perimeter at a fixed offset from edges."""

    placements: list[tuple[str, int]] = []
    offset: int = 2


class PerimeterPlacements(Scene[PerimeterPlacementsConfig]):
    """Place configured objects on unique random cells along an inset perimeter ring."""

    def render(self) -> None:
        cfg = self.config
        h, w = self.height, self.width
        offset = max(0, int(cfg.offset))

        perimeter_positions = (
            [(offset, c) for c in range(offset, w - offset)]
            + [(h - 1 - offset, c) for c in range(offset, w - offset)]
            + [(r, offset) for r in range(offset + 1, h - 1 - offset)]
            + [(r, w - 1 - offset) for r in range(offset + 1, h - 1 - offset)]
        )
        available_positions = list(dict.fromkeys(perimeter_positions))
        if not available_positions:
            return

        for obj_name, count in cfg.placements:
            spawn_count = min(max(0, int(count)), len(available_positions))
            if not obj_name or spawn_count <= 0:
                continue
            chosen = self.rng.choice(len(available_positions), size=spawn_count, replace=False)
            for idx in sorted((int(i) for i in np.atleast_1d(chosen)), reverse=True):
                r, c = available_positions.pop(idx)
                self.grid[r, c] = obj_name
