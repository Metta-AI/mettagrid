import hydra
import numpy as np
from mettagrid.mettagrid_c import MettaGrid
from omegaconf import OmegaConf

map = np.array([
  ["A", "a", "A"],
  [" ", " ", " "],
  ["A", " ", "A"]
])
cfg = OmegaConf.load('configs/test_basic.yaml')

cfg.game.map.room.num_agents = 4
cfg.game.map.room.width = 3
cfg.game.map.room.height = 3
cfg.game.map.room.objects.agent = 4
cfg.game.map.room.objects.altar = 1
cfg.game.map.room.objects.generator = 0
cfg.game.map.room.objects.converter = 0
cfg.game.kinship.enabled = True
cfg.game.kinship.observed = True
cfg.game.kinship.team_size = 2
cfg.game.kinship.team_reward = 1.0

cfg.game.num_agents = cfg.game.map.room.num_agents

metta_grid = MettaGrid(cfg, map)
metta_grid.reset()

actions = np.array([
  [0, 0],
  [0, 0],
  [0, 0],
  [0, 0]
], dtype=np.int32)
(obs, rewards, terms, truncs, infos) = metta_grid.step(actions)
assert str(rewards) == "[0. 0. 0. 0.]"


def test_shared_rewards(msg, rewards, expected, team_reward):
  cfg.game.kinship.team_reward = team_reward
  metta_grid = MettaGrid(cfg, map)
  metta_grid.reset()
  rewards = np.array(rewards, dtype=np.float32)
  expected = np.array(expected, dtype=np.float32)
  metta_grid._compute_shared_rewards(rewards)
  if str(rewards) != str(expected):
    print("msg:", msg)
    print("  team_reward:", team_reward)
    print("  expected:", expected)
    print("  got:     ", rewards)
    assert False

test_shared_rewards(
  msg = "0 rewards",
  rewards = [0, 0, 0, 0],
  expected = [0, 0, 0, 0],
  team_reward = 1.0
)

test_shared_rewards(
  msg = "1 reward",
  rewards = [1, 0, 0, 0],
  expected = [0.5, 0.5, 0, 0],
  team_reward = 1.0
)

test_shared_rewards(
  msg = "1 reward on other team",
  rewards = [0, 0, 1, 0],
  expected = [0, 0, 0.5, 0.5],
  team_reward = 1.0
)

test_shared_rewards(
  msg = "4 rewards",
  rewards = [1, 1, 1, 1],
  expected = [1, 1, 1, 1],
  team_reward = 1.0
)

test_shared_rewards(
  msg = "1 reward split 50%",
  rewards = [1, 0, 0, 0],
  expected = [.75, .25, 0, 0],
  team_reward = 0.5
)

test_shared_rewards(
  msg = "1 reward split 1/3%",
  rewards = [1, 0, 0, 0],
  expected = [0.8333334, 0.16666667, 0, 0],
  team_reward = 1/3
)

test_shared_rewards(
  msg = "2 rewards split 50%",
  rewards = [1, 1, 0, 0],
  expected = [1, 1, 0, 0],
  team_reward = 0.5
)

test_shared_rewards(
  msg = "1 rewards no split",
  rewards = [1, 0, 0, 0],
  expected = [1, 0, 0, 0],
  team_reward = 0.0
)
