import hydra
import numpy as np

# Make sure all modules import without errors:
import mettagrid

import mettagrid.mettagrid_env
import mettagrid.objects
import mettagrid.observation_encoder

import mettagrid.actions.actions
import mettagrid.actions.attack
import mettagrid.actions.gift
import mettagrid.actions.move
import mettagrid.actions.noop
import mettagrid.actions.rotate
import mettagrid.actions.shield
import mettagrid.actions.swap
import mettagrid.actions.use

import mettagrid.config.game_builder
import mettagrid.config.sample_config

import puffergrid
import puffergrid.action
import puffergrid.event
import puffergrid.grid_env
import puffergrid.grid_object
import puffergrid.observation_encoder
import puffergrid.stats_tracker

# Make sure all dependencies are installed:
import hydra
import jmespath
import matplotlib
import pettingzoo
import pynvml
import pytest
import yaml
import raylib
import rich
import scipy
import tabulate
import tensordict
import torchrl
import termcolor
import wandb
import wandb_core
import pandas
import tqdm

@hydra.main(version_base=None, config_path="../configs", config_name="test_basic")
def main(cfg):

    # Create the environment:
    metta_grid_env = mettagrid.mettagrid_env.metta_grid_env(render_mode=None, **cfg)

    # Make sure the environment was created correctly:
    print("metta_grid_env._renderer: ", metta_grid_env._renderer)
    assert metta_grid_env._renderer is None
    print("metta_grid_env._c_env: ", metta_grid_env._c_env)
    assert metta_grid_env._c_env is not None
    print("metta_grid_env._grid_env: ", metta_grid_env._grid_env)
    assert metta_grid_env._grid_env is not None
    assert metta_grid_env._c_env == metta_grid_env._grid_env
    print("metta_grid_env.done: ", metta_grid_env.done)
    assert metta_grid_env.done == False

    # Make sure reset works:
    metta_grid_env.reset()

    # Run a single step:
    print("current_timestep: ", metta_grid_env._c_env.current_timestep())
    assert metta_grid_env._c_env.current_timestep() == 0
    (obs, rewards, terminated, truncated, infos) = metta_grid_env.step([[0,0]]*5)
    assert metta_grid_env._c_env.current_timestep() == 1
    print("obs: ", obs)
    assert obs.shape == (5, 24, 11, 11)
    print("rewards: ", rewards)
    assert rewards.shape == (5,)
    print("terminated: ", terminated)
    assert np.array_equal(terminated, [0, 0, 0, 0, 0])
    print("truncated: ", truncated)
    assert np.array_equal(truncated, [0, 0, 0, 0, 0])
    print("infos: ", infos)

    print(metta_grid_env._c_env.render())

    print("grid_objects: ")
    for grid_object in metta_grid_env._c_env.grid_objects().values():
      print(f"* {grid_object}")

    infos = {}
    metta_grid_env.process_episode_stats(infos)
    print("process_episode_stats infos: ", infos)

    # Print some environment info:
    print("metta_grid_env._max_steps: ", metta_grid_env._max_steps)
    assert metta_grid_env._max_steps == 5000
    print("metta_grid_env.observation_space: ", metta_grid_env.observation_space)
    assert metta_grid_env.observation_space.shape == (24, 11, 11)
    print("metta_grid_env.action_space: ", metta_grid_env.action_space)
    assert metta_grid_env.action_space.nvec.tolist() == [8, 9]
    print("metta_grid_env.action_names(): ", metta_grid_env.action_names())
    print("metta_grid_env.grid_features: ", metta_grid_env.grid_features)
    print("metta_grid_env.global_features: ", metta_grid_env.global_features)
    print("metta_grid_env.render_mode: ", metta_grid_env.render_mode)
    assert metta_grid_env.render_mode == None

    print("metta_grid_env._c_env.map_width(): ", metta_grid_env._c_env.map_width())
    assert metta_grid_env._c_env.map_width() == 25
    print("metta_grid_env._c_env.map_height(): ", metta_grid_env._c_env.map_height())
    assert metta_grid_env._c_env.map_height() == 25

    print("metta_grid_env._c_env.num_agents(): ", metta_grid_env._c_env.num_agents())
    assert metta_grid_env._c_env.num_agents() == 5

if __name__ == "__main__":
    main()
