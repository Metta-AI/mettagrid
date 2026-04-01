import
  std/[algorithm, math, os, tables, options, sets],
  chroma, vmath, windy, silky,
  ../[common, actions, replays, colors],
  ./[team, pathfinding, tilemap, pixelator, shaderquad, terrains,
    heatmap, heatmapshader, pipegrid, starfield, custom_hud, camera],
  ../panelmode/objectpanel

const
  TileSize = 128
  TurnTransitionHalf = 0.20f        # Diagonal shown for ±20% around step boundary.
  TurnDisableSpeed = 50.0f          # Skip diagonal/rounding above this playback speed.
  CornerRoundingTension = 0.5f      # Catmull-Rom tension (0.5 = standard, higher = more curve).
  Ts = 1.0 / TileSize.float32 # Tile scale.
  MiniTileSize = 16
  Mts = 1.0 / MiniTileSize.float32 # Mini tile scale for minimap.
  MiniViewZoomThreshold = 4.25f # Show mini/pip overlays at a less zoomed-out level.
  FollowMarginScreenFraction = 0.2f # Keep selected agent within 1/5 of screen edges.
  FollowMarginMaxWorldTiles = 5.0f # Cap edge margin to 5 world tiles when zoomed out.
  ZoomOutMargin = 1.5f # Panel may show at most this multiple of the map's linear extent when zoomed out.
  SelectionRadiusPixels = 100.0f # Screen-space click radius for selecting nearby objects.
  BumpDepthTiles = 0.18f # Maximum agent offset during a bump, in tiles.
  BumpActiveFraction = 0.35f # Fraction of the step used by the bump animation.
  BumpDisableSpeed = 16.0f # Disable bump animation above this playback speed.

var
  visibilityMapStep*: int = -1
  visibilityMapSelectionId*: int = -1
  visibilityMap*: TileMap
  explorationFogMapStep*: int = -1
  explorationFogMapSelectionId*: int = -1
  explorationFogMap*: TileMap

  # AoE tilemap system - one map per team (dynamic).
  aoeMaps*: seq[TileMap]
  aoeMapStep*: int = -1
  aoeMapSelectionId*: int = -1
  aoeMapHiddenTeams*: HashSet[int]

  # Allocated coverage map for AoE map generation,
  # so that it's not reallocated every time and cause GC pressure.
  reuseableCoverageMap: seq[bool]
  reuseableFriendlyScoreMap: seq[float32]
  reuseableEnemyScoreMap: seq[float32]

  px*: Pixelator
  pxMini*: Pixelator
  sq*: ShaderQuad
  previousPanelSize*: Vec2 = vec2(0, 0)
  worldHeatmap*: Heatmap
  heatmapShaderInitialized*: bool = false
  needsInitialFit*: bool = true

proc ensureHeatmapReady*() =
  ## Lazily initialize heatmap data and shader on first use.
  if replay.isNil:
    return
  if worldHeatmap == nil:
    worldHeatmap = newHeatmap(replay)
  worldHeatmap.update(step, replay)
  if not heatmapShaderInitialized:
    initHeatmapShader()
    heatmapShaderInitialized = true

const patternToTile = @[
  18, 17, 4, 4, 12, 22, 4, 4, 30, 13, 41, 41, 30, 13, 41, 41, 19, 23, 5, 5, 37,
  9, 5, 5, 30, 13, 41, 41, 30, 13, 41, 41, 24, 43, 39, 39, 44, 45, 39, 39, 48,
  32, 46, 46, 48, 32, 46, 46, 24, 43, 39, 39, 44, 45, 39, 39, 48, 32, 46, 46,
  48, 32, 46, 46, 36, 10, 3, 3, 16, 40, 3, 3, 20, 27, 6, 6, 20, 27, 6, 6, 25,
  15, 2, 2, 26, 38, 2, 2, 20, 27, 6, 6, 20, 27, 6, 6, 24, 43, 39, 39, 44, 45,
  39, 39, 48, 32, 46, 46, 48, 32, 46, 46, 24, 43, 39, 39, 44, 45, 39, 39, 48,
  32, 46, 46, 48, 32, 46, 46, 28, 28, 8, 8, 21, 21, 8, 8, 33, 33, 7, 7, 33, 33,
  7, 7, 35, 35, 31, 31, 14, 14, 31, 31, 33, 33, 7, 7, 33, 33, 7, 7, 47, 47, 1,
  1, 42, 42, 1, 1, 34, 34, 0, 0, 34, 34, 0, 0, 47, 47, 1, 1, 42, 42, 1, 1,
  34, 34, 0, 0, 34, 34, 0, 0, 28, 28, 8, 8, 21, 21, 8, 8, 33, 33, 7, 7, 33,
  33, 7, 7, 35, 35, 31, 31, 14, 14, 31, 31, 33, 33, 7, 7, 33, 33, 7, 7, 47, 47,
  1, 1, 42, 42, 1, 1, 34, 34, 0, 0, 34, 34, 0, 0, 47, 47, 1, 1, 42, 42, 1,
  1, 34, 34, 0, 0, 34, 34, 0, 0
]

proc withinAgentVisionMask(dx: int32, dy: int32, radius: int, radiusSq: int): bool =
  let
    dxInt = int(dx)
    dyInt = int(dy)
    distSq = dxInt * dxInt + dyInt * dyInt
  if distSq <= radiusSq:
    return true
  # Expand pure cardinal tips from 1 tile to 3 tiles for radius >= 2.
  radius >= 2 and distSq == radiusSq + 1 and
    (abs(dxInt) == radius or abs(dyInt) == radius)

proc rebuildVisibilityMap*(visibilityMap: TileMap) {.measure.} =
  ## Rebuild the visibility map.
  let
    width = visibilityMap.width
    height = visibilityMap.height

  var fogOfWarMap: seq[bool] = newSeq[bool](width * height)
  for y in 1 .. replay.mapSize[1]:
    for x in 1 .. replay.mapSize[0]:
      fogOfWarMap[y * width + x] = true

  # Walk the agents and clear the visibility map.
  # If an agent is selected, only show that agent's vision. Otherwise show all agents.
  let agentsToProcess = if selected != nil and selected.isAgent:
    @[selected]
  else:
    replay.agents

  for obj in agentsToProcess:
    let center = ivec2(int32(obj.visionSize div 2), int32(obj.visionSize div 2))
    let visionRadius = obj.visionSize div 2
    let visionRadiusSq = visionRadius * visionRadius
    let pos = obj.location.at
    for i in 0 ..< obj.visionSize:
      for j in 0 ..< obj.visionSize:
        let dx = int32(i) - center.x
        let dy = int32(j) - center.y
        if not withinAgentVisionMask(dx, dy, visionRadius, visionRadiusSq):
          continue
        let gridPos = pos.xy + ivec2(int32(i), int32(j)) - center + ivec2(1, 1)
        if gridPos.x >= 0 and gridPos.x < width and
          gridPos.y >= 0 and gridPos.y < height:
          fogOfWarMap[gridPos.y * width + gridPos.x] = false

  # Generate the tile edges.
  for i in 0 ..< visibilityMap.indexData.len:
    let x = i mod width
    let y = i div width

    proc get(map: seq[bool], x: int, y: int): int =
      if x < 0 or y < 0 or x >= width or y >= height:
        return 0
      if map[y * width + x]:
        return 1
      return 0

    var tile: uint8 = 0
    if fogOfWarMap[y * width + x]:
      tile = 49
    else:
      let
        pattern = (
          1 * fogOfWarMap.get(x-1, y-1) + # NW
          2 * fogOfWarMap.get(x, y-1) + # N
          4 * fogOfWarMap.get(x+1, y-1) + # NE
          8 * fogOfWarMap.get(x+1, y) + # E
          16 * fogOfWarMap.get(x+1, y+1) + # SE
          32 * fogOfWarMap.get(x, y+1) + # S
          64 * fogOfWarMap.get(x-1, y+1) + # SW
          128 * fogOfWarMap.get(x-1, y) # W
        )
      tile = patternToTile[pattern].uint8
    visibilityMap.indexData[i] = tile

