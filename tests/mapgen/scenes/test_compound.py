import numpy as np
import pytest

from mettagrid.mapgen.scenes.compound import (
    CRAMPED_ROOM_STATION_ANCHORS,
    SERVICE_PASS_ROOM_STATION_ANCHORS,
    Compound,
)
from mettagrid.test_support.mapgen import render_scene


def test_station_offsets_omitted_when_unset() -> None:
    cfg = Compound.Config(stations=["alpha_station"])

    data = cfg.model_dump()

    assert "station_offsets" not in data


def test_station_offsets_serialized_when_set() -> None:
    cfg = Compound.Config(stations=["alpha_station"], station_offsets=[(1, -1)])

    data = cfg.model_dump(mode="json")

    assert data["station_offsets"] == [[1, -1]]


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
