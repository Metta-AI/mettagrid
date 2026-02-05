## Episode infos panel - displays game stats, agent stats, attributes, and rewards.

import
  std/[json, tables, strformat, algorithm],
  vmath, silky,
  common, panels, replays

proc drawInfosPanel*(panel: panels.Panel, frameId: string, contentPos: Vec2, contentSize: Vec2) =
  ## Draws the episode infos panel.
  frame(frameId, contentPos, contentSize):
    sk.at += vec2(8, 8)

    if replay.isNil:
      text("No replay loaded")
      return

    if replay.infos.isNil or replay.infos.kind != JObject:
      text("No infos available")
      text("(Replay may be an older version)")
      return

    let infos = replay.infos

    # Attributes section
    if "attributes" in infos and infos["attributes"].kind == JObject:
      h1text("Attributes")
      let attrs = infos["attributes"]
      if "seed" in attrs:
        text(&"  Seed: {attrs[\"seed\"].getInt}")
      if "map_w" in attrs and "map_h" in attrs:
        text(&"  Map size: {attrs[\"map_w\"].getInt} x {attrs[\"map_h\"].getInt}")
      if "steps" in attrs:
        text(&"  Steps: {attrs[\"steps\"].getInt}")
      if "max_steps" in attrs:
        text(&"  Max steps: {attrs[\"max_steps\"].getInt}")
      sk.advance(vec2(0, sk.theme.spacing.float32))

    # Game stats section
    if "game" in infos and infos["game"].kind == JObject:
      let gameStats = infos["game"]
      if gameStats.len > 0:
        h1text("Game Stats")
        var keys: seq[string] = @[]
        for key, _ in gameStats.pairs:
          keys.add(key)
        keys.sort()
        for key in keys:
          let value = gameStats[key]
          if value.kind == JFloat:
            text(&"  {key}: {value.getFloat:.2f}")
          elif value.kind == JInt:
            text(&"  {key}: {value.getInt}")
          else:
            text(&"  {key}: {value}")
        sk.advance(vec2(0, sk.theme.spacing.float32))

    # Agent stats section (averaged)
    if "agent" in infos and infos["agent"].kind == JObject:
      let agentStats = infos["agent"]
      if agentStats.len > 0:
        h1text("Agent Stats (avg)")
        var keys: seq[string] = @[]
        for key, _ in agentStats.pairs:
          keys.add(key)
        keys.sort()
        for key in keys:
          let value = agentStats[key]
          if value.kind == JFloat:
            text(&"  {key}: {value.getFloat:.2f}")
          elif value.kind == JInt:
            text(&"  {key}: {value.getInt}")
          else:
            text(&"  {key}: {value}")
        sk.advance(vec2(0, sk.theme.spacing.float32))

    # Collective stats section
    if "collective" in infos and infos["collective"].kind == JObject:
      let collectiveStats = infos["collective"]
      if collectiveStats.len > 0:
        h1text("Collective Stats")
        for collectiveName, stats in collectiveStats.pairs:
          text(&"  {collectiveName}:")
          if stats.kind == JObject:
            var keys: seq[string] = @[]
            for key, _ in stats.pairs:
              keys.add(key)
            keys.sort()
            for key in keys:
              let value = stats[key]
              if value.kind == JFloat:
                text(&"    {key}: {value.getFloat:.2f}")
              elif value.kind == JInt:
                text(&"    {key}: {value.getInt}")
              else:
                text(&"    {key}: {value}")
        sk.advance(vec2(0, sk.theme.spacing.float32))

    # Episode rewards section
    if "episode_rewards" in infos and infos["episode_rewards"].kind == JArray:
      let rewards = infos["episode_rewards"]
      if rewards.len > 0:
        h1text("Episode Rewards")
        var totalReward = 0.0
        for i, reward in rewards.pairs:
          let r = if reward.kind == JFloat: reward.getFloat
                  elif reward.kind == JInt: reward.getInt.float
                  else: 0.0
          totalReward += r
          text(&"  Agent {i}: {r:.2f}")
        text(&"  Total: {totalReward:.2f}")
        text(&"  Average: {totalReward / rewards.len.float:.2f}")