proc generateVisibilityMap(): TileMap {.measure.} =
  ## Generate a 1024x1024 texture where each pixel is a byte index into the 16x16 tile map.
  let
    width = ceil((replay.mapSize[0] + 2).float32 / 32.0f).int * 32
    height = ceil((replay.mapSize[1] + 2).float32 / 32.0f).int * 32

  var visibilityMap = newTileMap(
    width = width,
    height = height,
    tileSize = 64,
    atlasPath = dataDir / "fog7x8.png"
  )
  visibilityMap.rebuildVisibilityMap()
  visibilityMap.setupGPU()
  return visibilityMap

proc updateVisibilityMap*(visibilityMap: TileMap) =
  ## Update the visibility map.
  visibilityMap.rebuildVisibilityMap()
  visibilityMap.updateGPU()

proc rebuildExplorationFogMap*(explorationFogMap: TileMap) {.measure.} =
  ## Rebuild persistent exploration fog map up to current step.
  let
    width = explorationFogMap.width
    height = explorationFogMap.height

  var fogOfWarMap: seq[bool] = newSeq[bool](width * height)
  for y in 1 .. replay.mapSize[1]:
    for x in 1 .. replay.mapSize[0]:
      fogOfWarMap[y * width + x] = true


  # Selection-aware source:
  # - one selected agent => only that agent's historical exploration
  # - no selected agent => all agents
  let agentsToProcess = if selected != nil and selected.isAgent:
    @[selected]
  else:
    replay.agents

  # NOTE: We intentionally recompute exploration from history each update.
  # In practice this has been fast enough for current replay sizes, and it keeps
  # memory bounded. Caching explored fog per step/per agent would significantly
  # increase memory use (potentially map-size data across many timesteps).
  for obj in agentsToProcess:
    let center = ivec2(int32(obj.visionSize div 2), int32(obj.visionSize div 2))
    let visionRadius = obj.visionSize div 2
    let visionRadiusSq = visionRadius * visionRadius
    for historyStep in 0 .. step:
      let pos = obj.location.at(historyStep)
      for i in 0 ..< obj.visionSize:
        for j in 0 ..< obj.visionSize:
          let dx = int32(i) - center.x
          let dy = int32(j) - center.y
          if not withinAgentVisionMask(dx, dy, visionRadius, visionRadiusSq):
            continue
          let gridPos = pos.xy + ivec2(int32(i), int32(j)) - center + ivec2(1, 1)
          if gridPos.x >= 0 and gridPos.x < width and
            gridPos.y >= 0 and gridPos.y < height:
            fogOfWarMap[gridPos.y * width + gridPos.x] = false

  # Generate tile edges.
  for i in 0 ..< explorationFogMap.indexData.len:
    let x = i mod width
    let y = i div width

    proc get(map: seq[bool], x: int, y: int): int =
      if x < 0 or y < 0 or x >= width or y >= height:
        return 0
      if map[y * width + x]:
        return 1
      return 0

    var tile: uint8 = 0
    if fogOfWarMap[y * width + x]:
      tile = 49
    else:
      let
        pattern = (
          1 * fogOfWarMap.get(x-1, y-1) + # NW
          2 * fogOfWarMap.get(x, y-1) + # N
          4 * fogOfWarMap.get(x+1, y-1) + # NE
          8 * fogOfWarMap.get(x+1, y) + # E
          16 * fogOfWarMap.get(x+1, y+1) + # SE
          32 * fogOfWarMap.get(x, y+1) + # S
          64 * fogOfWarMap.get(x-1, y+1) + # SW
          128 * fogOfWarMap.get(x-1, y) # W
        )
      tile = patternToTile[pattern].uint8
    explorationFogMap.indexData[i] = tile

proc generateExplorationFogMap(): TileMap {.measure.} =
  ## Generate persistent exploration fog tilemap.
  let
    width = ceil((replay.mapSize[0] + 2).float32 / 32.0f).int * 32
    height = ceil((replay.mapSize[1] + 2).float32 / 32.0f).int * 32

  var explorationFogMap = newTileMap(
    width = width,
    height = height,
    tileSize = 64,
    atlasPath = dataDir / "fog7x8.png"
  )
  explorationFogMap.rebuildExplorationFogMap()
  explorationFogMap.setupGPU()
  return explorationFogMap

proc updateExplorationFogMap*(explorationFogMap: TileMap) =
  ## Update persistent exploration fog map.
  explorationFogMap.rebuildExplorationFogMap()
  explorationFogMap.updateGPU()

proc getProjectionView*(): Mat4 {.measure.} =
  ## Get the projection and view matrix.
  let m = getTransform()
  let view = mat4(
    m[0, 0], m[0, 1], m[0, 2], 0,
    m[1, 0], m[1, 1], m[1, 2], 0,
    0, 0, 0, 1,
    m[2, 0], m[2, 1], m[2, 2], 1
  )
  let projection = ortho(0.0f, window.size.x.float32, window.size.y.float32, 0.0f, -1.0f, 1.0f)
  projection * view

proc withinTerritoryInfluenceRadius(dx: int, dy: int, aoeRange: int): bool =
  ## Matches C++ TerritoryTracker::register_source: dist_sq <= range_sq.
  dx * dx + dy * dy <= aoeRange * aoeRange

proc territoryInfluenceScore(spec: TerritoryControl, distSq: int): float32 =
  max(0.0f, spec.strength.float32 - spec.decay.float32 * sqrt(distSq.float32))

proc rebuildAoeMap*(aoeMap: TileMap, teamIdx: int) {.measure.} =
  ## Rebuild the AoE map for a specific team with friendly/enemy scoring.
  let
    width = aoeMap.width
    height = aoeMap.height
    mapWidth = replay.mapSize[0]
    mapHeight = replay.mapSize[1]

  reuseableCoverageMap.setLen(width * height)
  reuseableFriendlyScoreMap.setLen(width * height)
  reuseableEnemyScoreMap.setLen(width * height)
  for i in 0 ..< reuseableCoverageMap.len:
    reuseableCoverageMap[i] = true
    reuseableFriendlyScoreMap[i] = 0.0f
    reuseableEnemyScoreMap[i] = 0.0f

  let
    numTeams = getNumTeams()
    hasTeams = numTeams > 0
    isEnabled = if hasTeams:
      teamIdx < numTeams and teamIdx notin settings.hiddenTeamAoe
    else:
      teamIdx == 0

  proc markSelectedCoverage(obj: Entity) =
    if hasTeams and getEntityTeamIndex(obj) != teamIdx:
      return
    let specs = influenceAoeSpecs(obj)
    if specs.len == 0:
      return
    let pos = obj.location.at(step).xy
    for spec in specs:
      let range = spec.effectiveRadius
      for dx in -range .. range:
        for dy in -range .. range:
          let
            tx = pos.x + dx.int32
            ty = pos.y + dy.int32
          if not withinTerritoryInfluenceRadius(dx, dy, range):
            continue
          let distSq = dx * dx + dy * dy
          let score = territoryInfluenceScore(spec, distSq)
          if score <= 0.0f:
            continue
          if tx >= 0 and tx < mapWidth and ty >= 0 and ty < mapHeight:
            reuseableCoverageMap[ty * width + tx] = false

  proc accumulateInfluence(obj: Entity) =
    let specs = influenceAoeSpecs(obj)
    if specs.len == 0:
      return
    var isFriendly = false
    if hasTeams:
      let objTeam = getEntityTeamIndex(obj)
      if objTeam < 0 or objTeam in settings.hiddenTeamAoe:
        return
      isFriendly = objTeam == teamIdx
    let pos = obj.location.at(step).xy
    for spec in specs:
      let range = spec.effectiveRadius
      for dx in -range .. range:
        for dy in -range .. range:
          let
            tx = pos.x + dx.int32
            ty = pos.y + dy.int32
          if not withinTerritoryInfluenceRadius(dx, dy, range):
            continue
          if tx >= 0 and tx < mapWidth and ty >= 0 and ty < mapHeight:
            let idx = ty * width + tx
            let distSq = dx * dx + dy * dy
            let score = territoryInfluenceScore(spec, distSq)
            if score <= 0.0f:
              continue
            if not hasTeams:
              reuseableCoverageMap[idx] = false
            elif isFriendly:
              reuseableFriendlyScoreMap[idx] += score
            else:
              reuseableEnemyScoreMap[idx] += score

  let selectionHasInfluence = selected != nil and hasInfluenceAoe(selected)
  if selectionHasInfluence:
    markSelectedCoverage(selected)
  else:
    if isEnabled:
      for obj in replay.objects:
        if not obj.alive.at:
          continue
        accumulateInfluence(obj)
      if hasTeams:
        for i in 0 ..< reuseableCoverageMap.len:
          let
            friendlyScore = reuseableFriendlyScoreMap[i]
            enemyScore = reuseableEnemyScoreMap[i]
          reuseableCoverageMap[i] = friendlyScore <= enemyScore + 1e-6f

  for i in 0 ..< aoeMap.indexData.len:
    let x = i mod width
    let y = i div width

    proc get(map: seq[bool], x: int, y: int): int =
      if x < 0 or y < 0 or x >= width or y >= height:
        return 1
      if map[y * width + x]:
        return 1
      return 0

    var tile: uint8 = 0
    if reuseableCoverageMap[y * width + x]:
      tile = 49
    else:
      let
        pattern = (
          1 * reuseableCoverageMap.get(x-1, y-1) +
          2 * reuseableCoverageMap.get(x, y-1) +
          4 * reuseableCoverageMap.get(x+1, y-1) +
          8 * reuseableCoverageMap.get(x+1, y) +
          16 * reuseableCoverageMap.get(x+1, y+1) +
          32 * reuseableCoverageMap.get(x, y+1) +
          64 * reuseableCoverageMap.get(x-1, y+1) +
          128 * reuseableCoverageMap.get(x-1, y)
        )
      tile = patternToTile[pattern].uint8
    aoeMap.indexData[i] = tile

