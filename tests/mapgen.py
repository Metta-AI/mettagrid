import os
import signal  # Aggressively exit on ctrl+c
import random
import string

import hydra
from omegaconf import OmegaConf
from mettagrid.mettagrid_env import MettaGridEnv
from mettagrid.renderer.raylib.raylib_renderer import MettaGridRaylibRenderer

signal.signal(signal.SIGINT, lambda sig, frame: os._exit(0))

def env_to_ascii(env):
    grid = env._c_env.render_ascii()
    # convert to strings
    return ["".join(row) for row in grid]

@hydra.main(version_base=None, config_path="../configs", config_name="mapgen")
def main(cfg):
    env = MettaGridEnv(cfg, render_mode="human")

    ascii_grid = env_to_ascii(env)
    
    if cfg.mapgen.save:
        target_name = cfg.mapgen.target.get('name', None)
        if target_name is None:
            random_suffix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))
            target_name = f"map_{random_suffix}.yaml"

        target_file = os.path.join(cfg.mapgen.target.dir, target_name)
        with open(target_file, "w") as f:
            # Note: OmegaConf messes up multiline strings (adds extra newlines). But we take care of it in the mettamap viewer.
            f.write(OmegaConf.to_yaml(cfg.game.map_builder))
            f.write("\n---\n")
            f.write("\n".join(ascii_grid) + "\n")

    show = cfg.mapgen.show
    if show == "raylib":
        renderer = MettaGridRaylibRenderer(env._c_env, env._env_cfg.game)
        while True:
            renderer.render_and_wait()
    elif show == "ascii":
        print("\n".join(ascii_grid))
    elif show == "ascii_border":
        # Useful for generating examples for docstrings in code.
        width = len(ascii_grid[0])
        lines = ["┌" + "─" * width + "┐"]
        for row in ascii_grid:
            lines.append("│" + row + "│")
        lines.append("└" + "─" * width + "┘")
        print("\n".join(lines))
    elif show == "none":
        pass
    else:
        raise ValueError(f"Invalid show mode: {show}")


if __name__ == "__main__":
    main()
