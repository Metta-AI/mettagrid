import logging
import os
import random
import signal  # Aggressively exit on ctrl+c
import string
import time
from typing import Literal

import hydra

from mettagrid.map.utils.serialization import AsciiMap, env_to_ascii
from mettagrid.mettagrid_env import MettaGridEnv

signal.signal(signal.SIGINT, lambda sig, frame: os._exit(0))

logger = logging.getLogger(__name__)


ShowMode = Literal["raylib", "ascii", "ascii_border", "none"]


def show_env(env: MettaGridEnv, mode: ShowMode):
    if mode == "raylib":
        from mettagrid.renderer.raylib.raylib_renderer import MettaGridRaylibRenderer

        renderer = MettaGridRaylibRenderer(env._c_env, env._env_cfg.game)
        while True:
            renderer.render_and_wait()

    elif mode == "ascii":
        ascii_lines = env_to_ascii(env)
        print("\n".join(ascii_lines))

    elif mode == "ascii_border":
        ascii_lines = env_to_ascii(env, border=True)
        print("\n".join(ascii_lines))

    elif mode == "none":
        pass

    else:
        raise ValueError(f"Invalid show mode: {mode}")


@hydra.main(version_base=None, config_path="../configs", config_name="mapgen")
def main(cfg):
    # Generate and measure time taken
    start = time.time()
    env = MettaGridEnv(cfg, render_mode="human")
    gen_time = time.time() - start
    logger.info(f"Time taken to create env: {gen_time} seconds")

    # Save the map if requested
    if cfg.mapgen.save:
        target_name = cfg.mapgen.target.get("name", None)
        if target_name is None:
            random_suffix = "".join(random.choices(string.ascii_lowercase + string.digits, k=8))
            target_name = f"map_{random_suffix}.yaml"

        target_uri = os.path.join(cfg.mapgen.target.dir, target_name)
        ascii_map = AsciiMap.from_env(env, gen_time=gen_time)
        ascii_map.save(target_uri)

    # Show the map if requested
    show_env(env, cfg.mapgen.show)


if __name__ == "__main__":
    main()
