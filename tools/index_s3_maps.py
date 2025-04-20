import logging
import os
import signal  # Aggressively exit on ctrl+c

import hydra

from mettagrid.map.utils.serialization import get_s3_client, parse_s3_uri, save_to_uri

signal.signal(signal.SIGINT, lambda sig, frame: os._exit(0))
logger = logging.getLogger(__name__)


@hydra.main(version_base=None, config_path="../configs", config_name="index_s3_maps")
def main(cfg):
    s3_dir = cfg.index_s3_maps.dir
    s3 = get_s3_client()
    bucket, key = parse_s3_uri(s3_dir)
    response = s3.list_objects_v2(Bucket=bucket, Prefix=key)

    keys: list[str] = []
    for obj in response["Contents"]:
        keys.append(obj["Key"])

    save_to_uri(text="\n".join(keys), uri=f"{s3_dir}/index.txt")


if __name__ == "__main__":
    main()
