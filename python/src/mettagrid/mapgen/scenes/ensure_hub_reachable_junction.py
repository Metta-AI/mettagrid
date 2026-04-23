from __future__ import annotations

from collections import deque

from mettagrid.mapgen.scene import Scene, SceneConfig


class EnsureHubReachableJunctionConfig(SceneConfig):
    """Ensure each hub/ship has at least one nearby neutral junction."""

    anchor_suffixes: list[str] = [":hub", ":ship"]
    anchor_names: list[str] = ["hub", "ship"]
    junction_name: str = "junction"
    min_distance: int = 4
    max_distance: int = 15


class EnsureHubReachableJunction(Scene[EnsureHubReachableJunctionConfig]):
    def _is_hub_cell(self, value: object) -> bool:
        if not isinstance(value, str):
            return False
        return (
            any(value.endswith(s) or f"{s}:" in value for s in self.config.anchor_suffixes)
            or value in self.config.anchor_names
        )

    def _is_passable(self, value: object) -> bool:
        if not isinstance(value, str):
            return False
        if value == "empty":
            return True
        if value == self.config.junction_name:
            return True
        return self._is_hub_cell(value)

    def _reachable_cells(self, start_r: int, start_c: int) -> set[tuple[int, int]]:
        grid = self.grid
        h, w = self.height, self.width
        if not (0 <= start_r < h and 0 <= start_c < w):
            return set()
        if not self._is_passable(grid[start_r, start_c]):
            return set()

        q = deque([(start_r, start_c)])
        seen = {(start_r, start_c)}
        while q:
            r, c = q.popleft()
            for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                nr = r + dr
                nc = c + dc
                if nr < 0 or nr >= h or nc < 0 or nc >= w:
                    continue
                if (nr, nc) in seen:
                    continue
                if not self._is_passable(grid[nr, nc]):
                    continue
                seen.add((nr, nc))
                q.append((nr, nc))
        return seen

    def render(self) -> None:
        cfg = self.config
        grid = self.grid
        h, w = self.height, self.width

        hubs: list[tuple[int, int]] = []
        junctions: list[tuple[int, int]] = []
        for r in range(h):
            for c in range(w):
                cell = grid[r, c]
                if self._is_hub_cell(cell):
                    hubs.append((r, c))
                elif cell == cfg.junction_name:
                    junctions.append((r, c))

        if not hubs:
            return

        min_r2 = cfg.min_distance * cfg.min_distance
        max_r2 = cfg.max_distance * cfg.max_distance

        for hr, hc in hubs:
            reachable = self._reachable_cells(hr, hc)
            has_reachable_nearby_junction = any(
                (jr - hr) * (jr - hr) + (jc - hc) * (jc - hc) <= max_r2 and (jr, jc) in reachable
                for jr, jc in junctions
            )
            if has_reachable_nearby_junction:
                continue

            candidates: list[tuple[int, int, int]] = []
            r0 = max(0, hr - cfg.max_distance)
            r1 = min(h, hr + cfg.max_distance + 1)
            c0 = max(0, hc - cfg.max_distance)
            c1 = min(w, hc + cfg.max_distance + 1)
            for r in range(r0, r1):
                for c in range(c0, c1):
                    if grid[r, c] != "empty":
                        continue
                    if (r, c) not in reachable:
                        continue
                    d2 = (r - hr) * (r - hr) + (c - hc) * (c - hc)
                    if d2 < min_r2 or d2 > max_r2:
                        continue
                    candidates.append((d2, r, c))

            if not candidates:
                continue

            candidates.sort(key=lambda x: x[0])
            best_d2 = candidates[0][0]
            best = [(r, c) for d2, r, c in candidates if d2 == best_d2]
            idx = int(self.rng.integers(0, len(best)))
            rr, cc = best[idx]
            grid[rr, cc] = cfg.junction_name
            junctions.append((rr, cc))
