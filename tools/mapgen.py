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


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=str)
    parser.add_argument("--output-uri", type=str)
    parser.add_argument("--show", choices=get_args(ShowMode))
    parser.add_argument("--count", type=int, default=1)
    parser.add_argument("--overrides", type=str, default="")
    parser.add_argument("cfg_path", type=str)
    args = parser.parse_args()

    show_mode = args.show
    if not show_mode and not args.output_dir and not args.output_uri:
        # if not asked to save, show the map
        show_mode = "raylib"

    output_dir = args.output_dir
    output_uri = args.output_uri
    count = args.count
    cfg_path = args.cfg_path
    overrides = args.overrides

    overrides_cfg = OmegaConf.from_cli([override for override in overrides.split(" ") if override])

    if output_uri and count > 1:
        raise ValueError("Cannot provide both output_uri and count > 1")

    if output_dir and output_uri:
        raise ValueError("Cannot provide both output_dir and output_uri")

    def make_output_uri() -> str | None:
        if output_uri:
            return output_uri

        if not output_dir:
            return None  # the map won't be saved

        random_suffix = "".join(random.choices(string.ascii_lowercase + string.digits, k=8))
        return f"{output_dir}/map_{random_suffix}.yaml"

    if output_uri:
        output_dir = os.path.dirname(output_uri)

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