proc generateAoeMap(teamIdx: int): TileMap {.measure.} =
  ## Generate an AoE tilemap for a specific team.
  let
    width = ceil(replay.mapSize[0].float32 / 32.0f).int * 32
    height = ceil(replay.mapSize[1].float32 / 32.0f).int * 32

  var aoeMap = newTileMap(
    width = width,
    height = height,
    tileSize = 64,
    atlasPath = dataDir / "aoe7x8.png"
  )
  aoeMap.rebuildAoeMap(teamIdx)
  aoeMap.setupGPU()
  return aoeMap

proc initAoeMaps*() {.measure.} =
  ## Initialize AoE tilemaps, one per team.
  let count = max(getNumTeams(), 1)
  aoeMaps = newSeq[TileMap](count)
  for i in 0 ..< count:
    aoeMaps[i] = generateAoeMap(i)
  aoeMapStep = step
  aoeMapHiddenTeams = settings.hiddenTeamAoe

proc updateAoeMaps*() {.measure.} =
  ## Update all AoE tilemaps.
  for i in 0 ..< aoeMaps.len:
    aoeMaps[i].rebuildAoeMap(i)
    aoeMaps[i].updateGPU()
  aoeMapStep = step
  aoeMapHiddenTeams = settings.hiddenTeamAoe

proc drawAoeMaps*() {.measure.} =
  ## Draw team-colored AoE tilemaps.
  if replay.isNil:
    return

  let
    numTeams = getNumTeams()
    expectedCount = max(numTeams, 1)
  if aoeMaps.len != expectedCount:
    initAoeMaps()

  let currentSelectionId = if selected != nil: selected.id else: -1
  let needsRebuild = aoeMapStep != step or
    aoeMapHiddenTeams != settings.hiddenTeamAoe or
    aoeMapSelectionId != currentSelectionId
  if needsRebuild:
    updateAoeMaps()
    aoeMapSelectionId = currentSelectionId

  let selectionHasInfluence = selected != nil and hasInfluenceAoe(selected)
  for i in 0 ..< aoeMaps.len:
    let shouldDraw = if selectionHasInfluence and numTeams > 0:
      getEntityTeamIndex(selected) == i
    else:
      i notin settings.hiddenTeamAoe
    if shouldDraw:
      let tint = if numTeams > 0:
        getTeamColor(i).color
      else:
        color(0.3, 0.6, 1.0, 0.5)
      aoeMaps[i].draw(
        getProjectionView(),
        zoom = 2.0f,
        zoomThreshold = 1.5f,
        tint = tint
      )

proc getMoveActionDir(agent: Entity, atStep: int): Option[IVec2] =
  ## Return the attempted move direction for the given agent step when present.
  if agent.isNil or not agent.isAgent or replay.isNil:
    return none(IVec2)

  let actionId = agent.actionId.at(atStep)
  if actionId == replay.moveNorthActionId:
    return some(ivec2(0, -1))
  if actionId == replay.moveSouthActionId:
    return some(ivec2(0, 1))
  if actionId == replay.moveWestActionId:
    return some(ivec2(-1, 0))
  if actionId == replay.moveEastActionId:
    return some(ivec2(1, 0))
  none(IVec2)

proc getBumpDirForAction(agent: Entity, actionStep: int): Option[IVec2] =
  ## Return the bump direction for a single action step.
  const AnimationBump = 1
  if agent.isNil or not agent.isAgent or replay.isNil:
    return none(IVec2)

  if agent.animationId.len > 0 and agent.animationId.at(actionStep) == AnimationBump:
    return agent.getMoveActionDir(actionStep)

  none(IVec2)

proc getBumpDir(agent: Entity, atStep: int): Option[IVec2] =
  ## Return the bump direction for the rendered interval starting at the given step.
  if agent.isNil or not agent.isAgent or replay.isNil:
    return none(IVec2)
  if atStep < 0 or atStep + 1 >= replay.maxSteps:
    return none(IVec2)

  let
    startPos = agent.location.at(atStep).xy
    endPos = agent.location.at(atStep + 1).xy
  if startPos != endPos:
    return none(IVec2)

  let startActionBump = agent.getBumpDirForAction(atStep)
  if startActionBump.isSome:
    return startActionBump

  agent.getBumpDirForAction(atStep + 1)

proc getActiveBumpDir(agent: Entity): Option[IVec2] =
  ## Return the current bump direction while the bump animation is active.
  if agent.isNil or not agent.isAgent or replay.isNil:
    return none(IVec2)
  if playSpeed > BumpDisableSpeed:
    return none(IVec2)

  let
    baseStep = floor(stepFloat).int
    stepFrac = clamp(stepFloat - baseStep.float32, 0.0f, 1.0f)
  if stepFrac <= 0.0f or stepFrac >= BumpActiveFraction:
    return none(IVec2)

  agent.getBumpDir(baseStep)

proc bumpOffset(agent: Entity): Vec2 =
  ## Return the render-time offset for the current bump animation frame.
  if agent.isNil or not agent.isAgent or replay.isNil:
    return vec2(0, 0)

  let
    baseStep = floor(stepFloat).int
    stepFrac = clamp(stepFloat - baseStep.float32, 0.0f, 1.0f)
  if stepFrac <= 0.0f or stepFrac >= BumpActiveFraction:
    return vec2(0, 0)

  let bumpDir = agent.getActiveBumpDir()
  if not bumpDir.isSome:
    return vec2(0, 0)

  let
    progress = stepFrac / BumpActiveFraction
    depth = sin(PI.float32 * progress) * BumpDepthTiles
  bumpDir.get.vec2 * depth

proc smoothPos*(entity: Entity): Vec2 =
  ## Interpolate position with Catmull-Rom spline for smooth corners.
  if entity.isNil:
    return vec2(0, 0)
  let
    baseStep = floor(stepFloat).int
    t = clamp(stepFloat - baseStep.float32, 0.0f, 1.0f)
    p1 = entity.location.at(baseStep).xy.vec2
    p2 = entity.location.at(baseStep + 1).xy.vec2
  if playSpeed > TurnDisableSpeed or baseStep < 1:
    result = p1 + (p2 - p1) * t
  elif p1 == p2:
    # Fall back to linear when stationary this step.
    result = p1
  else:
    let
      p0 = entity.location.at(baseStep - 1).xy.vec2
      p3 = entity.location.at(baseStep + 2).xy.vec2
      # Zero tangent when the adjacent segment is stationary to prevent overshoot.
      m0 = if p0 == p1: vec2(0, 0) else: CornerRoundingTension * (p2 - p0)
      m1 = if p2 == p3: vec2(0, 0) else: CornerRoundingTension * (p3 - p1)
      t2 = t * t
      t3 = t2 * t
    # Cubic Hermite spline.
    result = (2.0f*t3 - 3.0f*t2 + 1.0f) * p1 +
      (t3 - 2.0f*t2 + t) * m0 +
      (-2.0f*t3 + 3.0f*t2) * p2 +
      (t3 - t2) * m1
  if entity.isAgent:
    result += bumpOffset(entity)

