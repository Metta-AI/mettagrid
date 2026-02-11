import
  std/[tables, sets],
  windy,
  replays, worldmap, common, configs, panels


proc onReplayLoaded*() =
  ## Called when a replay is loaded.
  # Clear cached maps that depend on the old replay
  terrainMap = nil
  visibilityMap = nil
  worldHeatmap = nil
  # Clear AoE tilemaps so they get regenerated for the new replay
  aoeMaps = @[]
  aoeMapStep = -1
  aoeMapHiddenCollectives.clear()

  # Reset global state for the new replay
  step = 0
  stepFloat = 0.0
  previousStep = -1
  selection = nil
  requestPython = false
  agentPaths = initTable[int, seq[PathAction]]()
  agentObjectives = initTable[int, seq[Objective]]()

  needsInitialFit = true

  let config = loadConfig()
  applyUIState(config)

  # Update zoom info rect based on game mode (same logic as switchGameMode)
  if gameMode == Game:
    worldMapZoomInfo.rect = irect(0, 0, window.size.x.int32, window.size.y.int32)
    worldMapZoomInfo.scrollArea = rect(irect(0, 0, window.size.x.int32, window.size.y.int32))
    worldMapZoomInfo.hasMouse = true
  else: # Editor mode
    # Panel drawing will update rect/scrollArea, but we reset hasMouse
    worldMapZoomInfo.hasMouse = false

  echo "Replay loaded: ", replay.fileName
