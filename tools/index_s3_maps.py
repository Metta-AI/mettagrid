import logging
import os
import signal  # Aggressively exit on ctrl+c

import hydra

from mettagrid.map.utils.serialization import get_s3_client, is_s3_uri, parse_s3_uri, save_to_uri

signal.signal(signal.SIGINT, lambda sig, frame: os._exit(0))
logger = logging.getLogger(__name__)


@hydra.main(version_base=None, config_path="../configs", config_name="index_s3_maps")
def main(cfg):
    s3_dir = cfg.index_s3_maps.dir
    if not is_s3_uri(s3_dir):
        s3_dir = f"{cfg.s3.maps_root}/{s3_dir}"

    s3 = get_s3_client()
    bucket, key = parse_s3_uri(s3_dir)

    paginator = s3.get_paginator("list_objects_v2")
    pages = paginator.paginate(Bucket=bucket, Prefix=key)

    uri_list: list[str] = []
    logger.info(f"Listing objects in s3://{bucket}/{key}...")
    for page in pages:
        if "Contents" not in page:
            continue

        for obj in page["Contents"]:
            obj_key = obj["Key"]
            if obj_key == key or not obj_key.endswith(".yaml"):
                continue
            uri_list.append(f"s3://{bucket}/{obj_key}")

    logger.info("Finished listing objects.")

    target = cfg.index_s3_maps.target
    if target is None:
        target = f"{s3_dir}/index.txt"

    save_to_uri(text="\n".join(uri_list), uri=target)
    logger.info(f"Index with {len(uri_list)} maps saved to {target}")


if __name__ == "__main__":
    main()
