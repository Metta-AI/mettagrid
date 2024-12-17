import hydra
import numpy as np
import mettagrid
import mettagrid.mettagrid_env

@hydra.main(version_base=None, config_path="../configs", config_name="test_basic")
def main(cfg):
    print("Basic level:")
    print("cfg.last_action", cfg)
    cfg.last_action = True
    metta_grid_env = mettagrid.mettagrid_env.MettaGridEnv(render_mode=None, **cfg)
    print(metta_grid_env._c_env.render())

    (obs, rewards, terminated, truncated, infos) = metta_grid_env.step([[1,2]]*5)
    for agentId in range(metta_grid_env._c_env.num_agents()):
        print("agentId:", agentId)
        for feature_id, feature in enumerate(obs[agentId]):
            try:
                feature_name = metta_grid_env.grid_features[feature_id]
            except IndexError:
                feature_name = "???"
            print("  Feature:", feature_id, ":", feature_name)
            print(feature)
    print("rewards:", rewards)
    print("terminated:", terminated)
    print("truncated:", truncated)
    print("infos:", infos)
    print("obs.shape:", obs.shape)

if __name__ == "__main__":
    main()
