import hydra
import numpy as np
import mettagrid
import mettagrid.mettagrid_env

@hydra.main(version_base=None, config_path="../configs", config_name="test_basic")
def main(cfg):

    print("Basic level:")
    print("cfg.enable_last_action", cfg)
    cfg.enable_last_action = True
    metta_grid_env = mettagrid.mettagrid_env.MettaGridEnv(render_mode=None, **cfg)
    print(metta_grid_env._c_env.render())

    (obs, rewards, terminated, truncated, infos) = metta_grid_env.step([[0,0]]*5)
    print("obs:", obs)
    for agentId in range(metta_grid_env._c_env.num_agents()):
        print("agentId:", agentId)
        for feature_id, feature in enumerate(obs[agentId]):
            feature_name = metta_grid_env.grid_features[feature_id]
            print("  Feature:", feature_name, feature)
    print("rewards:", rewards)
    print("terminated:", terminated)
    print("truncated:", truncated)
    print("infos:", infos)


if __name__ == "__main__":
    main()
