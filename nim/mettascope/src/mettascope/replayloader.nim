import
  std/[tables, sets],
  replays, worldmap, common, heatmap, heatmapshader, configs, aoepanel


proc onReplayLoaded*() =
  ## Called when a replay is loaded.
  # Clear cached maps that depend on the old replay
  terrainMap = nil
  visibilityMap = nil
  worldHeatmap = nil
  # Clear AoE tilemaps so they get regenerated for the new replay
  for i in 0 ..< NumCollectives:
    aoeMaps[i] = nil

  # Reset global state for the new replay
  step = 0
  stepFloat = 0.0
  previousStep = -1
  selection = nil
  requestPython = false
  agentPaths = initTable[int, seq[PathAction]]()
  agentObjectives = initTable[int, seq[Objective]]()

  # Enable AoE overlays for collectives 0 and 1 by default
  settings.aoeEnabledCollectives.clear()
  settings.aoeEnabledCollectives.incl(0)
  settings.aoeEnabledCollectives.incl(1)

  # Initialize heatmap for the new replay
  worldHeatmap = newHeatmap(replay)
  worldHeatmap.initialize(replay)
  initHeatmapShader()

  needsInitialFit = true

  let config = loadConfig()
  applyUIState(config)

  echo "Replay loaded: ", replay.fileName
