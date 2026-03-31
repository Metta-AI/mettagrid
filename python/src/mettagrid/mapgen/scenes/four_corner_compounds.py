"""Scene that places up to 4 Compound instances at the corners of the map."""

from __future__ import annotations

from pydantic import Field

from mettagrid.mapgen.area import AreaWhere
from mettagrid.mapgen.scene import ChildrenAction, Scene, SceneConfig
from mettagrid.mapgen.scenes.compound import CompoundConfig


class FourCornerCompoundsConfig(SceneConfig):
    """Place 1-4 compounds at the corners of the map (TL, TR, BL, BR order)."""

    compound: CompoundConfig = Field(default_factory=CompoundConfig)
    num_compounds: int = Field(default=4, ge=1, le=4)
    spawn_count: int = 8
    # Per-compound hub object names. Length must equal num_compounds if set.
    hub_objects: list[str] | None = None
    # Per-compound station lists. Length must equal num_compounds if set.
    stations_per_compound: list[list[str]] | None = None
    # Per-compound spawn symbols (e.g. agent.team_0, agent.team_1).
    spawn_symbols: list[str] | None = None


class FourCornerCompounds(Scene[FourCornerCompoundsConfig]):
    """Render up to 4 compounds, one per corner quadrant."""

    def render(self) -> None:
        cfg = self.config
        h, w = self.height, self.width
        half_w = w // 2
        half_h = h // 2

        quadrants = [
            (0, 0, half_w, half_h),
            (half_w, 0, w - half_w, half_h),
            (0, half_h, half_w, h - half_h),
            (half_w, half_h, w - half_w, h - half_h),
        ]
        for i in range(cfg.num_compounds):
            x, y, qw, qh = quadrants[i]
            self.make_area(x, y, qw, qh, tags=[f"corner_{i}"])

    def get_children(self) -> list[ChildrenAction]:
        cfg = self.config
        children: list[ChildrenAction] = []
        for i in range(cfg.num_compounds):
            updates: dict = {"spawn_count": cfg.spawn_count}
            if cfg.hub_objects and i < len(cfg.hub_objects):
                updates["hub_object"] = cfg.hub_objects[i]
            if cfg.stations_per_compound and i < len(cfg.stations_per_compound):
                updates["stations"] = cfg.stations_per_compound[i]
            if cfg.spawn_symbols and i < len(cfg.spawn_symbols):
                updates["spawn_symbol"] = cfg.spawn_symbols[i]
            compound_cfg = cfg.compound.model_copy(deep=True, update=updates)
            children.append(
                ChildrenAction(
                    scene=compound_cfg,
                    where=AreaWhere(tags=[f"corner_{i}"]),
                    limit=1,
                    order_by="first",
                )
            )
        return children
