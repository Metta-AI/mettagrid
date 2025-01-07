import hydra
import numpy as np
import mettagrid
import mettagrid.mettagrid_env

def dump_agents(env):
  output = ""
  for thing in env.grid_objects.values():
      if thing["type"] == 0: # agent
        output += (
          "Agent id=" + str(thing["id"]) +
          " agent_id=" + str(thing["agent_id"]) +
          " x=" + str(thing["c"]) +
          " y=" + str(thing["r"]) +
          " energy=" + str(thing["agent:energy"]) +
          " shield=" + str(thing["agent:shield"]) +
          " inventory=" + str(thing["agent:inv:r1"]) +
          "\n"
        )

  return output

def dump_map(env):
  output = ""
  for thing in env.grid_objects.values():
      if thing["type"] == 0: # agent
        output += "Agent " + str(thing["id"]) + " " + str(thing["agent_id"]) + " " + str(thing["c"]) + " " + str(thing["r"]) + "\n"
      elif thing["type"] == 1: # wall
        output += "Wall " + str(thing["id"]) + " " + str(thing["c"]) + " " + str(thing["r"]) + "\n"
      elif thing["type"] == 2: # generator
        output += "Generator " + str(thing["id"]) + " " + str(thing["c"]) + " " + str(thing["r"]) + "\n"
      elif thing["type"] == 3: # converter
        output += "Converter " + str(thing["id"]) + " " + str(thing["c"]) + " " + str(thing["r"]) + "\n"
      elif thing["type"] == 4: # altar
        output += "Altar " + str(thing["id"]) + " " + str(thing["c"]) + " " + str(thing["r"]) + "\n"
  return output

def render_to_string(env):
    """ Render the environment to a string """
    output = ""
    for x in range(env.map_width):
      for y in range(env.map_height):
        cell = " "
        for thing in env.grid_objects.values():
          if thing["r"] == x and thing["c"] == y:
            if thing["type"] == 0: # agent
              cell = "A"
            elif thing["type"] == 1: # wall
              cell = "#"
            elif thing["type"] == 2: # generator
              cell = "g"
            elif thing["type"] == 3: # converter
              cell = "c"
            elif thing["type"] == 4: # altar
              cell = "a"
            break
        output += cell
      output += "\n"
    return output

def render_obs_to_string(env, obs, match=None):
  output = ""
  for agentId in range(env._c_env.num_agents()):
      output += "Agent: " + str(agentId) + "\n"
      for feature_id, feature in enumerate(obs[agentId]):
          try:
              feature_name = env.grid_features[feature_id]
          except IndexError:
              feature_name = "???"
          if match is None or match in feature_name:
            output += "Feature " + feature_name + ' ' + str(feature_id) + '\n'
            for x in range(11):
              for y in range(11):
                output += f"{feature[x,y]:4d}"
              output += '\n'
  return output

def header(message):
  return "=" * 80 + "\n" + message + "\n" + "=" * 80 + "\n"

@hydra.main(version_base=None, config_path="../configs", config_name="test_basic")
def main(cfg):
    output = ""

    output += header("Basic level:")
    np.random.seed(123)
    env = mettagrid.mettagrid_env.MettaGridEnv(render_mode=None, **cfg)
    env.reset()

    r = 0
    actions = np.zeros((env.num_agents, 2), dtype=np.uint8)

    output += dump_map(env)

    for i in range(10):
      for agentId in range(env.num_agents):
        actions[agentId][0] = r % 9
        r += 1
        actions[agentId][1] = r % 9
        r += 1

      output += header(f"Step {i}")
      output += render_to_string(env)

      output += header("Actions:")
      for agentId in range(env.num_agents):
        output += f"Agent {agentId}: {actions[agentId][0]} {actions[agentId][1]}\n"

      (obs, rewards, terminated, truncated, infos) = env.step(actions)

      output += header("Agents:")
      output += dump_agents(env)
      output += header("Observations:")
      output += render_obs_to_string(env, obs)

      with open("tests/gold/test_env.txt", "w") as f:
        f.write(output)

if __name__ == "__main__":
    main()
