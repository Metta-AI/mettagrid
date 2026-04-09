import numpy as np
import pytest

from mettagrid.mapgen.scenes.compound import (
    CRAMPED_ROOM_STATION_ANCHORS,
    SERVICE_PASS_ROOM_STATION_ANCHORS,
    Compound,
)
from mettagrid.test_support.mapgen import render_scene


@pytest.mark.parametrize(
    ("layout", "station_count"),
    [
        ("cramped_room", len(CRAMPED_ROOM_STATION_ANCHORS)),
        ("service_pass_room", len(SERVICE_PASS_ROOM_STATION_ANCHORS)),
    ],
)
def test_randomized_spawn_positions_stay_inside_overcooked_layout_interior(
    layout: str,
    station_count: int,
) -> None:
    hub_width = 21
    hub_height = 21
    template_width = 17
    template_height = 13
    scene = render_scene(
        Compound.Config(
            layout=layout,
            hub_width=hub_width,
            hub_height=hub_height,
            randomize_spawn_positions=True,
            spawn_count=999,
            stations=[f"station_{i}" for i in range(station_count)],
        ),
        shape=(hub_height, hub_width),
    )

    spawn_positions = np.argwhere(scene.grid == scene.config.spawn_symbol)

    assert len(spawn_positions) > 0
    assert spawn_positions[:, 1].min() >= hub_width - template_width + 1
    assert spawn_positions[:, 0].min() >= hub_height - template_height + 1


@pytest.mark.parametrize(
    ("layout", "station_count"),
    [
        ("cramped_room", len(CRAMPED_ROOM_STATION_ANCHORS)),
        ("service_pass_room", len(SERVICE_PASS_ROOM_STATION_ANCHORS)),
    ],
)
def test_overcooked_layouts_keep_outer_border_open(
    layout: str,
    station_count: int,
) -> None:
    scene = render_scene(
        Compound.Config(
            layout=layout,
            hub_width=18,
            hub_height=14,
            stations=[f"station_{i}" for i in range(station_count)],
        ),
        shape=(14, 18),
    )

    assert np.all(scene.grid[0, :] != "wall")
    assert np.all(scene.grid[:, 0] != "wall")
    assert np.all(scene.grid[-1, :] != "wall")
    assert np.all(scene.grid[:, -1] != "wall")
