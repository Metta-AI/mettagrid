import
  std/[strutils, sets],
  windy, jsony,
  common, collectives

type
  SettingsConfig* = object
    showFogOfWar*: bool
    showVisualRange*: bool
    showGrid*: bool
    showResources*: bool
    showObservations*: int
    lockFocus*: bool
    showHeatmap*: bool
    hiddenCollectiveAoeNames*: seq[string]

  AreaLayoutConfig* = object
    layout*: AreaLayout
    split*: float32
    areas*: seq[AreaLayoutConfig]
    panelNames*: seq[string]
    selectedPanelNum*: int

  MettascopeConfig* = object
    windowWidth*: int32
    windowHeight*: int32
    panelLayout*: AreaLayoutConfig
    playSpeed*: float32
    settings*: SettingsConfig
    selectedAgentId*: int
    gameMode*: GameMode

const DefaultConfig* = MettascopeConfig(
  windowWidth: 1200,
  windowHeight: 800,
  playSpeed: 10.0,
  settings: SettingsConfig(
    showFogOfWar: false,
    showVisualRange: true,
    showGrid: true,
    showResources: true,
    showObservations: -1,
    lockFocus: false,
    showHeatmap: false
  ),
  selectedAgentId: -1,
  gameMode: Editor
)

proc serializeArea*(area: Area): AreaLayoutConfig =
  ## Convert an Area tree to a serializable config format.
  result.layout = area.layout
  result.split = area.split
  result.selectedPanelNum = area.selectedPanelNum

  for panel in area.panels:
    result.panelNames.add(panel.name)

  for subArea in area.areas:
    result.areas.add(serializeArea(subArea))

proc deserializeArea*(config: AreaLayoutConfig, referenceArea: Area): Area =
  ## Rebuild an Area tree from a config format.
  result = Area()
  result.selectedPanelNum = config.selectedPanelNum

  for name in config.panelNames:
    let referencePanel = getPanelByName(referenceArea, name)
    if referencePanel != nil:
      let panel = Panel(name: name, parentArea: result, draw: referencePanel.draw)
      result.panels.add(panel)

  for subConfig in config.areas:
    let subArea = deserializeArea(subConfig, referenceArea)
    result.areas.add(subArea)

  if result.panels.len > 0 and result.areas.len > 0:
    raise newException(ValueError, "Area cannot have both panels and child areas")

  # Silky requires only 2 children per area.
  if result.areas.len > 0:
    if result.areas.len != 2:
      raise newException(ValueError, "Area with child areas must have exactly 2 children, got " & $result.areas.len)
    result.layout = config.layout
    result.split = clamp(config.split, 0.1, 0.9)

proc validateAreaStructure*(area: Area, isRoot: bool = true): bool =
  ## Validate that an Area tree has correct structure.
  ## Returns true if valid, false otherwise.
  if area.isNil:
    return false

  if isRoot:
    if area.areas.len == 0:
      return false
    if area.panels.len > 0:
      return false

  if area.panels.len > 0 and area.areas.len > 0:
    return false

  # Areas with child areas must have exactly 2 children
  if area.areas.len > 0:
    if area.areas.len != 2:
      return false
    # Validate child areas recursively
    for subArea in area.areas:
      if not validateAreaStructure(subArea, false):
        return false
    return true

  if area.panels.len > 0:
    return true

  return false

proc saveConfig*(config: MettascopeConfig) =
  ## Saves config to file.
  setConfig("mettascope", "config.json", config.toJson())

proc loadConfig*(): MettascopeConfig =
  ## Loads config from file, creates default config if file doesn't exist or parsing fails.
  let jsonStr = getConfig("mettascope", "config.json")
  if jsonStr != "":
    try:
      result = jsonStr.fromJson(MettascopeConfig)
    except:
      echo "Failed to parse config file, using default config: ", getCurrentExceptionMsg()
      result = DefaultConfig
      saveConfig(result)
  else:
    result = DefaultConfig
    saveConfig(result)

proc applyUIState*(config: MettascopeConfig) =
  ## Apply the loaded UI state from config to global variables.
  playSpeed = config.playSpeed

  # Allow the CLI to force a game mode, otherwise use the config's last used mode.
  if forcedGameMode != Auto:
    gameMode = forcedGameMode
  else:
    if config.gameMode == Auto:
      gameMode = Editor
    else:
      gameMode = config.gameMode

  settings.showFogOfWar = config.settings.showFogOfWar
  settings.showVisualRange = config.settings.showVisualRange
  settings.showGrid = config.settings.showGrid
  settings.showResources = config.settings.showResources
  settings.showObservations = config.settings.showObservations
  settings.lockFocus = config.settings.lockFocus
  settings.showHeatmap = config.settings.showHeatmap
  # Rebuild hiddenCollectiveAoe IDs from saved names.
  # ["cogs", "clips"] -> [0, 1]
  settings.hiddenCollectiveAoe.clear()
  let numCollectives = getNumCollectives()
  for name in config.settings.hiddenCollectiveAoeNames:
    for i in 0 ..< numCollectives:
      if getCollectiveName(i) == name:
        settings.hiddenCollectiveAoe.incl(i)
        break
  if replay != nil and config.selectedAgentId >= 0 and config.selectedAgentId < replay.agents.len:
    selected = replay.agents[config.selectedAgentId]

proc saveUIState*() =
  ## Save the current UI state to config.
  var config = loadConfig()
  config.playSpeed = playSpeed
  if gameMode == Auto:
    config.gameMode = Editor
  else:
    config.gameMode = gameMode
  config.settings.showFogOfWar = settings.showFogOfWar
  config.settings.showVisualRange = settings.showVisualRange
  config.settings.showGrid = settings.showGrid
  config.settings.showResources = settings.showResources
  config.settings.showObservations = settings.showObservations
  config.settings.lockFocus = settings.lockFocus
  config.settings.showHeatmap = settings.showHeatmap
  # Save hiddenCollectiveAoe as names so they survive ID changes across replays.
  # [0, 1] -> ["cogs", "clips"]
  config.settings.hiddenCollectiveAoeNames = @[]
  let numCollectives = getNumCollectives()
  for id in settings.hiddenCollectiveAoe:
    if id >= 0 and id < numCollectives:
      let name = getCollectiveName(id)
      if name.len > 0:
        config.settings.hiddenCollectiveAoeNames.add(name)
  if selected != nil and selected.isAgent:
    config.selectedAgentId = selected.agentId
  saveConfig(config)

proc savePanelLayout*() =
  ## Save the current panel layout to config.
  var config = loadConfig()
  config.panelLayout = serializeArea(rootArea)
  saveConfig(config)