proc isSelectableCandidate(entity: Entity): bool =
  ## Return true when an entity should participate in click selection.
  not entity.isNil and entity.typeName != "wall" and entity.alive.at

proc issueOrderAt(gridPos: IVec2, mousePos: Vec2, effectiveShift: bool, effectiveRepeat: bool) =
  ## Issue a move or bump order for the selected agent at the given grid position.
  if selected == nil or not selected.isAgent:
    return
  let startPos = selected.location.at(replay.maxSteps - 1).xy
  let targetObj = getObjectAtLocation(gridPos)
  var objective: Objective
  if targetObj != nil:
    let typeName = targetObj.typeName
    if typeName != "agent" and typeName != "wall":
      let
        tileCenterX = gridPos.x.float32
        tileCenterY = gridPos.y.float32
        offsetX = mousePos.x - tileCenterX
        offsetY = mousePos.y - tileCenterY
      var approachDir: IVec2
      if abs(offsetX) > abs(offsetY):
        approachDir = if offsetX > 0: ivec2(1, 0) else: ivec2(-1, 0)
      else:
        approachDir = if offsetY > 0: ivec2(0, 1) else: ivec2(0, -1)
      objective = Objective(kind: Bump, pos: gridPos, approachDir: approachDir, repeat: effectiveRepeat)
    else:
      objective = Objective(kind: Move, pos: gridPos, approachDir: ivec2(0, 0), repeat: effectiveRepeat)
  else:
    objective = Objective(kind: Move, pos: gridPos, approachDir: ivec2(0, 0), repeat: effectiveRepeat)
  if effectiveShift:
    if not agentObjectives.hasKey(selected.agentId) or agentObjectives[selected.agentId].len == 0:
      agentObjectives[selected.agentId] = @[objective]
      recomputePath(selected.agentId, startPos)
    else:
      agentObjectives[selected.agentId].add(objective)
      recomputePath(selected.agentId, startPos)
  else:
    agentObjectives[selected.agentId] = @[objective]
    recomputePath(selected.agentId, startPos)

proc useSelections*(zoomInfo: ZoomInfo) {.measure.} =
  ## Reads the mouse position and selects the thing under it.
  let modifierDown = when defined(macosx):
    window.buttonDown[KeyLeftSuper] or window.buttonDown[KeyRightSuper]
  else:
    window.buttonDown[KeyLeftControl] or window.buttonDown[KeyRightControl]

  if not selected.isNil and not selected.alive.at:
    selectObject(nil)

  let shiftDown = window.buttonDown[KeyLeftShift] or window.buttonDown[KeyRightShift]
  let rDown = window.buttonDown[KeyR]
  let effectiveShift = shiftDown or queueToggleActive
  let effectiveRepeat = rDown or repeatToggleActive

  # Track mouse down position to distinguish clicks from drags.
  if window.buttonPressed[MouseLeft] and not modifierDown:
    mouseDownPos = window.mousePos.vec2

  # Toggle pin on double-click.
  if window.buttonPressed[DoubleClick] and not modifierDown:
    settings.lockFocus = not settings.lockFocus

  # Left-click release: selection or order (when move mode active).
  if window.buttonReleased[MouseLeft] and not modifierDown:
    let mouseDragDistance = (window.mousePos.vec2 - mouseDownPos).length
    const maxClickDragDistance = 5.0
    if mouseDragDistance < maxClickDragDistance:
      let
        mouseScreenPos = window.mousePos.vec2
        mousePos = getTransform().inverse * mouseScreenPos
        gridPos = (mousePos + vec2(0.5, 0.5)).ivec2
        clickRadiusSq = SelectionRadiusPixels * SelectionRadiusPixels
        transform = getTransform()
      var
        obj: Entity = nil
        closestDistSq = clickRadiusSq
      for candidate in replay.objects:
        if not isSelectableCandidate(candidate):
          continue
        let
          candidateScreenPos = transform * candidate.smoothPos()
          delta = candidateScreenPos - mouseScreenPos
          distSq = delta.x * delta.x + delta.y * delta.y
          sameDistance = abs(distSq - closestDistSq) <= 0.0001f
        if distSq > clickRadiusSq:
          continue
        if obj.isNil or distSq < closestDistSq or (sameDistance and candidate.id < obj.id):
          obj = candidate
          closestDistSq = distSq

      let inMapBounds = gridPos.x >= 0 and gridPos.x < replay.mapSize[0] and
        gridPos.y >= 0 and gridPos.y < replay.mapSize[1]
      if moveToggleActive and selected != nil and selected.isAgent and inMapBounds:
        if obj != nil and obj.isAgent:
          selectObject(obj)
        else:
          issueOrderAt(gridPos, mousePos, effectiveShift, effectiveRepeat)
          if not queueToggleActive:
            moveToggleActive = false
      else:
        selectObject(obj)

  # Right-click or Ctrl+left: issue order.
  if window.buttonPressed[MouseRight] or (window.buttonPressed[MouseLeft] and modifierDown):
    if selected != nil and selected.isAgent:
      let
        mousePos = getTransform().inverse * window.mousePos.vec2
        gridPos = (mousePos + vec2(0.5, 0.5)).ivec2
      if gridPos.x >= 0 and gridPos.x < replay.mapSize[0] and
        gridPos.y >= 0 and gridPos.y < replay.mapSize[1]:
        issueOrderAt(gridPos, mousePos, effectiveShift, effectiveRepeat)

proc inferOrientationFromDir(dir: IVec2): Orientation =
  ## Return a cardinal orientation for the given direction vector.
  if dir.x > 0:
    return E
  if dir.x < 0:
    return W
  if dir.y > 0:
    return S
  N

proc inferOrientation*(agent: Entity, step: int): Orientation =
  ## Get the orientation from movement, else from a successful directional action.
  if agent.isNil or agent.location.len == 0:
    return S
  let lastStep = step.clamp(0, agent.location.len - 1)
  for i in countdown(lastStep, 0):
    if i > 0:
      let
        loc0 = agent.location.at(i - 1)
        loc1 = agent.location.at(i)
        dx = loc1.x - loc0.x
        dy = loc1.y - loc0.y
      if dx != 0 or dy != 0:
        if dx > 0:
          return E
        elif dx < 0:
          return W
        elif dy > 0:
          return S
        else:
          return N

    if agent.actionSuccess.len > 0 and agent.actionSuccess.at(i):
      let moveDir = agent.getMoveActionDir(i)
      if moveDir.isSome:
        return inferOrientationFromDir(moveDir.get)
  return S

# stripTeamSuffix, stripTeamPrefix, normalizeTypeName are imported from common

proc diagonalSuffix(a, b: Orientation): string =
  ## Return the diagonal sprite suffix for a turn between two cardinals.
  ## Returns "" for 180-degree turns or same direction.
  case a
  of N:
    case b
    of E: "ne"
    of W: "nw"
    else: ""
  of S:
    case b
    of E: "se"
    of W: "sw"
    else: ""
  of E:
    case b
    of N: "ne"
    of S: "se"
    else: ""
  of W:
    case b
    of N: "nw"
    of S: "sw"
    else: ""
  of Invalid: ""

proc smoothOrientation*(agent: Entity): string =
  ## Return sprite direction suffix for the agent's current facing.
  ## Returns "n","s","e","w" normally, or "ne","nw","se","sw" during turn transitions.
  ## Diagonal straddles the step boundary: last 20% before + first 20% after a turn.
  if agent.isNil:
    return $S.char

  let bumpDir = agent.getActiveBumpDir()
  if bumpDir.isSome:
    return $inferOrientationFromDir(bumpDir.get).char

  let
    baseStep = floor(stepFloat).int
    stepFrac = clamp(stepFloat - baseStep.float32, 0.0f, 1.0f)
    orientationCurr = inferOrientation(agent, baseStep)
    orientationNext = inferOrientation(agent, baseStep + 1)
  if playSpeed <= TurnDisableSpeed and baseStep > 0:
    # Just turned: first 20% of this step, show diagonal for curr->next boundary.
    if orientationCurr != orientationNext and stepFrac < TurnTransitionHalf:
      let diag = diagonalSuffix(orientationCurr, orientationNext)
      if diag.len > 0:
        return diag
    # Approaching turn: last 20% of this step, show diagonal for next boundary.
    if stepFrac > (1.0f - TurnTransitionHalf):
      let orientationNextNext = inferOrientation(agent, baseStep + 2)
      if orientationNext != orientationNextNext:
        let diag = diagonalSuffix(orientationNext, orientationNextNext)
        if diag.len > 0:
          return diag
  if stepFrac >= 0.05f:
    $orientationNext.char
  else:
    $orientationCurr.char

