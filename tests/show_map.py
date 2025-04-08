import os
import signal  # Aggressively exit on ctrl+c

import hydra
from mettagrid.mettagrid_env import MettaGridEnv
from mettagrid.renderer.raylib.raylib_renderer import MettaGridRaylibRenderer

signal.signal(signal.SIGINT, lambda sig, frame: os._exit(0))

@hydra.main(version_base=None, config_path="../configs", config_name="simple")
def main(cfg):
    env = MettaGridEnv(cfg, render_mode="human")

    mode = cfg.get('show_map', {}).get('mode', "raylib")
    if mode == "raylib":
        renderer = MettaGridRaylibRenderer(env._c_env, env._env_cfg.game)
        while True:
            renderer.render_and_wait()
    elif mode == "ascii":
        print(env._c_env.render())
    elif mode == "ascii_border":
        # Useful for generating examples for docstrings in code.
        grid = env._c_env.render_ascii(["A", "#", "g", "c", "a"])
        lines = ["┌" + "─" * len(grid[0]) + "┐"]
        for row in grid:
            lines.append("│" + "".join(row) + "│")
        lines.append("└" + "─" * len(grid[0]) + "┘")
        print("\n".join(lines))
    else:
        raise ValueError(f"Invalid mode: {mode}")


if __name__ == "__main__":
    main()
