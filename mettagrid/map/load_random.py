# Root map generator, based on nodes.

import random

from mettagrid.map.load import Load
from mettagrid.map.utils.serialization import load_from_uri

from .scene import SceneCfg


class LoadRandom(Load):
    """
    Load a random map from a list of pregenerated maps.

    The directory must contain a file `index.txt` that lists all the maps in the
    directory. (Listing S3 objects would be too slow because of pagination.)

    The index file can be produced with the following command:
        python -m tools.index_s3_maps index_s3_maps.dir=s3://...
    """

    def __init__(self, index_uri: str, extra_root: SceneCfg | None = None):
        self._index_uri = index_uri

        # For 10k maps in a directory we'd have to fetch 100Kb of index data.
        # (Can we optimize this further by caching?)
        index = load_from_uri(self._index_uri)
        index = index.split("\n")
        random_map_uri = random.choice(index)

        super().__init__(random_map_uri, extra_root)
