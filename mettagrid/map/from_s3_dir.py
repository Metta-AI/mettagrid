# Root map generator, based on nodes.

import random

from mettagrid.map.from_uri import FromUri
from mettagrid.map.utils.serialization import load_from_uri, parse_s3_uri

from .scene import SceneCfg


class FromS3Dir(FromUri):
    """
    Load a random map from a directory of pregenerated maps.

    The directory must contain a file `index.txt` that lists all the maps in the
    directory. (Listing S3 objects would be too slow because of pagination.)

    The index file can be produced with the following command:
        python -m tools.index_s3_maps index_s3_maps.dir=s3://...
    """

    def __init__(self, s3_dir: str, extra_root: SceneCfg | None = None):
        self._s3_dir = s3_dir

        # For 10k maps in a directory we'd have to fetch 100Kb of index data.
        # (Can we optimize this further by caching?)
        index_uri = load_from_uri(self._s3_dir + "/index.txt")
        index = index_uri.split("\n")
        random_map = random.choice(index)

        bucket, _ = parse_s3_uri(s3_dir)
        super().__init__(f"s3://{bucket}/{random_map}", extra_root)
