import
  std/[times, tables, os, pathnorm, sets, strutils, options],
  bumpy, windy, vmath, silky,
  replays

var dataDir* = "packages/mettagrid/nim/mettascope/data"

proc setDataDir*(path: string) =
  ## Set the data directory path. Called from Python bindings with absolute path.
  dataDir = path.normalizePath

type
  IRect* = object
    x*: int32
    y*: int32
    w*: int32
    h*: int32

  AreaLayout* = enum
    Horizontal
    Vertical

  Area* = ref object
    layout*: AreaLayout
    areas*: seq[Area]
    panels*: seq[Panel]
    split*: float32
    selectedPanelNum*: int
    rect*: Rect # Calculated during draw

  PanelDraw* = proc(panel: Panel, frameId: string, contentPos: Vec2, contentSize: Vec2)

  Panel* = ref object
    name*: string
    parentArea*: Area
    draw*: PanelDraw

  Settings* = object
    showFogOfWar* = false
    showVisualRange* = true
    showGrid* = true
    showMask* = true
    showSplats* = true
    showResources* = true
    showHeatmap* = false
    showObservations* = -1
    lockFocus* = false
    hiddenCollectiveAoe*: HashSet[int]  ## Set of collective IDs to hide AoE for. Empty = all shown.

  PlayMode* = enum
    Historical
    Realtime

  GameMode* = enum
    Auto # Auto allows the saved config to override the game mode with the previously used mode.
    Editor
    Game

  Heatmap* = ref object
    ## Tracks agent presence on tiles over time.
    data*: seq[seq[int]] ## data[step][y * width + x] - flattened 2D array
    width*: int
    height*: int
    maxSteps*: int
    maxHeat*: seq[int] ## Cached max heat per step for normalization
    currentTextureStep*: int = -1 ## Track which step's data is in the texture

var
  sk*: Silky
  window*: Window
  frame*: int

  # Transform stack (replaces boxy's transform management).
  transformMat*: Mat3 = mat3()
  transformStack*: seq[Mat3]

  # Fluffy tracing.
  isTracing* = false

proc saveTransform*() =
  ## Push the current transform onto the stack.
  transformStack.add(transformMat)

proc restoreTransform*() =
  ## Pop a transform off the stack.
  transformMat = transformStack.pop()

proc getTransform*(): Mat3 =
  ## Get the current transform.
  transformMat

proc translateTransform*(v: Vec2) =
  ## Translate the current transform.
  transformMat = transformMat * translate(v)

proc scaleTransform*(s: Vec2) =
  ## Scale the current transform.
  transformMat = transformMat * scale(s)

var
  settings* = Settings()
  selected*: Entity
  policyTarget*: Option[IVec2]  ## Target cell from policy_infos to highlight on map.
  activeCollective*: int = 1  ## Currently active faction (0 = Clips, 1 = Cogs). Defaults to Cogs.

  step*: int = 0
  stepFloat*: float32 = 0
  stepFloatSmoothing*: bool = false
  previousStep*: int = -1
  replay*: Replay
  play*: bool
  playSpeed*: float32 = 10.0
  lastSimTime*: float64 = epochTime()
  playMode* = Historical
  gameMode* = Editor
  rootArea*: Area

  ## Signals when we want to give control back to Python (DLL mode only).
  requestPython*: bool = false

  # Command line arguments.
  commandLineReplay*: string = ""
  forcedGameMode*: GameMode = Auto

  # Popup warning system.
  popupWarning*: string = ""


type
  ActionRequest* = object
    agentId*: int
    actionName*: string

  ObjectiveKind* = enum
    Move # Move to a specific position.
    Bump # Bump an object at a specific position to interact with it.
    Vibe # Execute a specific vibe action.

  Objective* = object
    case kind*: ObjectiveKind
    of Move, Bump:
      pos*: IVec2
      approachDir*: IVec2 ## Direction to approach from for Bump actions (e.g., ivec2(-1, 0) means approach from the left).
    of Vibe:
      vibeActionId*: int
    repeat*: bool ## If true, this objective will be re-queued at the end when completed.

  PathAction* = object
    case kind*: ObjectiveKind
    of Move:
      pos*: IVec2 ## Target position for move.
    of Bump:
      bumpPos*: IVec2 ## Bump target position.
      bumpDir*: IVec2 ## Direction to bump for bump actions.
    of Vibe:
      vibeActionId*: int

