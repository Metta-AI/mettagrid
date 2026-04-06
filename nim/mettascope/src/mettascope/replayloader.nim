import
  std/[tables, strutils],
  windy,
  replays, common, configs, talk,
  gamemode/[team, worldmap, camera, pipegrid],
  panelmode/[objectpanel, monologuepanel]


proc onReplayLoaded*() =
  ## Called when a replay is loaded.
  # Clear cached maps that depend on the old replay
  resetTerrainCaches()
  resetPipegridState()
  visibilityMap = nil
  visibilityMapStep = -1
  visibilityMapSelectionId = -1
  explorationFogMap = nil
  explorationFogMapStep = -1
  explorationFogMapSelectionId = -1
  worldHeatmap = nil
  # Clear AoE tilemaps so they get regenerated for the new replay
  aoeMaps = @[]
  aoeMapStep = -1

  # Reset global state for the new replay
  step = 0
  stepFloat = 0.0
  stepFloatSmoothing = false
  previousStep = -1
  selected = nil
  lastSelectedTeam = -1
  requestPython = false
  agentPaths = initTable[int, seq[PathAction]]()
  agentObjectives = initTable[int, seq[Objective]]()
  clearTalkCompose()
  resetMonologueCaches()

  needsInitialFit = true
  replay.discoverTeams()

  let config = loadConfig()
  applyUIState(config)
  if selected != nil:
    # Route restored selection through selectObject so team tracking is consistent.
    selectObject(selected)
  if lastSelectedTeam < 0:
    # Auto-select the first cogs team if no team is selected.
    for i, info in replay.teams:
      if info.name.startsWith("cogs"):
        lastSelectedTeam = i
        break
  rebuildSplats()

  # Update zoom info rect based on game mode (same logic as switchGameMode)
  if gameMode == Game:
    worldMapZoomInfo.rect = irect(0, 0, window.size.x.int32, window.size.y.int32)
    worldMapZoomInfo.scrollArea = rect(irect(0, 0, window.size.x.int32, window.size.y.int32))
    previousPanelSize = vec2(window.size.x.float32, window.size.y.float32)
    worldMapZoomInfo.hasMouse = true
  else: # Editor mode
    # Panel drawing will update rect/scrollArea, but we reset hasMouse
    worldMapZoomInfo.hasMouse = false

  updateMinZoom(worldMapZoomInfo)
  echo "Replay loaded: ", replay.fileName