proc agentRigName(agent: Entity): string =
  ## Get the rig of the agent.
  # Look at the inventory show the rig for "scout", "miner", "aligner" and "scrambler"
  if agent.inventory.len == 0:
    return "agent"
  for item in agent.inventory.at(step):
    let itemName = replay.itemNames[item.itemId]
    if itemName == "scout":
      return "scout"
    elif itemName == "miner":
      return "miner"
    elif itemName == "aligner":
      return "aligner"
    elif itemName == "scrambler":
      return "scrambler"
  return "agent"

proc remnantSpriteName(obj: Entity): string =
  ## Return a remnant sprite name when available for a dead building.
  let resolvedAsset = replay.resolveRenderAsset(obj, step)
  for name in @[
    resolvedAsset,
    obj.renderName,
    obj.typeName,
    stripTeamPrefix(obj.typeName),
    stripTeamSuffix(obj.typeName)
  ]:
    if name.len == 0:
      continue
    let sprite = "objects/" & name & ".remnant"
    if sprite in px:
      return sprite
  ""

proc drawObjects*() {.measure.} =
  ## Draw the objects on the map, sorted for correct draw order.

  # Sort: lower Y first (farther away, drawn behind), buildings before agents
  # at same Y, then by object ID ascending.

  # Collect non-wall objects into a sortable list.
  var objects = newSeqOfCap[Entity](replay.objects.len)
  for obj in replay.objects:
    if obj.typeName == "wall":
      continue
    objects.add(obj)

  # Sort for painter's algorithm draw order.
  objects.sort(proc(a, b: Entity): int =
    let
      aY = a.smoothPos().y
      bY = b.smoothPos().y
    # Primary: lower Y drawn first (behind).
    result = cmp(aY, bY)
    if result != 0: return
    # Secondary: buildings before agents at same Y.
    let
      aOrder = if a.typeName == "agent": 1 else: 0
      bOrder = if b.typeName == "agent": 1 else: 0
    result = cmp(aOrder, bOrder)
    if result != 0: return
    # Tertiary: lower object ID drawn first.
    result = cmp(a.id, b.id)
  )

  # Tracks
  const SpriteOffset = ivec2(0, -32)

  for thing in objects:
    let pos = thing.smoothPos()
    if thing.typeName == "agent":
      let agent = thing
      let resolvedAsset = replay.resolveRenderAsset(agent, step)
      let dirSuffix = smoothOrientation(agent)
      var agentImage =
        if resolvedAsset.len > 0:
          "agents/" & resolvedAsset & "." & dirSuffix
        else:
          ""
      if agentImage notin px:
        agentImage = "agents/" & agentRigName(agent) & "." & dirSuffix

      # Tint sprite by team color using mask for selective coloring.
      let teamIdx = getEntityTeamIndex(agent)
      let tint = if teamIdx >= 0: getTeamColor(teamIdx) else: WhiteTint
      let mask = if teamIdx >= 0: agentImage & ".mask" else: ""

      px.drawSprite(
        agentImage,
        (pos * TileSize.float32 + SpriteOffset.vec2).ivec2,
        tint,
        mask
      )

    else:
      if not thing.alive.at:
        let remnantSprite = remnantSpriteName(thing)
        if remnantSprite.len == 0:
          continue
        px.drawSprite(
          remnantSprite,
          (pos * TileSize.float32 + SpriteOffset.vec2).ivec2
        )
        continue

      let resolvedAsset = replay.resolveRenderAsset(thing, step)
      let spriteName =
        if resolvedAsset.len > 0 and "objects/" & resolvedAsset in px:
          "objects/" & resolvedAsset
        elif "objects/" & thing.renderName in px:
          "objects/" & thing.renderName
        elif "objects/" & thing.typeName in px:
          "objects/" & thing.typeName
        elif "objects/" & stripTeamPrefix(thing.typeName) in px:
          "objects/" & stripTeamPrefix(thing.typeName)
        elif "objects/" & stripTeamSuffix(thing.typeName) in px:
          "objects/" & stripTeamSuffix(thing.typeName)
        else:
          "objects/unknown"
      let normalized = normalizeTypeName(thing.typeName)
      let teamIdx = getEntityTeamIndex(thing)
      if normalized == "junction" and teamIdx >= 0:
        px.drawSprite(
          spriteName,
          (pos * TileSize.float32 + SpriteOffset.vec2).ivec2,
          getTeamColor(teamIdx),
          lamp = "objects/junction.lamp"
        )
      else:
        px.drawSprite(
          spriteName,
          (pos * TileSize.float32 + SpriteOffset.vec2).ivec2
        )

proc drawVisualRanges*(alpha = 0.5) {.measure.} =
  ## Draw the visual ranges of the selected agent.

  if visibilityMap == nil:
    visibilityMapStep = step
    visibilityMapSelectionId = if selected != nil: selected.id else: -1
    visibilityMap = generateVisibilityMap()

  let
    currentSelectionId = if selected != nil: selected.id else: -1
    needsRebuild = visibilityMapStep != step or visibilityMapSelectionId != currentSelectionId

  if needsRebuild:
    visibilityMapStep = step
    visibilityMapSelectionId = currentSelectionId
    visibilityMap.updateVisibilityMap()

  visibilityMap.draw(
    getProjectionView() * translate(vec3(-1.0f, -1.0f, 0.0f)),
    zoom = 2.0f,
    zoomThreshold = 1.5f,
    tint = color(0, 0, 0, alpha)
  )

proc drawFogOfWar*() {.measure.} =
  ## Draw exploration fog of war.
  if explorationFogMap == nil:
    explorationFogMapStep = step
    explorationFogMapSelectionId = if selected != nil: selected.id else: -1
    explorationFogMap = generateExplorationFogMap()

  let
    currentSelectionId = if selected != nil: selected.id else: -1
    needsRebuild = explorationFogMapStep != step or explorationFogMapSelectionId != currentSelectionId

  if needsRebuild:
    explorationFogMapStep = step
    explorationFogMapSelectionId = currentSelectionId
    explorationFogMap.updateExplorationFogMap()

  explorationFogMap.draw(
    getProjectionView() * translate(vec3(-1.0f, -1.0f, 0.0f)),
    zoom = 2.0f,
    zoomThreshold = 1.5f,
    tint = color(0, 0, 0, 1.0)
  )

proc drawTrajectory*() {.measure.} =
  ## Draw the trajectory of the selected object, with footprints or a future arrow.
  if selected != nil and selected.location.len > 1:
    var prevDirection = S
    for i in 1 ..< replay.maxSteps:
      let
        loc0 = selected.location.at(i - 1)
        loc1 = selected.location.at(i)
        cx0 = loc0.x.int
        cy0 = loc0.y.int
        cx1 = loc1.x.int
        cy1 = loc1.y.int

      if loc0.x == loc1.x and loc0.y == loc1.y:
        continue

      if cx0 != cx1 or cy0 != cy1:
        var thisDirection: Orientation =
          if cx1 > cx0:
            E
          elif cx1 < cx0:
            W
          elif cy1 > cy0:
            S
          else:
            N
        if prevDirection == N and thisDirection == S or
          prevDirection == S and thisDirection == N or
          prevDirection == E and thisDirection == W or
          prevDirection == W and thisDirection == E:
          # Turned around, don't draw a track.
          continue

        let a = 1.0f - abs(i - step).float32 / 200.0f
        if a > 0:
          var image = ""
          if i <= step:
            image = "agents/tracks." & prevDirection.char & thisDirection.char
          else:
            image = "agents/path." & prevDirection.char & thisDirection.char

          # Draw centered at the tile with rotation. Use a slightly larger scale on diagonals.
          px.drawSprite(
            image,
            ivec2(cx0.int32, cy0.int32) * TileSize
          )
        prevDirection = thisDirection

