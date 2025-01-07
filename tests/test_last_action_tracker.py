import hydra
import numpy as np
import mettagrid
import mettagrid.mettagrid_env
from test_env import render_obs_to_string, render_to_string, header

@hydra.main(version_base=None, config_path="../configs", config_name="test_basic")
def main(cfg):
    output = ""

    output += header("Last Action Tracker:")
    np.random.seed(123)
    cfg.last_action_tracker = True
    metta_grid_env = mettagrid.mettagrid_env.MettaGridEnv(render_mode=None, **cfg)
    metta_grid_env.reset()

    actions = [
        [0,5],
        [1,6],
        [2,7],
        [3,8],
        [4,9],
    ]
    output += render_to_string(metta_grid_env)

    (obs, rewards, terminated, truncated, infos) = metta_grid_env.step(actions)
    output += header("Observations:")
    output += render_obs_to_string(metta_grid_env, obs, match="last_action")

    output += f"grid_features: {metta_grid_env.grid_features}\n"

    assert "last_action" in metta_grid_env.grid_features
    assert "last_action_argument" in metta_grid_env.grid_features

    output += f"rewards: {rewards}\n"
    output += f"terminated: {terminated}\n"
    output += f"truncated: {truncated}\n"
    output += f"infos: {infos}\n"
    output += f"obs.shape: {obs.shape}\n"

    output += header("# No Last Action Tracker:")

    cfg.last_action_tracker = False
    metta_grid_env = mettagrid.mettagrid_env.MettaGridEnv(render_mode=None, **cfg)
    output += f"grid_features: {metta_grid_env.grid_features}\n"

    assert "last_action" not in metta_grid_env.grid_features
    assert "last_action_argument" not in metta_grid_env.grid_features

    (obs, rewards, terminated, truncated, infos) = metta_grid_env.step([[1,2]]*5)
    output += f"rewards: {rewards}\n"
    output += f"terminated: {terminated}\n"
    output += f"truncated: {truncated}\n"
    output += f"infos: {infos}\n"
    output += f"obs.shape: {obs.shape}\n"

    with open("tests/gold/test_last_action_tracker.txt", "w") as f:
        f.write(output)

if __name__ == "__main__":
    main()
