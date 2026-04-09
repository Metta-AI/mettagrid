from typing import Literal, Sequence

import numpy as np
from pydantic import Field

from mettagrid.mapgen.scene import Scene, SceneConfig

DEFAULT_EXTRACTORS: tuple[str, str, str, str] = (
    "carbon_extractor",
    "oxygen_extractor",
    "germanium_extractor",
    "silicon_extractor",
)

# Adapted from the official Overcooked-AI `cramped_room.layout` floorplan and
# widened to support Metta's extended station surface.
# https://raw.githubusercontent.com/HumanCompatibleAI/overcooked_ai/master/src/overcooked_ai_py/data/layouts/cramped_room.layout
CRAMPED_ROOM_STATION_ANCHORS: tuple[tuple[int, int], ...] = (
    (3, 3),
    (5, 3),
    (11, 5),
    (7, 3),
    (9, 3),
    (11, 3),
    (9, 7),
    (11, 7),
    (7, 7),
)
CRAMPED_ROOM_SPAWNS: tuple[tuple[int, int], ...] = (
    (6, 5),
    (8, 5),
    (6, 6),
    (8, 6),
)

# Multiplayer service-pass variant used by Overcooked's default kitchen.
SERVICE_PASS_ROOM_STATION_ANCHORS: tuple[tuple[int, int], ...] = (
    (3, 2),
    (8, 2),
    (12, 10),
    (5, 5),
    (10, 5),
    (13, 2),
    (8, 10),
    (15, 8),
    (1, 4),
)
SERVICE_PASS_ROOM_SPAWNS: tuple[tuple[int, int], ...] = (
    (6, 6),
    (10, 6),
    (6, 8),
    (10, 8),
)


class CompoundConfig(SceneConfig):
    hub_object: str = "hub"
    corner_generator: str | None = None
    spawn_symbol: str = "agent.agent"
    # If set, place at least this many spawn pads (best-effort) in the hub
    spawn_count: int | None = None
    hub_width: int = 21
    hub_height: int = 21
    include_inner_wall: bool = True
    # Make an empty buffer around the hub on the full grid (in tiles)
    outer_clearance: int = 3
    # Order: top-left, top-right, bottom-left, bottom-right.
    # Notes:
    # - If corner_objects is provided (len==4), Compound will use that set directly.
    # - corner_bundle/cross_bundle can be "none" | "extractors" | "custom".
    # - When both objects and bundle are provided, objects win (per Compound logic).
    corner_objects: list[str] | None = None
    corner_bundle: Literal["extractors", "none", "custom"] = "extractors"
    cross_objects: list[str] | None = None
    cross_bundle: Literal["none", "extractors", "custom"] = "none"
    cross_distance: int = 4
    layout: Literal["default", "tight", "cramped_room", "service_pass_room"] = "default"
    randomize_spawn_positions: bool = False
    # Gear stations: list of station names to place (e.g., ["aligner_station", "scrambler_station"])
    # These are placed in a row below the chest, similar to how the chest is placed
    stations: list[str] = []
    # Optional explicit station offsets relative to hub center (dx, dy), one per station.
    # If set, these are used instead of row placement.
    station_offsets: list[tuple[int, int]] | None = Field(default=None, exclude_if=lambda value: value is None)