proc getInventoryItem*(entity: Entity, itemName: string, atStep: int = step): int =
  ## Get the count of a named item in the entity's inventory at a given step.
  let itemId = replay.itemNames.find(itemName)
  if itemId < 0:
    return 0
  let inv = entity.inventory.at(atStep)
  for item in inv:
    if item.itemId == itemId:
      return item.count
  return 0

type PipSize* = enum
  SmallPip   # 2x3 px
  MediumPip  # 3x4 px
  LargePip   # 5x6 px

proc drawBar*(pos: IVec2, tint: ColorRGBX, numPips: int, maxValue: int, current: int, prev: int, size: PipSize) =
  ## Draw a bar centered horizontally at pos (in tile-pixel coords).
  ## Converts raw current/prev values to pips using maxValue.
  ## Delta between current and prev is shown in white.
  ## Sub-pip changes also flash the last filled pip white.
  let pipWidth = case size
    of SmallPip: 3
    of MediumPip: 4
    of LargePip: 6
  let (bgSprite, fgSprite) = case size
    of SmallPip: ("agents/barPip2x3Bg", "agents/barPip2x3")
    of MediumPip: ("agents/barPip3x4Bg", "agents/barPip3x4")
    of LargePip: ("agents/barPip5x6Bg", "agents/barPip5x6")
  let
    currentPips = clamp(current * numPips div max(maxValue, 1), 0, numPips)
    prevPips = clamp(prev * numPips div max(maxValue, 1), 0, numPips)
    barWidth = numPips * pipWidth
    startX = pos.x - int32(barWidth div 2) + int32(pipWidth div 2)
  # Pass 1: backgrounds
  for i in 0 ..< numPips:
    px.drawSprite(bgSprite, ivec2(startX + int32(i * pipWidth), pos.y))
  # Pass 2: colored current pips
  for i in 0 ..< currentPips:
    px.drawSprite(fgSprite, ivec2(startX + int32(i * pipWidth), pos.y), tint)
  # Pass 3: white delta pips (overwrites colored where whole pips changed)
  let deltaLo = min(currentPips, prevPips)
  let deltaHi = max(currentPips, prevPips)
  for i in deltaLo ..< deltaHi:
    px.drawSprite(fgSprite, ivec2(startX + int32(i * pipWidth), pos.y))
  # Sub-pip change: if raw value changed but pip count is the same, white-out last pip
  if current != prev and currentPips > 0 and currentPips == prevPips:
    px.drawSprite(fgSprite, ivec2(startX + int32((currentPips - 1) * pipWidth), pos.y))

proc drawAgentDecorations*() {.measure.} =
  ## Draw configurable HUD bars above each agent.
  const
    NumPips = 10
  let
    prevStep = max(0, step - 1)
    hud1Cfg = replay.hudItem1
    hud2Cfg = replay.hudItem2
  if replay.hasCustomHuds:
    const
      BaseHudY = 68
      HudYStep = 7
    let hudConfigs = replay.hudItems
    for agent in replay.agents:
      if not agent.alive.at:
        continue
      let pos = (agent.smoothPos * TileSize.float32).ivec2
      let tint = getTeamColor(getEntityTeamIndex(agent))
      for i, hudCfg in hudConfigs:
        let
          hud = getInventoryItem(agent, hudCfg.resource)
          hudPrev = getInventoryItem(agent, hudCfg.resource, prevStep)
          y = pos.y - int32(BaseHudY - i * HudYStep)
          barSize =
            if i == 0: LargePip
            else: MediumPip
          barTint =
            if i == 0: tint
            else: colors.Yellow
        drawBar(
          ivec2(pos.x, y), barTint, NumPips,
          hudCfg.max, hud, hudPrev, barSize)
  else:
    for agent in replay.agents:
      if not agent.alive.at:
        continue
      let pos = (agent.smoothPos * TileSize.float32).ivec2
      let tint = getTeamColor(getEntityTeamIndex(agent))
      let hud1 = getInventoryItem(agent, hud1Cfg.resource)
      let hud1Prev = getInventoryItem(agent, hud1Cfg.resource, prevStep)
      drawBar(ivec2(pos.x, pos.y - 68), tint, NumPips, hud1Cfg.max, hud1, hud1Prev, LargePip)
      let hud2 = getInventoryItem(agent, hud2Cfg.resource)
      let hud2Prev = getInventoryItem(agent, hud2Cfg.resource, prevStep)
      drawBar(ivec2(pos.x, pos.y - 61), colors.Yellow, NumPips, hud2Cfg.max, hud2, hud2Prev, MediumPip)

proc drawGrid*() {.measure.} =
  # Draw the grid using a single quad and shader-based lines.
  if sq == nil:
    sq = newGridQuad(dataDir / "view/grid10.png", 10, 10)
  let
    mvp = getProjectionView()
    mapSize = vec2(replay.mapSize[0].float32, replay.mapSize[1].float32)
    tileSize = vec2(1.0f, 1.0f) # world units per tile
    gridColor = vec4(1.0f, 1.0f, 1.0f, 1.0f) # subtle white grid
  sq.draw(mvp, mapSize, tileSize, gridColor, 1.0f)

proc effectiveQueueMode(): bool =
  ## Same semantics as order input: true when the next click would append to the queue.
  queueToggleActive or
    window.buttonDown[KeyLeftShift] or window.buttonDown[KeyRightShift]

proc getPreviewStartPos(agentId: int): IVec2 =
  ## Return the position to start the move preview from.
  ## When queue mode is active and there are queued objectives, returns the queued end position.
  ## Otherwise returns the agent's current position.
  let agent = getAgentById(agentId)
  var lastPos = agent.location.at(step).xy
  if not effectiveQueueMode():
    return lastPos
  if agentPaths.hasKey(agentId) and agentPaths[agentId].len > 0:
    var pos = agent.location.at(step).xy
    for action in agentPaths[agentId]:
      case action.kind
      of Move:
        pos = action.pos
      of Bump:
        pos = ivec2(action.bumpPos.x - action.bumpDir.x, action.bumpPos.y - action.bumpDir.y)
      of Vibe:
        discard
    return pos
  if agentObjectives.hasKey(agentId) and agentObjectives[agentId].len > 0:
    for objective in agentObjectives[agentId]:
      case objective.kind
      of Move:
        lastPos = objective.pos
      of Bump:
        lastPos = ivec2(
          objective.pos.x + objective.approachDir.x,
          objective.pos.y + objective.approachDir.y
        )
      of Vibe:
        discard
  lastPos

proc cardinalDirection(fromPos: IVec2, toPos: IVec2): Orientation =
  ## Resolve a cardinal direction for a single tile step.
  let
    dx = toPos.x - fromPos.x
    dy = toPos.y - fromPos.y
  if dx > 0 and dy == 0:
    return E
  if dx < 0 and dy == 0:
    return W
  if dx == 0 and dy > 0:
    return S
  if dx == 0 and dy < 0:
    return N
  Invalid

proc drawPlannedSegment(
  fromPos: IVec2,
  toPos: IVec2,
  prevDirection: var Orientation,
  hasPrevDirection: var bool,
  drawTile: bool = true
) =
  ## Draw one planned segment using directional plan sprites with path fallback.
  if fromPos == toPos:
    return
  let thisDirection = cardinalDirection(fromPos, toPos)
  if thisDirection == Invalid:
    echo "Expected cardinal move from ", fromPos, " to ", toPos
    if drawTile:
      px.drawSprite("agents/path", fromPos.ivec2 * TileSize)
    return

  let
    incomingDirection = if hasPrevDirection: prevDirection else: thisDirection
    planSprite = "agents/plan." & incomingDirection.char & thisDirection.char
    pathSprite = "agents/path." & incomingDirection.char & thisDirection.char
    isUTurn =
      (incomingDirection == N and thisDirection == S) or
      (incomingDirection == S and thisDirection == N) or
      (incomingDirection == E and thisDirection == W) or
      (incomingDirection == W and thisDirection == E)
    uTurnSprite = "agents/plan." & thisDirection.char

  if drawTile:
    if isUTurn and uTurnSprite in px:
      px.drawSprite(uTurnSprite, fromPos.ivec2 * TileSize)
    elif planSprite in px:
      px.drawSprite(planSprite, fromPos.ivec2 * TileSize)
    elif pathSprite in px:
      px.drawSprite(pathSprite, fromPos.ivec2 * TileSize)
    else:
      px.drawSprite("agents/path", fromPos.ivec2 * TileSize)

  prevDirection = thisDirection
  hasPrevDirection = true