var
  requestActions*: seq[ActionRequest]

var
  ## Path queue for each agent. Maps agentId to a sequence of path actions.
  agentPaths* = initTable[int, seq[PathAction]]()
  ## Objective queue for each agent. Maps agentId to a sequence of objectives.
  agentObjectives* = initTable[int, seq[Objective]]()
  ## Track mouse down position to distinguish clicks from drags.
  mouseDownPos*: Vec2

proc at*[T](sequence: seq[T], step: int): T =
  ## Get the value at the given step.
  if sequence.len == 0:
    return default(T)
  sequence[step.clamp(0, sequence.len - 1)]

proc at*[T](sequence: seq[T]): T =
  ## Get the value at the current step.
  sequence.at(step)

proc irect*(x, y, w, h: SomeNumber): IRect =
  IRect(x: x.int32, y: y.int32, w: w.int32, h: h.int32)

proc rect*(rect: IRect): Rect =
  Rect(
    x: rect.x.float32,
    y: rect.y.float32,
    w: rect.w.float32,
    h: rect.h.float32
  )

proc xy*(rect: IRect): IVec2 =
  ivec2(rect.x, rect.y)

proc wh*(rect: IRect): IVec2 =
  ivec2(rect.w, rect.h)

proc getAgentById*(agentId: int): Entity =
  ## Get an agent by ID. Asserts the agent exists.
  for obj in replay.objects:
    if obj.isAgent and obj.agentId == agentId:
      return obj
  raise newException(ValueError, "Agent with ID " & $agentId & " does not exist")

proc getObjectById*(objectId: int): Entity =
  ## Get an object by ID. Asserts the object exists.
  for obj in replay.objects:
    if obj.id == objectId:
      return obj
  raise newException(ValueError, "Object with ID " & $objectId & " does not exist")

proc getObjectAtLocation*(pos: IVec2): Entity =
  ## Get the first object at the given position. Returns nil if no object is there.
  for obj in replay.objects:
    if obj.location.at(step).xy == pos:
      return obj
  return nil

proc getVibeName*(vibeId: int): string =
  if vibeId >= 0 and vibeId < replay.config.game.vibeNames.len:
    result = replay.config.game.vibeNames[vibeId]
  else:
    raise newException(ValueError, "Vibe with ID " & $vibeId & " does not exist")

proc getPanelByName*(area: Area, name: string): Panel =
  ## Get a panel by name from the given area and its subareas. Returns nil if not found.
  for panel in area.panels:
    if panel.name == name:
      return panel
  for subarea in area.areas:
    let panel = getPanelByName(subarea, name)
    if panel != nil:
      return panel
  return nil

proc stripSuffix*(s: var string, suffix: string) =
  ## Strip a suffix from a string.
  if s.endsWith(suffix):
    s = s[0 ..< (s.len - suffix.len)]
proc stripTeamSuffix*(typeName: string): string =
  ## Strip team suffix like _0, _1 from type name.
  result = typeName
  if result.len >= 2 and result[^2] == '_' and result[^1] in {'0'..'9'}:
    result = typeName[0..^3]
  result.stripSuffix("_station")

proc stripTeamPrefix*(typeName: string): string =
  ## Strip team prefix in "XX:" format (e.g., "c:hub" → "hub", "cg:miner" → "miner").
  ## Also handles legacy "cogs_green_" style prefixes.
  let colonIdx = typeName.find(':')
  if colonIdx >= 0 and colonIdx < typeName.len - 1:
    return typeName[colonIdx + 1 .. ^1]
  const teamPrefixes = ["cogs_green_", "cogs_blue_", "cogs_red_", "cogs_yellow_", "clips_"]
  for prefix in teamPrefixes:
    if typeName.len > prefix.len and typeName[0 ..< prefix.len] == prefix:
      return typeName[prefix.len .. ^1]
  return typeName

proc normalizeTypeName*(typeName: string): string =
  ## Normalize a type name by stripping team prefixes and suffixes.
  ## Handles formats like "c:hub", "cogs_green_hub", "hub_0", etc.
  result = stripTeamPrefix(typeName)
  result = stripTeamSuffix(result)
