import
  std/[times, tables, os, strutils, pathnorm, sets, random, algorithm],
  boxy, windy, vmath, silky,
  replays

var dataDir* = "packages/mettagrid/nim/vibescope/data"

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
    showResources* = true
    showHeatmap* = false
    showEventsTimeline* = true
    showStatCharts* = true
    showObservations* = -1
    lockFocus* = false
    aoeEnabledCollectives*: HashSet[int]  ## Set of collective IDs to show AOE for. -1 = unaligned.
    statChartHeight*: float32 = 40.0  ## Height of the stat chart panel.

  PlayMode* = enum
    Historical
    Realtime

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
  bxy*: Boxy
  window*: Window
  frame*: int

  settings* = Settings()
  selection*: Entity

  step*: int = 0
  stepFloat*: float32 = 0
  previousStep*: int = -1
  replay*: Replay
  play*: bool
  playSpeed*: float32 = 10.0
  lastSimTime*: float64 = epochTime()
  playMode* = Historical
  rootArea*: Area

  ## Signals when we want to give control back to Python (DLL mode only).
  requestPython*: bool = false

  # Command line arguments.
  commandLineReplay*: string = ""

  # Popup warning system.
  popupWarning*: string = ""

type
  ActionRequest* = object
    agentId*: int
    actionName*: cstring

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
  ## Cog names: maps agentId -> display name ("First L.") for the current episode.
  cogNames*: Table[int, string]
  ## All loaded names grouped by first letter.
  cogNamesByLetter: Table[char, seq[string]]
  cogNamesLoaded: bool = false

proc loadCogNames*() =
  ## Load cog names from data/cog_names.txt and group by first letter.
  if cogNamesLoaded:
    return
  cogNamesLoaded = true
  cogNamesByLetter = initTable[char, seq[string]]()
  let path = dataDir / "cog_names.txt"
  if not fileExists(path):
    echo "cog_names.txt not found at ", path
    return
  for line in lines(path):
    let trimmed = line.strip()
    if trimmed.len == 0 or trimmed[0] == '#':
      continue
    let parts = trimmed.split(" ", maxsplit = 1)
    if parts.len < 2:
      continue
    let firstName = parts[0]
    let lastName = parts[1]
    let displayName = firstName & " " & lastName[0] & "."
    let letter = firstName[0].toUpperAscii
    if letter notin cogNamesByLetter:
      cogNamesByLetter[letter] = @[]
    cogNamesByLetter[letter].add(displayName)

proc assignCogNames*() =
  ## Assign random cog names to agents. Call once per episode.
  loadCogNames()
  cogNames = initTable[int, string]()
  if replay.isNil or replay.agents.len == 0:
    return
  # Collect available letters sorted.
  var letters: seq[char] = @[]
  for letter in cogNamesByLetter.keys:
    letters.add(letter)
  letters.sort()
  if letters.len == 0:
    return
  # Assign names round-robin through the alphabet.
  let numAgents = replay.agents.len
  for i in 0 ..< numAgents:
    let agent = replay.agents[i]
    let letter = letters[i mod letters.len]
    let names = cogNamesByLetter[letter]
    let name = names[rand(names.len - 1)]
    cogNames[agent.agentId] = name

proc getCogName*(agentId: int): string =
  ## Get the cog name for an agent, or empty string if none assigned.
  ## Lazily assigns names if agents exist but names haven't been assigned yet.
  if cogNames.len == 0 and not replay.isNil and replay.agents.len > 0:
    assignCogNames()
  cogNames.getOrDefault(agentId, "")

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
  let numObjects = replay.objects.len
  for i in 0 ..< numObjects:
    let obj = replay.objects[i]
    if obj.isAgent and obj.agentId == agentId:
      return obj
  raise newException(ValueError, "Agent with ID " & $agentId & " does not exist")

proc getObjectById*(objectId: int): Entity =
  ## Get an object by ID. Asserts the object exists.
  let numObjects = replay.objects.len
  for i in 0 ..< numObjects:
    let obj = replay.objects[i]
    if obj.id == objectId:
      return obj
  raise newException(ValueError, "Object with ID " & $objectId & " does not exist")

proc getObjectAtLocation*(pos: IVec2): Entity =
  ## Get the first object at the given position. Returns nil if no object is there.
  let numObjects = replay.objects.len
  for i in 0 ..< numObjects:
    let obj = replay.objects[i]
    if obj.location.at(step).xy == pos:
      return obj
  return nil

proc configMaxSteps*(): int =
  ## Get the full episode length from config, falling back to replay.maxSteps.
  ## In realtime mode, replay.maxSteps only reflects simulation progress,
  ## but config.game.maxSteps gives the full episode length.
  if replay.config.game.maxSteps > 0:
    return replay.config.game.maxSteps
  return replay.maxSteps

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