proc drawMovePreview*() {.measure.} =
  ## Draw a prediction path from the selected agent to the mouse position when move mode is active.
  if not moveToggleActive or selected == nil or not selected.isAgent or replay == nil:
    return
  let
    mousePos = getTransform().inverse * window.mousePos.vec2
    gridPos = (mousePos + vec2(0.5, 0.5)).ivec2
  if gridPos.x < 0 or gridPos.x >= replay.mapSize[0] or gridPos.y < 0 or gridPos.y >= replay.mapSize[1]:
    return
  let startPos = getPreviewStartPos(selected.agentId)
  let previewPath = findPath(startPos, gridPos)
  var
    currentPos = startPos
    prevDirection = S
    hasPrevDirection = false
    isFirstSegment = true
  for pos in previewPath:
    if pos != startPos:
      drawPlannedSegment(
        currentPos,
        pos,
        prevDirection,
        hasPrevDirection,
        drawTile = not isFirstSegment
      )
      isFirstSegment = false
      currentPos = pos
  px.drawSprite("objects/selection", gridPos.ivec2 * TileSize)

proc drawPlannedPath*() {.measure.} =
  ## Draw the planned paths for all agents.
  ## Only show paths when in realtime mode and viewing the latest or partial step.
  let latestStep = (replay.maxSteps - 1).float32
  if playMode != Realtime or stepFloat < latestStep - 1.0:
    return
  for agentId, pathActions in agentPaths:
    if pathActions.len == 0:
      continue

    # Start the path from where the agent is heading, not where it was.
    let
      agent = getAgentById(agentId)
      baseStep = floor(stepFloat).int
    var
      currentPos = agent.location.at(baseStep + 1).xy
      prevDirection = S
      hasPrevDirection = false
      isFirstSegment = true

    for action in pathActions:
      case action.kind
      of Move:
        let
          pos0 = currentPos
          pos1 = action.pos

        drawPlannedSegment(
          pos0,
          pos1,
          prevDirection,
          hasPrevDirection,
          drawTile = not isFirstSegment
        )
        isFirstSegment = false
        currentPos = action.pos
      of Bump:
        # Draw the bump as a final path segment into the target tile.
        drawPlannedSegment(
          currentPos,
          action.bumpPos,
          prevDirection,
          hasPrevDirection,
          drawTile = true
        )
        isFirstSegment = false
      of Vibe:
        discard

    # Draw final queued objective.
    if agentObjectives.hasKey(agentId):
      let objectives = agentObjectives[agentId]
      if objectives.len > 0:
        let objective = objectives[^1]
        if objective.kind in {Move, Bump}:
          px.drawSprite(
            "objects/selection",
            objective.pos.ivec2 * TileSize
          )


proc drawSelection*() {.measure.} =
  # Draw selected.
  if selected != nil:
    px.drawSprite(
      "objects/selection",
      (selected.smoothPos * TileSize.float32).ivec2,
    )

proc drawPolicyTarget*() {.measure.} =
  ## Draw the policy target highlight and a path from the selected agent to that target.
  if not isSome(policyTarget):
    return
  if selected.isNil or not selected.isAgent:
    return

  let
    targetPos = get(policyTarget)
    agentPos = selected.location.at(step).xy.ivec2
    greenTint = rgbx(100, 255, 100, 200)
    dx = abs(targetPos.x - agentPos.x)
    dy = abs(targetPos.y - agentPos.y)
    sx = if agentPos.x < targetPos.x: 1.int32 else: -1.int32
    sy = if agentPos.y < targetPos.y: 1.int32 else: -1.int32

  var
    err = dx - dy
    x = agentPos.x
    y = agentPos.y
    first = true

  while true:
    if not first and (x != targetPos.x or y != targetPos.y):
      px.drawSprite(
        "agents/path",
        ivec2(x, y) * TileSize,
        greenTint
      )
    first = false

    if x == targetPos.x and y == targetPos.y:
      break

    let e2 = 2 * err
    if e2 > -dy:
      err -= dy
      x += sx
    if e2 < dx:
      err += dx
      y += sy

  px.drawSprite(
    "objects/selection",
    targetPos * TileSize,
    greenTint
  )

proc applyOrientationOffset*(x: int, y: int, orientation: int): (int, int) =
  case orientation
  of 0:
    return (x, y - 1)
  of 1:
    return (x, y + 1)
  of 2:
    return (x - 1, y)
  of 3:
    return (x + 1, y)
  else:
    return (x, y)

proc drawTerrain*() {.measure.} =
  terrains.drawTerrain(getProjectionView(), px, pxMini)

proc drawMask*() {.measure.} =
  terrains.drawMask(getProjectionView())

proc rebuildSplats*() =
  terrains.rebuildSplats()

proc resetTerrainCaches*() =
  terrains.resetTerrainCaches()

proc drawSplats*() {.measure.} =
  terrains.drawSplats(getProjectionView(), px)

proc drawMaskedSplatComposite*() {.measure.} =
  terrains.drawMaskedSplatComposite(getProjectionView(), px)

proc drawObjectPips*() {.measure.} =
  ## Draw the pips for the objects on the minimap using the mini pixelator.

  for obj in replay.objects:
    if obj.typeName == "wall":
      continue
    if not obj.alive.at:
      continue
    let resolvedAsset = replay.resolveRenderAsset(obj, step)
    var pipName =
      if resolvedAsset.len > 0:
        "minimap/" & resolvedAsset
      else:
        "minimap/" & obj.renderName
    if pipName notin pxMini:
      pipName = "minimap/" & obj.typeName
    if pipName notin pxMini:
      pipName = "minimap/" & stripTeamSuffix(obj.typeName)
    if pipName notin pxMini:
      pipName = "minimap/" & stripTeamPrefix(obj.typeName)
    if pipName notin pxMini:
      pipName = "minimap/unknown"
    let loc = obj.location.at(step).xy
    let normalized = normalizeTypeName(obj.typeName)
    let pipTint = if normalized in ["junction", "agent"]:
      getTeamColor(getEntityTeamIndex(obj))
    else:
      WhiteTint
    pxMini.drawSprite(
      pipName,
      loc.ivec2 * MiniTileSize,
      pipTint
    )
    if selected != nil and obj.id == selected.id:
      pxMini.drawSprite(
        "minimap/selection",
        loc.ivec2 * MiniTileSize,
        WhiteTint
      )

proc drawWorldMini*() {.measure.} =
  ## Draw the world map at minimap zoom level using pxMini.
  drawTerrain()
  drawMaskedSplatComposite()
  drawAoeMaps()

  # Draw heatmap if enabled.
  if settings.showHeatmap:
    ensureHeatmapReady()

    if worldHeatmap != nil:
      # Update heatmap texture if step changed.
      updateTexture(worldHeatmap, step)
      # Draw heatmap overlay.
      let maxHeat = worldHeatmap.getMaxHeat(step).float32
      draw(
        worldHeatmap,
        getProjectionView(),
        vec2(replay.mapSize[0].float32, replay.mapSize[1].float32),
        maxHeat
      )

  drawMinimapPipePips(pxMini)
  drawObjectPips()

  pxMini.flush(getProjectionView() * scale(vec3(Mts, Mts, 1.0f)))

  # Overlays (drawn after minimap pips so fog/range can cover icons).
  if settings.showFogOfWar:
    drawFogOfWar()
  if settings.showVisualRange:
    drawVisualRanges()

