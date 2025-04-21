import logging
import os
import signal  # Aggressively exit on ctrl+c

import hydra

from mettagrid.map.utils import s3utils

signal.signal(signal.SIGINT, lambda sig, frame: os._exit(0))
logger = logging.getLogger(__name__)


@hydra.main(version_base=None, config_path="../configs", config_name="index_s3_maps")
def main(cfg):
    s3_dir = cfg.index_s3_maps.dir
    if not s3utils.is_s3_uri(s3_dir):
        s3_dir = f"{cfg.s3.maps_root}/{s3_dir}"

    uri_list = s3utils.list_objects(s3_dir)

    target = cfg.index_s3_maps.target
    if target is None:
        target = f"{s3_dir}/index.txt"

    s3utils.save_to_uri(text="\n".join(uri_list), uri=target)
    logger.info(f"Index with {len(uri_list)} maps saved to {target}")


if __name__ == "__main__":
    main()
