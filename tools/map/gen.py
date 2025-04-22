import argparse
import logging
import os
import random
import signal
import string
import time
from datetime import datetime
from typing import Any, Literal, cast, get_args

import hydra
import numpy as np
from omegaconf import DictConfig, OmegaConf

from mettagrid.map.utils.storable_map import StorableMap, grid_to_ascii
from mettagrid.mettagrid_env import MettaGridEnv

# Aggressively exit on ctrl+c
signal.signal(signal.SIGINT, lambda sig, frame: os._exit(0))

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

ShowMode = Literal["raylib", "ascii", "ascii_border"]


def show_map(storable_map: StorableMap, mode: ShowMode | None):
    if not mode:
        return

    if mode == "raylib":
        num_agents = np.count_nonzero(np.char.startswith(storable_map.grid, "agent"))

        env_cfg = OmegaConf.load("configs/mettagrid.yaml")
        env_cfg.game.num_agents = num_agents

        env = MettaGridEnv(cast(Any, env_cfg), env_map=storable_map.grid, render_mode="none")

        from mettagrid.renderer.raylib.raylib_renderer import MettaGridRaylibRenderer

        renderer = MettaGridRaylibRenderer(env._c_env, env._env_cfg.game)
        while True:
            renderer.render_and_wait()

    elif mode == "ascii":
        ascii_lines = grid_to_ascii(storable_map.grid)
        print("\n".join(ascii_lines))

    elif mode == "ascii_border":
        ascii_lines = grid_to_ascii(storable_map.grid, border=True)
        print("\n".join(ascii_lines))

    else:
        raise ValueError(f"Invalid show mode: {mode}")


def make_map(cfg_path: str, overrides: DictConfig | None = None):
    cfg: DictConfig = cast(DictConfig, OmegaConf.merge(OmegaConf.load(cfg_path), overrides))
    if not OmegaConf.is_dict(cfg):
        raise ValueError(f"Invalid config type: {type(cfg)}")

    # Generate and measure time taken
    start = time.time()
    map_builder = hydra.utils.instantiate(cfg, _recursive_=False)
    grid = map_builder.build()
    gen_time = time.time() - start
    logger.info(f"Time taken to build map: {gen_time}s")

    storable_map = StorableMap(
        grid=grid,
        metadata={
            "gen_time": gen_time,
            "timestamp": datetime.now().isoformat(),
        },
        config=cfg,
    )
    return storable_map


def uri_is_file(uri: str) -> bool:
    last_part = uri.split("/")[-1]
    return "." in last_part and len(last_part.split(".")[-1]) <= 4


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-uri", type=str, help="Output URI")
    parser.add_argument("--show", choices=get_args(ShowMode), help="Show the map in the specified mode")
    parser.add_argument("--count", type=int, default=1, help="Number of maps to generate")
    parser.add_argument("--overrides", type=str, default="", help="OmniConf overrides for the map config")
    parser.add_argument("cfg_path", type=str, help="Path to the map config file")
    args = parser.parse_args()

    show_mode = args.show
    if not show_mode and not args.output_uri:
        # if not asked to save, show the map
        show_mode = "raylib"

    output_uri = args.output_uri
    count = args.count
    cfg_path = args.cfg_path
    overrides = args.overrides

    overrides_cfg = OmegaConf.from_cli([override for override in overrides.split(" ") if override])

    if count > 1 and not output_uri:
        # requested multiple maps, let's check that output_uri is a directory
        if not output_uri:
            raise ValueError("Cannot generate more than one map without providing output_uri")

    # s3 can store things at s3://.../foo////file, so we need to remove trailing slashes
    while output_uri and output_uri.endswith("/"):
        output_uri = output_uri[:-1]

    output_is_file = output_uri and uri_is_file(output_uri)

    if count > 1 and output_is_file:
        raise ValueError(f"{output_uri} looks like a file, cannot generate multiple maps in a single file")

    def make_output_uri() -> str | None:
        if not output_uri:
            return None  # the map won't be saved

        if output_is_file:
            return output_uri

        random_suffix = "".join(random.choices(string.ascii_lowercase + string.digits, k=8))
        return f"{output_uri}/map_{random_suffix}.yaml"

    for i in range(count):
        if count > 1:
            logger.info(f"Generating map {i + 1} of {count}")

        # Generate and measure time taken
        storable_map = make_map(cfg_path, overrides_cfg)

        # Save the map if requested
        target_uri = make_output_uri()
        if target_uri:
            storable_map.save(target_uri)

        # Show the map if requested
        show_map(storable_map, show_mode)


if __name__ == "__main__":
    main()
