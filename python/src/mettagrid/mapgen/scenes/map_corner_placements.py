from __future__ import annotations

from mettagrid.mapgen.scene import Scene, SceneConfig


class MapCornerPlacementsConfig(SceneConfig):
    """Place objects at map corners. Corner indices: 0=TL, 1=TR, 2=BL, 3=BR."""

    placements: list[tuple[str, int]] = []
    offset: int = 2


class MapCornerPlacements(Scene[MapCornerPlacementsConfig]):
    def render(self) -> None:
        cfg = self.config
        h, w = self.height, self.width
        offset = max(0, int(cfg.offset))
        corners = [
            (offset, offset),
            (offset, w - 1 - offset),
            (h - 1 - offset, offset),
            (h - 1 - offset, w - 1 - offset),
        ]
        for obj_name, corner_idx in cfg.placements:
            if 0 <= corner_idx < 4 and obj_name:
                r, c = corners[corner_idx]
                if 0 <= r < h and 0 <= c < w:
                    self.grid[r, c] = obj_name
