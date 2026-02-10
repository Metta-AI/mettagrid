import
  vmath,
  replays, common

proc newHeatmap*(replay: Replay): Heatmap =
  ## Create a new heatmap for the given replay.
  ## Data is generated lazily via update.
  result = Heatmap()
  result.width = replay.mapSize[0]
  result.height = replay.mapSize[1]
  result.maxSteps = 0
  result.maxHeat = @[]
  result.data = @[]
  result.currentTextureStep = -1

proc update*(heatmap: Heatmap, step: int, replay: Replay) =
  ## Extend generated heatmap data up to and including `step`.
  if step < 0 or step < heatmap.maxSteps:
    return
  if replay.maxSteps <= 0:
    return

  let
    targetStep = min(step, replay.maxSteps - 1)
    mapArea = heatmap.width * heatmap.height
  if targetStep < heatmap.maxSteps:
    return

  for target in heatmap.maxSteps .. targetStep:
    heatmap.data.add(newSeq[int](mapArea))
    heatmap.maxHeat.add(0)

    # Copy previous cumulative data.
    if target > 0:
      for i in 0 ..< mapArea:
        heatmap.data[target][i] = heatmap.data[target - 1][i]

    # Add heat for this step.
    if target == 0:
      for agent in replay.agents:
        let
          currentLocation = agent.location.at(0)
          x = currentLocation.x.int
          y = currentLocation.y.int
        if x >= 0 and x < heatmap.width and y >= 0 and y < heatmap.height:
          heatmap.data[target][y * heatmap.width + x] += 1
    else:
      for agent in replay.agents:
        let currentLocation = agent.location.at(target)
        if agent.location.at(target - 1) == currentLocation:
          continue
        let
          x = currentLocation.x.int
          y = currentLocation.y.int
        if x >= 0 and x < heatmap.width and y >= 0 and y < heatmap.height:
          heatmap.data[target][y * heatmap.width + x] += 1

    var maxHeat = 0
    for heat in heatmap.data[target]:
      if heat > maxHeat:
        maxHeat = heat
    heatmap.maxHeat[target] = maxHeat

  heatmap.maxSteps = targetStep + 1

proc initialize*(heatmap: Heatmap, replay: Replay) =
  ## Initialize the heatmap for all replay steps.
  if replay.maxSteps <= 0:
    return
  heatmap.update(replay.maxSteps - 1, replay)

proc getHeat*(heatmap: Heatmap, step: int, x: int, y: int): int =
  ## Get the heat value at the given position and step.
  if step < 0 or step >= heatmap.maxSteps or x < 0 or x >= heatmap.width or y < 0 or y >= heatmap.height:
    return 0
  heatmap.data[step][y * heatmap.width + x]

proc getMaxHeat*(heatmap: Heatmap, step: int): int =
  ## Get the maximum heat value for the given step.
  if step < 0 or step >= heatmap.maxSteps:
    return 0
  heatmap.maxHeat[step]