class Compound(Scene[CompoundConfig]):
    """
    Build a symmetric 11x11 base:
    - Center cell: hub with junction two cells above
    - Four corner generators with one empty cell of clearance on all sides
    - Symmetric L-shaped empty corridors at each corner to form 4 exits
    - Spawn pads around center with empty clearance
    """

    def render(self) -> None:
        full_grid = self.grid
        full_h, full_w = self.height, self.width
        cfg = self.config

        # Compute centered hub region
        hub_w = max(7, min(cfg.hub_width, full_w))
        hub_h = max(7, min(cfg.hub_height, full_h))
        x0 = (full_w - hub_w) // 2
        y0 = (full_h - hub_h) // 2
        x1 = x0 + hub_w
        y1 = y0 + hub_h

        # Ensure an empty buffer around the hub region on the full grid
        clearance = max(0, int(cfg.outer_clearance))
        if clearance > 0:
            bx0 = max(0, x0 - clearance)
            by0 = max(0, y0 - clearance)
            bx1 = min(full_w, x1 + clearance)
            by1 = min(full_h, y1 + clearance)
            full_grid[by0:by1, bx0:bx1] = "empty"

        grid = full_grid[y0:y1, x0:x1]
        h, w = hub_h, hub_w
        cx, cy = w // 2, h // 2

        # Clear hub region
        grid[:] = "empty"

        # Optional inner wall around hub region
        if cfg.include_inner_wall and h >= 3 and w >= 3:
            grid[0, :] = "wall"
            grid[-1, :] = "wall"
            grid[:, 0] = "wall"
            grid[:, -1] = "wall"

            gate_half = 2
            # top/bottom gates
            grid[0, cx - gate_half : cx + gate_half + 1] = "empty"
            grid[1, cx - gate_half : cx + gate_half + 1] = "empty"
            grid[h - 1, cx - gate_half : cx + gate_half + 1] = "empty"
            grid[h - 2, cx - gate_half : cx + gate_half + 1] = "empty"
            # left/right gates
            grid[cy - gate_half : cy + gate_half + 1, 0] = "empty"
            grid[cy - gate_half : cy + gate_half + 1, 1] = "empty"
            grid[cy - gate_half : cy + gate_half + 1, w - 1] = "empty"
            grid[cy - gate_half : cy + gate_half + 1, w - 2] = "empty"

        original_grid = self.grid
        original_height = self.height
        original_width = self.width

        try:
            self.grid = grid
            self.height = h
            self.width = w

            if cfg.layout == "tight":
                self._render_tight_layout(cx, cy)
            elif cfg.layout == "cramped_room":
                self._render_cramped_room_layout()
            elif cfg.layout == "service_pass_room":
                self._render_service_pass_room_layout()
            else:
                self._render_default_layout(cx, cy)
        finally:
            self.grid = original_grid
            self.height = original_height
            self.width = original_width

    def _place_spawn_pads(self, positions: Sequence[tuple[int, int]]) -> None:
        grid = self.grid
        h, w = self.height, self.width

        for x, y in positions:
            if 1 <= x < w - 1 and 1 <= y < h - 1 and grid[y, x] == "empty":
                grid[y, x] = self.config.spawn_symbol

    def _fill_missing_spawn_positions(
        self,
        positions: Sequence[tuple[int, int]],
        desired: int,
    ) -> list[tuple[int, int]]:
        if desired <= 0:
            return []

        seen: set[tuple[int, int]] = set()
        valid_positions: list[tuple[int, int]] = []
        grid = self.grid
        h, w = self.height, self.width

        for x, y in positions:
            pos = (x, y)
            if pos in seen:
                continue
            seen.add(pos)
            if 1 <= x < w - 1 and 1 <= y < h - 1 and grid[y, x] == "empty":
                valid_positions.append(pos)
            if len(valid_positions) >= desired:
                return valid_positions

        for pos in self._sample_random_spawn_positions(desired):
            if pos in seen:
                continue
            x, y = pos
            if 1 <= x < w - 1 and 1 <= y < h - 1 and grid[y, x] == "empty":
                valid_positions.append(pos)
                seen.add(pos)
            if len(valid_positions) >= desired:
                break

        return valid_positions

    def _sample_random_spawn_positions(
        self,
        count: int,
        *,
        min_x: int = 1,
        min_y: int = 1,
        max_x: int | None = None,
        max_y: int | None = None,
    ) -> list[tuple[int, int]]:
        """Sample random empty positions within an interior hub region for spawn pads."""
        grid = self.grid
        h, w = self.height, self.width
        min_x = max(1, min_x)
        min_y = max(1, min_y)
        resolved_max_x = w - 1 if max_x is None else min(w - 1, max_x)
        resolved_max_y = h - 1 if max_y is None else min(h - 1, max_y)

        if min_x >= resolved_max_x or min_y >= resolved_max_y:
            return []

        # Vectorized: find all empty cells inside the requested interior bounds.
        interior = grid[min_y:resolved_max_y, min_x:resolved_max_x]
        ys, xs = np.where(interior == "empty")
        # Offset back to full grid coordinates
        xs = xs + min_x
        ys = ys + min_y

        count = min(count, len(xs))
        indices = self.rng.choice(len(xs), size=count, replace=False)
        return [(int(xs[i]), int(ys[i])) for i in indices]

    def _place_stations(self, cx: int, cy: int, base_y: int, grid) -> None:
        """Place stations in a row centered at cx, starting at base_y.

        Stations are placed like chests, in a horizontal row centered around cx.
        """
        stations = self.config.stations
        if not stations:
            return

        h, w = self.height, self.width
        num_stations = len(stations)
        station_offsets = self.config.station_offsets

        if station_offsets is not None:
            if len(station_offsets) != num_stations:
                raise ValueError(
                    f"Expected {num_stations} station offsets, got {len(station_offsets)}. "
                    "Provide one (dx, dy) pair per station."
                )

            for station_name, (dx, dy) in zip(stations, station_offsets, strict=True):
                x = cx + int(dx)
                y = cy + int(dy)
                if not (1 <= x < w - 1 and 1 <= y < h - 1):
                    raise ValueError(
                        f"Cannot place station '{station_name}' at ({x}, {y}): "
                        f"out of bounds (hub width={w}, hub height={h})."
                    )
                if grid[y, x] != "empty":
                    raise ValueError(
                        f"Cannot place station '{station_name}' at ({x}, {y}): tile occupied by '{grid[y, x]}'."
                    )
                grid[y, x] = station_name
            return

        # Prefer the default spaced row, but compress to a dense row when the
        # hub interior is too narrow. This keeps tight layouts viable for
        # larger station sets without introducing game-specific placement rules.
        interior_width = max(1, w - 2)
        if num_stations <= 1:
            spacing = 1
        else:
            max_spacing_that_fits = max(1, (interior_width - 1) // (num_stations - 1))
            spacing = min(2, max_spacing_that_fits)
        row_span = 1 + (num_stations - 1) * spacing if num_stations > 1 else 1
        start_x = cx - row_span // 2

        for i, station_name in enumerate(stations):
            x = start_x + i * spacing

            # Check if x is out of bounds (station row doesn't fit in hub)
            if not (1 <= x < w - 1):
                raise ValueError(
                    f"Cannot place station '{station_name}' at x={x}: "
                    f"out of bounds (hub width={w}). Consider fewer stations or larger hub."
                )

            # Find a valid y position (try base_y, then search nearby)
            placed = False
            for dy in range(0, max(h, w)):
                for try_y in [base_y + dy, base_y - dy]:
                    if 1 <= try_y < h - 1 and grid[try_y, x] == "empty":
                        grid[try_y, x] = station_name
                        placed = True
                        break
                if placed:
                    break

            if not placed:
                raise ValueError(f"Cannot place station '{station_name}': no empty position found at x={x}")

    def _resolve_corner_names(self) -> list[str]:
        cfg = self.config
        names: list[str] = []
        if cfg.corner_objects and len(cfg.corner_objects) == 4:
            names = list(cfg.corner_objects)
        elif cfg.corner_generator:
            names = [cfg.corner_generator] * 4
        elif cfg.corner_bundle == "extractors":
            names = list(DEFAULT_EXTRACTORS)
        else:
            names = []
        return [n for n in names]

    def _resolve_cross_names(self) -> list[str]:
        cfg = self.config
        names: list[str] = []
        if cfg.cross_objects and len(cfg.cross_objects) == 4:
            names = list(cfg.cross_objects)
        elif cfg.cross_bundle == "extractors":
            names = list(DEFAULT_EXTRACTORS)
        else:
            names = []

        return [n for n in names]

    def _cross_positions(self, cx: int, cy: int, distance: int) -> list[tuple[int, int]]:
        dist = max(1, distance)
        return [
            (cx, cy - dist),
            (cx + dist, cy),
            (cx, cy + dist),
            (cx - dist, cy),
        ]

    def _place_named_objects(self, positions: Sequence[tuple[int, int]], names: Sequence[str]) -> None:
        grid = self.grid
        h, w = self.height, self.width
        pos_list = list(positions)
        name_list = list(names)
        # Enforce exact length when names are explicitly provided; allow empty to mean "place nothing"
        if name_list and len(name_list) != len(pos_list):
            raise ValueError(f"Expected {len(pos_list)} names, got {len(name_list)}")
        for (x, y), name in zip(pos_list, name_list, strict=True):
            if not name:
                continue
            if 0 <= x < w and 0 <= y < h:
                grid[y, x] = name

    def _render_default_layout(self, cx: int, cy: int) -> None:
        grid = self.grid
        h, w = self.height, self.width
        cfg = self.config

        corridor_width = 5
        half = corridor_width // 2

        # Carve plus-shaped corridors that meet each gate with corridor_width tiles
        x0 = max(1, cx - half)
        x1 = min(w - 1, cx + half + 1)
        y0 = max(1, cy - half)
        y1 = min(h - 1, cy + half + 1)

        grid[1 : h - 1, x0:x1] = "empty"
        grid[y0:y1, 1 : w - 1] = "empty"

        # Place central hub, junction after carving so they persist
        if 1 <= cx < w - 1 and 1 <= cy < h - 1:
            grid[cy, cx] = cfg.hub_object

            # Place stations in a row below the hub
            self._place_stations(cx, cy, cy + 4, grid)

        # Spawn pads: ensure at least spawn_count if provided, otherwise place 4
        desired = max(0, int(cfg.spawn_count)) if cfg.spawn_count is not None else 4

        if cfg.randomize_spawn_positions:
            valid_positions = self._sample_random_spawn_positions(desired)
        else:
            base_positions = [(cx, cy - 2), (cx + 2, cy), (cx, cy + 2), (cx - 2, cy)]
            valid_positions = []
            for sx, sy in base_positions:
                if len(valid_positions) >= desired:
                    break
                if 0 <= sx < w and 0 <= sy < h and grid[sy, sx] == "empty":
                    valid_positions.append((sx, sy))

            # If more spawns are needed, expand rings until we have enough empty tiles
            radius = 3
            max_radius = max(h, w)
            while len(valid_positions) < desired and radius < max_radius:
                candidates = [
                    (cx + radius, cy),
                    (cx - radius, cy),
                    (cx, cy + radius),
                    (cx, cy - radius),
                    (cx + radius, cy + radius),
                    (cx + radius, cy - radius),
                    (cx - radius, cy + radius),
                    (cx - radius, cy - radius),
                ]
                for sx, sy in candidates:
                    if len(valid_positions) >= desired:
                        break
                    if 0 <= sx < w and 0 <= sy < h and grid[sy, sx] == "empty":
                        valid_positions.append((sx, sy))
                radius += 1

        self._place_spawn_pads(valid_positions[:desired])

        # Place corner objects symmetrically
        corner_positions = [
            (2, 2),
            (w - 3, 2),
            (2, h - 3),
            (w - 3, h - 3),
        ]

        corner_names = self._resolve_corner_names()
        # Only place if corners are inside inner wall; enforce name count when provided
        if corner_names:
            if len(corner_names) != len(corner_positions):
                raise ValueError(f"Expected {len(corner_positions)} corner names, got {len(corner_names)}")
            for (x, y), name in zip(corner_positions, corner_names, strict=True):
                if not name:
                    continue
                if 1 <= x < w - 1 and 1 <= y < h - 1:
                    grid[y, x] = name

        cross_names = self._resolve_cross_names()
        if cross_names:
            cross_positions = self._cross_positions(cx, cy, cfg.cross_distance)
            self._place_named_objects(cross_positions, cross_names)

    def _render_tight_layout(self, cx: int, cy: int) -> None:
        grid = self.grid
        h, w = self.height, self.width
        cfg = self.config

        # Carve L exits first to keep ingress paths consistent with default layout
        self._carve_L(1, 1, orientation="right-down")
        self._carve_L(w - 4, 1, orientation="left-down")
        self._carve_L(1, h - 4, orientation="right-up")
        self._carve_L(w - 4, h - 4, orientation="left-up")

        core_radius = 3
        x0 = max(0, cx - core_radius)
        x1 = min(w, cx + core_radius + 1)
        y0 = max(0, cy - core_radius)
        y1 = min(h, cy + core_radius + 1)
        grid[y0:y1, x0:x1] = "empty"

        building_positions: list[tuple[int, int]] = []

        def place_building(x: int, y: int, name: str) -> None:
            if not (1 <= x < w - 1 and 1 <= y < h - 1):
                return
            if grid[y, x] != "empty":
                return
            grid[y, x] = name
            building_positions.append((x, y))

        if 1 <= cx < w - 1 and 1 <= cy < h - 1:
            place_building(cx, cy, cfg.hub_object)

        corner_positions = [
            (cx - 2, cy - 2),
            (cx + 2, cy - 2),
            (cx - 2, cy + 2),
            (cx + 2, cy + 2),
        ]

        corner_names = self._resolve_corner_names()
        if corner_names:
            if len(corner_names) != len(corner_positions):
                raise ValueError(f"Expected {len(corner_positions)} corner names, got {len(corner_names)}")
            for (x, y), name in zip(corner_positions, corner_names, strict=True):
                if not name:
                    continue
                place_building(x, y, name)

        cross_names = self._resolve_cross_names()
        if cross_names:
            cross_positions = self._cross_positions(cx, cy, cfg.cross_distance)
            self._place_named_objects(cross_positions, cross_names)

        self._ensure_clearance(building_positions)

        perimeter_radius = core_radius + 1
        self._build_tight_perimeter(cx, cy, perimeter_radius, gate_half=2)
        # Keep station row in tight layout as well. We keep it close to the
        # core so scripted policies can discover stations with local scans.
        self._place_stations(cx, cy, cy - 2, grid)

        # Spawn pads: ensure at least spawn_count if provided, otherwise place 4 near the perimeter
        desired = max(0, int(cfg.spawn_count)) if cfg.spawn_count is not None else 4

        if cfg.randomize_spawn_positions:
            valid_positions = self._sample_random_spawn_positions(desired)
        else:
            spawn_distance = perimeter_radius + 1
            positions: list[tuple[int, int]] = [
                (cx, cy - spawn_distance),
                (cx + spawn_distance, cy),
                (cx, cy + spawn_distance),
                (cx - spawn_distance, cy),
            ]
            # If more spawns needed, distribute more around the perimeter ring
            step = max(1, (2 * perimeter_radius + 1) // 4)
            if len(positions) < desired:
                for dx in range(-perimeter_radius, perimeter_radius + 1, step):
                    if len(positions) >= desired:
                        break
                    positions.append((cx + dx, cy - spawn_distance))
                    if len(positions) >= desired:
                        break
                    positions.append((cx + dx, cy + spawn_distance))
                for dy in range(-perimeter_radius, perimeter_radius + 1, step):
                    if len(positions) >= desired:
                        break
                    positions.append((cx - spawn_distance, cy + dy))
                    if len(positions) >= desired:
                        break
                    positions.append((cx + spawn_distance, cy + dy))

            valid_positions = self._fill_missing_spawn_positions(positions[:desired], desired)

        self._place_spawn_pads(valid_positions)

    def _render_cramped_room_layout(self) -> None:
        grid = self.grid
        h, w = self.height, self.width
        cfg = self.config

        template_w = 17
        template_h = 13
        if h < template_h or w < template_w:
            raise ValueError(f"cramped_room layout requires at least {template_w}x{template_h}, got hub size {w}x{h}")

        if len(cfg.stations) != len(CRAMPED_ROOM_STATION_ANCHORS):
            raise ValueError(
                "cramped_room layout expects exactly "
                f"{len(CRAMPED_ROOM_STATION_ANCHORS)} stations, got {len(cfg.stations)}"
            )

        # Keep the kitchen border open so the meaningful blockers are the
        # interior counters, not a perimeter wall frame.
        origin_x = max(0, w - template_w)
        origin_y = max(0, h - template_h)
        grid[:] = "empty"

        # Top prep counter run.
        grid[origin_y + 3, origin_x + 2 : origin_x + 13] = "wall"
        # Bottom service counter run.
        grid[origin_y + 7, origin_x + 6 : origin_x + 13] = "wall"
        # Right-side dish/serve spine.
        grid[origin_y + 3 : origin_y + 8, origin_x + 12] = "wall"
        grid[origin_y + 4, origin_x + 11] = "wall"
        grid[origin_y + 6, origin_x + 11] = "wall"

        for station_name, (anchor_x, anchor_y) in zip(cfg.stations, CRAMPED_ROOM_STATION_ANCHORS, strict=True):
            grid[origin_y + anchor_y, origin_x + anchor_x] = station_name

        spawn_positions = [(origin_x + x, origin_y + y) for x, y in CRAMPED_ROOM_SPAWNS]
        desired = max(0, int(cfg.spawn_count)) if cfg.spawn_count is not None else len(spawn_positions)
        if cfg.randomize_spawn_positions:
            valid_positions = self._sample_random_spawn_positions(
                desired,
                min_x=origin_x + 1,
                min_y=origin_y + 1,
                max_x=origin_x + template_w - 1,
                max_y=origin_y + template_h - 1,
            )
        else:
            valid_positions = self._fill_missing_spawn_positions(spawn_positions, desired)

        self._place_spawn_pads(valid_positions[:desired])

    def _render_service_pass_room_layout(self) -> None:
        grid = self.grid
        h, w = self.height, self.width
        cfg = self.config

        template_w = 17
        template_h = 13
        if h < template_h or w < template_w:
            raise ValueError(
                f"service_pass_room layout requires at least {template_w}x{template_h}, got hub size {w}x{h}"
            )

        if len(cfg.stations) != len(SERVICE_PASS_ROOM_STATION_ANCHORS):
            raise ValueError(
                "service_pass_room layout expects exactly "
                f"{len(SERVICE_PASS_ROOM_STATION_ANCHORS)} stations, got {len(cfg.stations)}"
            )

        # Keep the kitchen border open so the meaningful blockers are the
        # interior counters, not a perimeter wall frame.
        origin_x = max(0, w - template_w)
        origin_y = max(0, h - template_h)
        grid[:] = "empty"

        # Long top prep run with wider spacing between pickup and cook stations.
        grid[origin_y + 2, origin_x + 2 : origin_x + 14] = "wall"
        # Far-left order board spine against the wall.
        grid[origin_y + 3 : origin_y + 8, origin_x + 1] = "wall"
        # Mid-kitchen prep and cook islands.
        grid[origin_y + 5, origin_x + 4 : origin_x + 7] = "wall"
        grid[origin_y + 5, origin_x + 9 : origin_x + 12] = "wall"
        # Bottom service pass in the middle.
        grid[origin_y + 10, origin_x + 6 : origin_x + 14] = "wall"
        # Right-side wash spine with a couple of choke blockers.
        grid[origin_y + 3 : origin_y + 10, origin_x + 15] = "wall"
        grid[origin_y + 5, origin_x + 14] = "wall"
        grid[origin_y + 7, origin_x + 14] = "wall"

        for station_name, (anchor_x, anchor_y) in zip(cfg.stations, SERVICE_PASS_ROOM_STATION_ANCHORS, strict=True):
            grid[origin_y + anchor_y, origin_x + anchor_x] = station_name

        spawn_positions = [(origin_x + x, origin_y + y) for x, y in SERVICE_PASS_ROOM_SPAWNS]
        desired = max(0, int(cfg.spawn_count)) if cfg.spawn_count is not None else len(spawn_positions)
        if cfg.randomize_spawn_positions:
            valid_positions = self._sample_random_spawn_positions(
                desired,
                min_x=origin_x + 1,
                min_y=origin_y + 1,
                max_x=origin_x + template_w - 1,
                max_y=origin_y + template_h - 1,
            )
        else:
            valid_positions = self._fill_missing_spawn_positions(spawn_positions, desired)

        self._place_spawn_pads(valid_positions[:desired])

    def _ensure_clearance(self, positions: Sequence[tuple[int, int]]) -> None:
        grid = self.grid
        h, w = self.height, self.width

        for x, y in positions:
            for nx in range(x - 1, x + 2):
                if not (0 <= nx < w):
                    continue
                for ny in range(y - 1, y + 2):
                    if not (0 <= ny < h):
                        continue
                    if (nx, ny) == (x, y):
                        continue
                    grid[ny, nx] = "empty"

    def _build_tight_perimeter(self, cx: int, cy: int, radius: int, gate_half: int) -> None:
        if radius <= 0:
            return

        grid = self.grid
        h, w = self.height, self.width

        for x in range(cx - radius, cx + radius + 1):
            for y in range(cy - radius, cy + radius + 1):
                if not (0 <= x < w and 0 <= y < h):
                    continue

                on_perimeter = (abs(x - cx) == radius and abs(y - cy) <= radius) or (
                    abs(y - cy) == radius and abs(x - cx) <= radius
                )
                if not on_perimeter:
                    continue

                on_gate = (abs(x - cx) <= gate_half and abs(y - cy) == radius) or (
                    abs(y - cy) <= gate_half and abs(x - cx) == radius
                )

                if on_gate:
                    continue

                grid[y, x] = "wall"

    def _carve_L(self, x: int, y: int, orientation: Literal["right-down", "left-down", "right-up", "left-up"]):
        grid = self.grid
        h, w = self.height, self.width

        width = 5
        leg = max(3, min(h, w) // 3)  # leg length based on base size

        def carve_rect(x0: int, y0: int, cw: int, ch: int):
            x1 = max(0, x0)
            y1 = max(0, y0)
            x2 = min(w, x0 + cw)
            y2 = min(h, y0 + ch)
            if x2 > x1 and y2 > y1:
                grid[y1:y2, x1:x2] = "empty"

        if orientation == "right-down":
            # horizontal then vertical
            carve_rect(x, y, leg, width)
            carve_rect(x + leg - width, y, width, leg)
            # open top border
            carve_rect(x, 0, width, 1)
        elif orientation == "left-down":
            carve_rect(x - leg + width, y, leg, width)
            carve_rect(x - leg + width, y, width, leg)
            # open top border
            carve_rect(x - width + 1, 0, width, 1)
        elif orientation == "right-up":
            carve_rect(x, y, leg, width)
            carve_rect(x + leg - width, y - leg + width, width, leg)
            # open left border
            carve_rect(0, y - width + 1, width, width)
        elif orientation == "left-up":
            carve_rect(x - leg + width, y, leg, width)
            carve_rect(x - leg + width, y - leg + width, width, leg)
            # open bottom border
            carve_rect(x - width + 1, h - 1, width, 1)
