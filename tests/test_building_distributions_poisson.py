import numpy as np

from mettagrid.mapgen.scenes.building_distributions import (
    DistributionConfig,
    DistributionType,
    _sample_positions_by_distribution,
)


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

    def chebyshev(a: tuple[int, int], b: tuple[int, int]) -> int:
        return max(abs(a[0] - b[0]), abs(a[1] - b[1]))

    for i in range(len(positions)):
        for j in range(i + 1, len(positions)):
            assert chebyshev(positions[i], positions[j]) >= min_dist
