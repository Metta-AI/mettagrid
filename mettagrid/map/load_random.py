import random

from mettagrid.map.load import Load
from mettagrid.map.utils import s3utils

from .scene import SceneCfg


class LoadRandom(Load):
    """
    Load a random map from S3 directory.

    See also: `LoadRandomFromIndex` for a version that loads a random map from a pre-generated index.
    """

    def __init__(self, dir: str, extra_root: SceneCfg | None = None):
        self._dir = dir

        uris = s3utils.list_objects(self._dir)
        uris = [uri for uri in uris if uri.endswith(".yaml")]
        random_map_uri = random.choice(uris)

        super().__init__(random_map_uri, extra_root)
