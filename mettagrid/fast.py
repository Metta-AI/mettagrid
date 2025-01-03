# Add import path
import sys
from ctypes import *
import ctypes
import json
import os
from omegaconf import OmegaConf
import gym
import numpy as np
from pufferlib import PufferEnv

# sys.path.append("/Users/me/p/metta_fast/bindings/generated")
# from metta_fast import *

class CEnvironment:
  def __init__(self, env):
    self.env = env

  def action_names(self):
    return self.env.action_names()

class Environment(PufferEnv):
  # Wrapper around the Nim Environment.

  emulated = False

  def __init__(self, cfg):

    # public private API
    self._env_cfg = cfg
    self._c_env = CEnvironment(self)


    cfg_dict = OmegaConf.to_container(cfg, resolve=True)

    print(json.dumps(cfg_dict, indent=2))

    # Write config to file.
    path = "/Users/me/p/metta_fast/config3.json"
    print(path)
    with open(path, "w") as f:
      json.dump(cfg_dict, f, indent=2)
    # Compile the binary file.
    # set cwd to the directory of the file.
    currentDir = os.getcwd()
    os.chdir("/Users/me/p/metta_fast")
    cmd = "/Users/me/.nimble/bin/nim c -r -d:danger -o:bindings/generated/libmetta_fast.dylib bindings/bindings.nim"
    print(cmd)
    if os.system(cmd) != 0:
      raise Exception("Failed to compile Nim bindings.")

    os.chdir(currentDir)

    # Load the binary file.
    self.dll = cdll.LoadLibrary("/Users/me/p/metta_fast/bindings/generated/libmetta_fast.dylib")

    self.dll.metta_fast_new_environment.argtypes = []
    self.dll.metta_fast_new_environment.restype = c_ulonglong

    self.dll.metta_fast_environment_step.argtypes = [c_ulonglong, c_void_p]
    self.dll.metta_fast_environment_step.restype = None

    self.dll.metta_fast_environment_get_observation.argtypes = [c_ulonglong]
    self.dll.metta_fast_environment_get_observation.restype = c_void_p

    self.dll.metta_fast_environment_render.argtypes = [c_ulonglong]
    self.dll.metta_fast_environment_render.restype = c_char_p

    self.dll.metta_fast_environment_reset.argtypes = [c_ulonglong]
    self.dll.metta_fast_environment_reset.restype = None

    self.dll.metta_fast_environment_num_agents.argtypes = [c_ulonglong]
    self.dll.metta_fast_environment_num_agents.restype = c_ulonglong

    self.dll.metta_fast_environment_map_width.argtypes = [c_ulonglong]
    self.dll.metta_fast_environment_map_width.restype = c_ulonglong

    self.dll.metta_fast_environment_map_height.argtypes = [c_ulonglong]
    self.dll.metta_fast_environment_map_height.restype = c_ulonglong

    self.env = self.dll.metta_fast_new_environment()
    print("Created environment: ", self.env)

  def get_observation(self):
    print("get_observation")
    ptr = self.dll.metta_fast_environment_get_observation(self.env)
    buffer_length = (self.num_agents * 24 * 11 * 11)

    # Create a ctypes array from the pointer
    array_type = ctypes.c_uint8 * buffer_length
    buffer = array_type.from_address(ptr)

    data = np.frombuffer(buffer, dtype=np.uint8, count=buffer_length)
    reshaped_data = data.reshape((self.num_agents, 24, 11, 11))
    print(reshaped_data)
    return reshaped_data

  def reset(self):
    print("reset")
    self.dll.metta_fast_environment_reset(self.env)

    obs = self.get_observation()
    infos = None

    return (obs, infos)

  def step(self, actions):
    print("step")
    array_pointer = actions.ctypes.data_as(ctypes.POINTER(ctypes.c_byte))
    self.dll.metta_fast_environment_step(self.env, array_pointer)

    obs = self.get_observation()
    rewards = None
    terminated = None
    truncated = None
    infos = None

    return (obs, rewards, terminated, truncated, infos)

  def render(self):
    print("render")
    render_str = self.dll.metta_fast_environment_render(self.env).decode("utf8")
    print(render_str)

  def get_episode_stats(self):
    print("get_episode_stats")
    return {
      'game': {},
      'agent': {}
    }

  @property
  def observation_space(self):
    print("observation_space")
    return gym.spaces.Box(low=0, high=255, shape=(24, 11, 11), dtype=np.uint8)

  @property
  def single_observation_space(self):
    print("single_observation_space")
    return self.observation_space

  @property
  def action_space(self):
    print("action_space")
    return gym.spaces.MultiDiscrete((8, 9), dtype=np.uint32)

  @property
  def single_action_space(self):
    print("single_action_space")
    return self.action_space

  def action_names(self):
    return ['noop', 'move', 'rotate', 'use', 'attack', 'shield', 'swap']

  @property
  def num_agents(self):
    print("num_agents(", self.env, ")")
    n = self.dll.metta_fast_environment_num_agents(self.env)
    print("after num_agents: ", n)
    return n

  def map_width(self):
    print("map_width")
    return self.dll.metta_fast_environment_map_width(self.env)

  def map_height(self):
    print("map_height")
    return self.dll.metta_fast_environment_map_height(self.env)
