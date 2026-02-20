import math

import numpy as np

from mettagrid.mapgen.scenes.building_distributions import (
    DistributionConfig,
    DistributionType,
    _sample_positions_by_distribution,
)


def _l2_dist(a: tuple[int, int], b: tuple[int, int]) -> float:
    dr = a[0] - b[0]
    dc = a[1] - b[1]
    return math.sqrt(dr * dr + dc * dc)


def test_poisson_distribution_enforces_min_separation() -> None:
    rng = np.random.default_rng(0)
    dist = DistributionConfig(type=DistributionType.POISSON)

    row_min, row_max = 0, 49
    col_min, col_max = 0, 49
    available_width = col_max - col_min + 1
    available_height = row_max - row_min + 1

    count = 40
    area = available_width * available_height
    min_dist = max(1, int(np.sqrt(area / count) * 0.5))
    assert min_dist >= 2

    positions = _sample_positions_by_distribution(
        count=count,
        width=50,
        height=50,
        row_min=row_min,
        row_max=row_max,
        col_min=col_min,
        col_max=col_max,
        dist_config=dist,
        rng=rng,
    )

    assert len(positions) == count

    for i in range(len(positions)):
        for j in range(i + 1, len(positions)):
            assert _l2_dist(positions[i], positions[j]) >= min_dist


def test_poisson_distribution_cogsguard_min_separation_targets() -> None:
    def _min_pairwise_l2(positions: list[tuple[int, int]]) -> float:
        return min(
            _l2_dist(positions[i], positions[j]) for i in range(len(positions)) for j in range(i + 1, len(positions))
        )

    dist = DistributionConfig(type=DistributionType.POISSON)

    # 48x48 interior with count=84 corresponds to the current CogsGuard arena junction group.
    arena_positions = _sample_positions_by_distribution(
        count=84,
        width=50,
        height=50,
        row_min=1,
        row_max=48,
        col_min=1,
        col_max=48,
        dist_config=dist,
        rng=np.random.default_rng(0),
    )
    assert len(arena_positions) == 84
    assert _min_pairwise_l2(arena_positions) >= 3

    # 86x86 interior with count=158 corresponds to the current CogsGuard Machina1 junction group.
    machina_positions = _sample_positions_by_distribution(
        count=158,
        width=88,
        height=88,
        row_min=1,
        row_max=86,
        col_min=1,
        col_max=86,
        dist_config=dist,
        rng=np.random.default_rng(0),
    )
    assert len(machina_positions) == 158
    assert _min_pairwise_l2(machina_positions) >= 4