proc keepSelectionInView*(zoomInfo: ZoomInfo) =
  ## Keep selected inside a zoom-aware safe margin.
  if selected.isNil:
    return

  let
    rectW = zoomInfo.rect.w.float32
    rectH = zoomInfo.rect.h.float32
    z = zoomInfo.zoom * zoomInfo.zoom
  if rectW <= 0 or rectH <= 0 or z <= 0:
    return

  let
    selectionPos = selected.smoothPos
    maxMarginPx = FollowMarginMaxWorldTiles * z
    marginX = min(rectW * FollowMarginScreenFraction, maxMarginPx)
    marginY = min(rectH * FollowMarginScreenFraction, maxMarginPx)
    minX = marginX
    maxX = rectW - marginX
    minY = marginY
    maxY = rectH - marginY - 200.0f

  var
    selectionScreenX = selectionPos.x * z + zoomInfo.pos.x
    selectionScreenY = selectionPos.y * z + zoomInfo.pos.y
    moved = false

  if selectionScreenX < minX:
    zoomInfo.pos.x = minX - selectionPos.x * z
    moved = true
  elif selectionScreenX > maxX:
    zoomInfo.pos.x = maxX - selectionPos.x * z
    moved = true

  if selectionScreenY < minY:
    zoomInfo.pos.y = minY - selectionPos.y * z
    moved = true
  elif selectionScreenY > maxY:
    zoomInfo.pos.y = maxY - selectionPos.y * z
    moved = true

  if moved:
    clampMapPan(zoomInfo)

proc drawWorldMain*() {.measure.} =
  ## Draw the world map.

  drawStarfield()
  drawTerrain()
  drawMaskedSplatComposite()
  drawAoeMaps()
  drawPipegrids(px)

  # Draw heatmap if enabled.
  if settings.showHeatmap:
    measurePush("drawWorldMain.heatmap")
    ensureHeatmapReady()

    if worldHeatmap != nil:
      # Update heatmap texture if step changed.
      updateTexture(worldHeatmap, step)
      # Draw heatmap overlay.
      let maxHeat = worldHeatmap.getMaxHeat(step).float32
      worldHeatmap.draw(
        getProjectionView(),
        vec2(replay.mapSize[0].float32, replay.mapSize[1].float32),
        maxHeat
      )
    measurePop()

  drawTrajectory()

  drawObjects()
  drawSelection()
  drawPolicyTarget()

  drawAgentDecorations()
  drawPlannedPath()
  drawMovePreview()

  px.flush(getProjectionView() * scale(vec3(Ts, Ts, 1.0f)))

  if settings.showVisualRange:
    drawVisualRanges()
  if settings.showFogOfWar:
    drawFogOfWar()
  if settings.showGrid:
    drawGrid()

proc updateMinZoom*(zoomInfo: ZoomInfo) =
  ## Recompute minZoom so the map cannot be zoomed out beyond ZoomOutMargin times its full-fit size.
  if replay.isNil:
    return
  let rectW = zoomInfo.rect.w.float32
  let rectH = zoomInfo.rect.h.float32
  if rectW <= 0 or rectH <= 0:
    return
  let
    mapW = max(0.001f, replay.mapSize[0].float32)
    mapH = max(0.001f, replay.mapSize[1].float32)
    fitZoom = sqrt(min(rectW / mapW, rectH / mapH))
  zoomInfo.minZoom = fitZoom / sqrt(ZoomOutMargin)

proc fitFullMap*(zoomInfo: ZoomInfo) =
  ## Set zoom and pan so the full map fits in the panel.
  if replay.isNil:
    return
  let rectW = zoomInfo.rect.w.float32
  let rectH = zoomInfo.rect.h.float32
  if rectW <= 0 or rectH <= 0:
    return
  let
    mapMinX = -0.5f
    mapMinY = -0.5f
    mapMaxX = replay.mapSize[0].float32 - 0.5f
    mapMaxY = replay.mapSize[1].float32 - 0.5f
    mapW = max(0.001f, mapMaxX - mapMinX)
    mapH = max(0.001f, mapMaxY - mapMinY)
  let zoomScale = min(rectW / mapW, rectH / mapH)
  zoomInfo.zoom = clamp(sqrt(zoomScale), zoomInfo.minZoom, zoomInfo.maxZoom)
  let
    cx = (mapMinX + mapMaxX) / 2.0f
    cy = (mapMinY + mapMaxY) / 2.0f
    z = zoomInfo.zoom * zoomInfo.zoom
  zoomInfo.pos.x = rectW / 2.0f - cx * z
  zoomInfo.pos.y = rectH / 2.0f - cy * z

proc fitVisibleMap*(zoomInfo: ZoomInfo) =
  ## Set zoom and pan so the visible area (union of all agent vision ranges) fits in the panel.
  if replay.isNil:
    return

  if replay.agents.len == 0:
    fitFullMap(zoomInfo)
    return

  let rectSize = vec2(zoomInfo.rect.w.float32, zoomInfo.rect.h.float32)

  # Calculate the union of all agent vision areas.
  var
    minPos = vec2(float32.high, float32.high)
    maxPos = vec2(float32.low, float32.low)

  for agent in replay.agents:
    if agent.location.len == 0:
      continue
    let
      pos = agent.location.at(step).xy.vec2
      visionRadius = agent.visionSize.float32 / 2.0f
      agentMin = pos - vec2(visionRadius, visionRadius)
      agentMax = pos + vec2(visionRadius, visionRadius)

    minPos = min(minPos, agentMin)
    maxPos = max(maxPos, agentMax)

  # Ensure we have valid bounds with reasonable size, otherwise fall back to full map
  let size = maxPos - minPos
  if size.x < 1.0f or size.y < 1.0f:
    fitFullMap(zoomInfo)
    return

  let
    visibleSize = maxPos - minPos
    zoomScale = min(rectSize.x / visibleSize.x, rectSize.y / visibleSize.y)
    center = (minPos + maxPos) / 2.0f
    zoom = clamp(sqrt(zoomScale), zoomInfo.minZoom, zoomInfo.maxZoom)

  zoomInfo.zoom = zoom
  zoomInfo.pos = rectSize / 2.0f - center * (zoom * zoom)

proc adjustPanelForResize*(zoomInfo: ZoomInfo) =
  ## Adjust pan and zoom when panel resizes to show the same portion of the map.
  let currentSize = vec2(zoomInfo.rect.w.float32, zoomInfo.rect.h.float32)

  # Skip if this is the first time or no change
  if previousPanelSize.x <= 0 or previousPanelSize.y <= 0 or currentSize == previousPanelSize:
    previousPanelSize = currentSize
    return

  # Calculate current center point in world coordinates using previous panel size
  let
    oldRectW = previousPanelSize.x
    oldRectH = previousPanelSize.y
    rectW = zoomInfo.rect.w.float32
    rectH = zoomInfo.rect.h.float32
    z = zoomInfo.zoom * zoomInfo.zoom
    centerX = (oldRectW / 2.0f - zoomInfo.pos.x) / z
    centerY = (oldRectH / 2.0f - zoomInfo.pos.y) / z

  # Adjust zoom with square root of proportional scaling - moderate the zoom increase
  # when panel gets bigger to keep map elements reasonably sized
  let
    oldDiagonal = sqrt(oldRectW * oldRectW + oldRectH * oldRectH)
    newDiagonal = sqrt(rectW * rectW + rectH * rectH)
    zoomFactor = sqrt(newDiagonal / oldDiagonal)

  zoomInfo.zoom = clamp(zoomInfo.zoom * zoomFactor, zoomInfo.minZoom, zoomInfo.maxZoom)

  # Recalculate pan to keep the same center point
  let newZ = zoomInfo.zoom * zoomInfo.zoom
  zoomInfo.pos.x = rectW / 2.0f - centerX * newZ
  zoomInfo.pos.y = rectH / 2.0f - centerY * newZ

  # Update previous size
  previousPanelSize = currentSize

proc drawWorldMap*(zoomInfo: ZoomInfo) {.measure.} =
  ## Draw the world map.

  if replay == nil or replay.mapSize[0] == 0 or replay.mapSize[1] == 0:
    # Replay has not been loaded yet.
    return

  if needsInitialFit:
    # initial fit needs to happen after the the panel is set up to the correct size and the replay is loaded
    fitVisibleMap(zoomInfo)
    # fitFullMap(zoomInfo)
    needsInitialFit = false

  ## Draw the world map.
  if settings.lockFocus:
    keepSelectionInView(zoomInfo)

  zoomInfo.beginPanAndZoom()

  if zoomInfo.hasMouse:
    useSelections(zoomInfo)

  agentControls()

  if zoomInfo.zoom < MiniViewZoomThreshold:
    drawStarfield()
    drawWorldMini()
  else:
    drawWorldMain()

  zoomInfo.endPanAndZoom()
