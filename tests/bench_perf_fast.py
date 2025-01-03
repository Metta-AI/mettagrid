import time

import hydra
import numpy as np
from tqdm import tqdm
import pandas as pd

# Add import path
import sys
sys.path.append("/Users/me/p/metta_fast/bindings/generated")
import metta_fast
import ctypes

global actions
global env

def test_performance(env, actions, duration):
    tick = 0
    num_actions = actions.shape[0]
    start = time.time()
    with tqdm(total=duration, desc="Running performance test") as pbar:
        while time.time() - start < duration:
            atns = actions[tick % num_actions]
            #obs, rewards, terminated, truncated, infos = env.step(atns)

            array_pointer = atns.ctypes.data_as(ctypes.POINTER(ctypes.c_byte))
            env.step(array_pointer)
            tick += 1
            if tick % 1000 == 0:
                pbar.update(time.time() - start - pbar.n)

    print(env.get_episode_stats())
    sps = atns.shape[0] * tick / (time.time() - start)
    print(f'SPS: {sps:.2f} {1/sps*1000000:.2f}μs (microseconds)')

actions = {}
env = {}
@hydra.main(version_base=None, config_path="../configs", config_name="a20_40x40")
def main(cfg):
    # Run with c profile
    from cProfile import run
    global env

    cfg.env.game.max_steps = 999999999
    #env = hydra.utils.instantiate(cfg.env, render_mode="human")

    env = metta_fast.Environment()
    env.reset()

    global actions
    num_agents = cfg.env.game.num_agents
    actions = np.random.randint(0, 9, (1024, num_agents, 2), dtype=np.uint32)

    print(env.render())
    test_performance(env, actions, 5)
    #print(env.render())
    exit(0)

    run("test_performance(env, actions, 10)", 'stats.profile')
    import pstats
    from pstats import SortKey
    p = pstats.Stats('stats.profile')
    p.sort_stats(SortKey.TIME).print_stats(25)
    exit(0)


def print_stats(stats):
    # Extract game_stats
    game_stats = stats["game"]

    # Extract agent_stats
    agent_stats = stats["agent"]

    # Calculate total, average, min, and max for each agent stat
    total_agent_stats = {}
    avg_agent_stats = {}
    min_agent_stats = {}
    max_agent_stats = {}
    num_agents = len(agent_stats)

    for agent_stat in agent_stats:
        for key, value in agent_stat.items():
            if key not in total_agent_stats:
                total_agent_stats[key] = 0
                min_agent_stats[key] = float('inf')
                max_agent_stats[key] = float('-inf')
            total_agent_stats[key] += value
            if value < min_agent_stats[key]:
                min_agent_stats[key] = value
            if value > max_agent_stats[key]:
                max_agent_stats[key] = value

    for key, value in total_agent_stats.items():
        avg_agent_stats[key] = value / num_agents

    # Sort the keys alphabetically
    sorted_keys = sorted(total_agent_stats.keys())

    # Create DataFrame for game_stats
    game_stats_df = pd.DataFrame(sorted(game_stats.items()), columns=["Stat", "Value"])

    # Create DataFrame for agent stats
    agent_stats_df = pd.DataFrame({
        "Stat": sorted_keys,
        "Total": [total_agent_stats[key] for key in sorted_keys],
        "Average": [avg_agent_stats[key] for key in sorted_keys],
        "Min": [min_agent_stats[key] for key in sorted_keys],
        "Max": [max_agent_stats[key] for key in sorted_keys]
    })

    # Print the DataFrames
    print("\nGame Stats:")
    print(game_stats_df.to_string(index=False))

    print("\nAgent Stats:")
    print(agent_stats_df.to_string(index=False))


if __name__ == "__main__":
    main()
