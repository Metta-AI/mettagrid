import
  std/[algorithm, math, os, tables, random, json, sets, options, strutils],
  chroma, vmath, windy, silky,
  common, actions, replays,
  pathfinding, tilemap, pixelator, shaderquad, starfield,
  panels, heatmap, heatmapshader, collectives, colors,
  panels/objectpanel

const
  TileSize = 128
  Ts = 1.0 / TileSize.float32 # Tile scale.
  MiniTileSize = 16
  Mts = 1.0 / MiniTileSize.float32 # Mini tile scale for minimap.
  MiniViewZoomThreshold = 4.25f # Show mini/pip overlays at a less zoomed-out level.
  FollowMarginScreenFraction = 0.2f # Keep selected agent within 1/5 of screen edges.
  FollowMarginMaxWorldTiles = 5.0f # Cap edge margin to 5 world tiles when zoomed out.
  ZoomOutMargin = 1.5f # Panel may show at most this multiple of the map's linear extent when zoomed out.

proc centerAt*(zoomInfo: ZoomInfo, entity: Entity)

var
  terrainMap*: TileMap
  visibilityMapStep*: int = -1
  visibilityMapSelectionId*: int = -1
  visibilityMap*: TileMap
  explorationFogMapStep*: int = -1
  explorationFogMapSelectionId*: int = -1
  explorationFogMap*: TileMap

  # AoE tilemap system - one map per collective + one for neutral (dynamic)
  aoeMaps*: seq[TileMap]
  aoeMapStep*: int = -1
  aoeMapHiddenCollectives*: HashSet[int]
  aoeMapSelectionId*: int = -1

  # Allocated coverage map for AoE map generation,
  # so that it's not reallocated every time and cause GC pressure.
  reuseableCoverageMap: seq[bool]
  reuseableOwnershipMap: seq[uint8]
  reuseableFriendlyDistMap: seq[int]
  reuseableEnemyDistMap: seq[int]

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

proc weightedRandomInt*(weights: seq[int]): int =
  ## Return a random integer between 0 and 7, with a weighted distribution.
  var r = rand(sum(weights))
  var acc = 0
  for i, w in weights:
    acc += w
    if r <= acc:
      return i
  doAssert false, "should not happen"

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

proc generateTerrainMap(): TileMap {.measure.} =
  ## Generate a 1024x1024 texture where each pixel is a byte index into the 16x16 tile map.
  let
    width = ceil(replay.mapSize[0].float32 / 32.0f).int * 32
    height = ceil(replay.mapSize[1].float32 / 32.0f).int * 32

  var terrainMap = newTileMap(
    width = width,
    height = height,
    tileSize = 128,
    atlasPath = dataDir / "terrain/blob7x8.png"
  )

  var asteroidMap: seq[bool] = newSeq[bool](width * height)
  # Fill the asteroid map with ground (true).
  for y in 0 ..< height:
    for x in 0 ..< width:
      if x >= replay.mapSize[0] or y >= replay.mapSize[1]:
        # Clear the margins.
        asteroidMap[y * width + x] = true
      else:
        asteroidMap[y * width + x] = false

  # Walk the walls and generate a map of which tiles are present.
  for obj in replay.objects:
    if obj.typeName == "wall":
      let pos = obj.location.at(0)
      asteroidMap[pos.y * width + pos.x] = true


  # Generate the tile edges.
  for i in 0 ..< terrainMap.indexData.len:
    let x = i mod width
    let y = i div width

    proc get(map: seq[bool], x: int, y: int): int =
      if x < 0 or y < 0 or x >= width or y >= height:
        return 1
      if map[y * width + x]:
        return 1
      return 0

    var tile: uint8 = 0
    if asteroidMap[y * width + x]:
      tile = 49
    else:
      let
        pattern = (
          1 * asteroidMap.get(x-1, y-1) + # NW
          2 * asteroidMap.get(x, y-1) + # N
          4 * asteroidMap.get(x+1, y-1) + # NE
          8 * asteroidMap.get(x+1, y) + # E
          16 * asteroidMap.get(x+1, y+1) + # SE
          32 * asteroidMap.get(x, y+1) + # S
          64 * asteroidMap.get(x-1, y+1) + # SW
          128 * asteroidMap.get(x-1, y) # W
        )
      tile = patternToTile[pattern].uint8
    terrainMap.indexData[i] = tile

    # Randomize the solid tiles:
    for i in 0 ..< terrainMap.indexData.len:
      if terrainMap.indexData[i] == 29 or terrainMap.indexData[i] == 18:
        terrainMap.indexData[i] = (50 + weightedRandomInt(@[100, 50, 25, 10, 5, 2])).uint8

  terrainMap.setupGPU()
  return terrainMap

proc rebuildVisibilityMap*(visibilityMap: TileMap) {.measure.} =
  ## Rebuild the visibility map.
  let
    width = visibilityMap.width
    height = visibilityMap.height

  var fogOfWarMap: seq[bool] = newSeq[bool](width * height)
  for y in 0 ..< replay.mapSize[1]:
    for x in 0 ..< replay.mapSize[0]:
      fogOfWarMap[y * width + x] = true

  # Walk the agents and clear the visibility map.
  # If an agent is selected, only show that agent's vision. Otherwise show all agents.
  let agentsToProcess = if selection != nil and selection.isAgent:
    @[selection]
  else:
    replay.agents

  for obj in agentsToProcess:
    let center = ivec2(int32(obj.visionSize div 2), int32(obj.visionSize div 2))
    let pos = obj.location.at
    for i in 0 ..< obj.visionSize:
      for j in 0 ..< obj.visionSize:
        let gridPos = pos.xy + ivec2(int32(i), int32(j)) - center
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
    width = ceil(replay.mapSize[0].float32 / 32.0f).int * 32
    height = ceil(replay.mapSize[1].float32 / 32.0f).int * 32

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
  for y in 0 ..< replay.mapSize[1]:
    for x in 0 ..< replay.mapSize[0]:
      fogOfWarMap[y * width + x] = true

  # Selection-aware source:
  # - one selected agent => only that agent's historical exploration
  # - no selected agent => all agents
  let agentsToProcess = if selection != nil and selection.isAgent:
    @[selection]
  else:
    replay.agents

  # NOTE: We intentionally recompute exploration from history each update.
  # In practice this has been fast enough for current replay sizes, and it keeps
  # memory bounded. Caching explored fog per step/per agent would significantly
  # increase memory use (potentially map-size data across many timesteps).
  for obj in agentsToProcess:
    let center = ivec2(int32(obj.visionSize div 2), int32(obj.visionSize div 2))
    for historyStep in 0 .. step:
      let pos = obj.location.at(historyStep)
      for i in 0 ..< obj.visionSize:
        for j in 0 ..< obj.visionSize:
          let gridPos = pos.xy + ivec2(int32(i), int32(j)) - center
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
    width = ceil(replay.mapSize[0].float32 / 32.0f).int * 32
    height = ceil(replay.mapSize[1].float32 / 32.0f).int * 32

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

proc aoeRadius(aoeConfig: JsonNode): int =
  if "radius" notin aoeConfig:
    return 0
  if aoeConfig["radius"].kind == JInt:
    return aoeConfig["radius"].getInt
  if aoeConfig["radius"].kind == JFloat:
    return aoeConfig["radius"].getFloat.int
  return 0

proc aoeControlsTerritory(aoeConfig: JsonNode): bool =
  if "controls_territory" in aoeConfig and aoeConfig["controls_territory"].kind == JBool:
    return aoeConfig["controls_territory"].getBool
  return false

proc isInfluenceAoeConfig(aoeConfig: JsonNode): bool =
  ## Influence AOEs are fixed circular fields marked as territory-controlling.
  if aoeRadius(aoeConfig) <= 0:
    return false
  return aoeControlsTerritory(aoeConfig)

proc alignmentFilterPasses(filterConfig: JsonNode, sourceCollectiveId: int, observerCollectiveId: int): bool =
  if observerCollectiveId < 0 or observerCollectiveId >= getNumCollectives():
    return false

  let sourceIsFriendly = sourceCollectiveId == observerCollectiveId

  if "collective" in filterConfig and filterConfig["collective"].kind == JString:
    let observerCollectiveName = getCollectiveName(observerCollectiveId)
    if observerCollectiveName.len == 0:
      return false
    return observerCollectiveName == filterConfig["collective"].getStr

  if "alignment" notin filterConfig or filterConfig["alignment"].kind != JString:
    return true

  case filterConfig["alignment"].getStr
  of "same_collective":
    return sourceIsFriendly
  of "different_collective", "not_same_collective":
    return not sourceIsFriendly
  of "aligned":
    return true
  of "unaligned":
    return false
  else:
    return true

proc aoePassesForCollective(aoeConfig: JsonNode, sourceCollectiveId: int, observerCollectiveId: int): bool =
  if observerCollectiveId < 0 or observerCollectiveId >= getNumCollectives():
    return false

  if "filters" notin aoeConfig or aoeConfig["filters"].kind != JArray:
    return true

  for filterConfig in aoeConfig["filters"]:
    if filterConfig.kind != JObject:
      continue

    if "target" in filterConfig and filterConfig["target"].kind == JString and filterConfig["target"].getStr != "target":
      continue

    if "filter_type" in filterConfig and filterConfig["filter_type"].kind == JString:
      if filterConfig["filter_type"].getStr == "alignment":
        if not alignmentFilterPasses(filterConfig, sourceCollectiveId, observerCollectiveId):
          return false

  return true

proc hasInfluenceAoe*(obj: Entity): bool =
  ## Check if an object has influence (territory ownership) AoE in its config.
  if obj.isNil or obj.typeName == "agent":
    return false
  if replay.isNil or replay.mgConfig.isNil:
    return false
  if "game" notin replay.mgConfig:
    return false
  let game = replay.mgConfig["game"]
  if "objects" notin game:
    return false
  let objects = game["objects"]
  if obj.typeName notin objects:
    return false
  let objConfig = objects[obj.typeName]
  if "aoes" notin objConfig:
    return false
  let aoes = objConfig["aoes"]
  if aoes.kind != JObject:
    return false
  for _, aoeConfig in aoes.pairs:
    if isInfluenceAoeConfig(aoeConfig):
      return true
  return false

proc collectiveToSlot*(collectiveId: int): int =
  ## Map a game collective ID to an AoE map slot index.
  ## Collective IDs 0..N-1 map to slots 0..N-1; negative (neutral) maps to the last slot.
  if collectiveId < 0:
    getNumCollectives()
  else:
    collectiveId

proc rebuildAoeMap*(aoeMap: TileMap, slotId: int) {.measure.} =
  ## Rebuild the AoE map for a specific slot (0=Clips, 1=Cogs, 2=Neutral).
  let
    width = aoeMap.width
    height = aoeMap.height
    maxDist = high(int) div 4

  reuseableCoverageMap.setLen(width * height)
  reuseableOwnershipMap.setLen(width * height)
  reuseableFriendlyDistMap.setLen(width * height)
  reuseableEnemyDistMap.setLen(width * height)
  # Ownership encoding:
  # 0 = neutral/no ownership, 1 = friendly ownership, 2 = enemy ownership.
  for i in 0 ..< reuseableCoverageMap.len:
    reuseableCoverageMap[i] = true
    reuseableOwnershipMap[i] = 0'u8
    reuseableFriendlyDistMap[i] = maxDist
    reuseableEnemyDistMap[i] = maxDist

  # Check if this collective is visible (not hidden). Neutral slot is never shown in combined mode.
  let isEnabled = slotId < getNumCollectives() and slotId notin settings.hiddenCollectiveAoe

  proc influenceRangesForSlot(obj: Entity, observerSlot: int): seq[int] =
    ## Return all influence AOE radii that affect this observer slot.
    result = @[]
    if obj.typeName == "agent":
      return
    if replay.isNil or replay.mgConfig.isNil:
      return
    if "game" notin replay.mgConfig:
      return
    let game = replay.mgConfig["game"]
    if "objects" notin game:
      return
    let objects = game["objects"]
    if obj.typeName notin objects:
      return
    let sourceSlot = collectiveToSlot(obj.collectiveId.at(step))
    if sourceSlot >= getNumCollectives():
      return
    let objConfig = objects[obj.typeName]
    if "aoes" notin objConfig:
      return
    let aoes = objConfig["aoes"]
    if aoes.kind != JObject:
      return

    for _, aoeConfig in aoes.pairs:
      if not isInfluenceAoeConfig(aoeConfig):
        continue
      if not aoePassesForCollective(aoeConfig, sourceSlot, observerSlot):
        continue
      let aoeRange = aoeRadius(aoeConfig)
      if aoeRange > 0:
        result.add(aoeRange)

  # Mark AoE coverage directly (used for selected-object mode).
  proc markSelectedCoverage(obj: Entity) =
    if collectiveToSlot(obj.collectiveId.at(step)) != slotId:
      return

    let ranges = influenceRangesForSlot(obj, slotId)
    if ranges.len == 0:
      return

    let pos = obj.location.at(step).xy
    for aoeRange in ranges:
      let rangeSq = aoeRange * aoeRange
      for dx in -aoeRange .. aoeRange:
        for dy in -aoeRange .. aoeRange:
          let
            tx = pos.x + dx.int32
            ty = pos.y + dy.int32
          if dx * dx + dy * dy > rangeSq:
            continue
          if tx >= 0 and tx < width and ty >= 0 and ty < height:
            reuseableOwnershipMap[ty * width + tx] = 1'u8

  # Accumulate nearest distances for friendly/enemy influence (territory-style collapse).
  proc accumulateTerritoryDistances(obj: Entity) =
    let objSlot = collectiveToSlot(obj.collectiveId.at(step))
    if objSlot >= getNumCollectives() or objSlot in settings.hiddenCollectiveAoe:
      return

    let ranges = influenceRangesForSlot(obj, slotId)
    if ranges.len == 0:
      return

    let isFriendly = objSlot == slotId
    let pos = obj.location.at(step).xy

    for aoeRange in ranges:
      let rangeSq = aoeRange * aoeRange
      for dx in -aoeRange .. aoeRange:
        for dy in -aoeRange .. aoeRange:
          let
            tx = pos.x + dx.int32
            ty = pos.y + dy.int32
          let distSq = dx * dx + dy * dy
          if distSq > rangeSq:
            continue
          if tx >= 0 and tx < width and ty >= 0 and ty < height:
            let idx = ty * width + tx
            if isFriendly:
              if distSq < reuseableFriendlyDistMap[idx]:
                reuseableFriendlyDistMap[idx] = distSq
            else:
              if distSq < reuseableEnemyDistMap[idx]:
                reuseableEnemyDistMap[idx] = distSq

  # If a selected object has influence AoE, show only its AoE.
  # Otherwise show combined AoE for all objects in enabled collectives.
  let selectionHasInfluence = selection != nil and hasInfluenceAoe(selection)

  if selectionHasInfluence:
    # Only show the selected object's influence AoE
    if collectiveToSlot(selection.collectiveId.at(step)) == slotId:
      markSelectedCoverage(selection)
  else:
    # Show combined AoE with territory-style collapse:
    # winner per tile by nearest distance, ties are neutral.
    if isEnabled:
      for obj in replay.objects:
        if not obj.alive.at:
          continue
        accumulateTerritoryDistances(obj)

      for i in 0 ..< reuseableOwnershipMap.len:
        let
          friendlyDist = reuseableFriendlyDistMap[i]
          enemyDist = reuseableEnemyDistMap[i]
        if friendlyDist == maxDist and enemyDist == maxDist:
          reuseableOwnershipMap[i] = 0'u8
        elif enemyDist == maxDist:
          reuseableOwnershipMap[i] = 1'u8
        elif friendlyDist == maxDist:
          reuseableOwnershipMap[i] = 2'u8
        elif friendlyDist < enemyDist:
          reuseableOwnershipMap[i] = 1'u8
        elif enemyDist < friendlyDist:
          reuseableOwnershipMap[i] = 2'u8
        else:
          # Midpoint tie => neutral ownership.
          reuseableOwnershipMap[i] = 0'u8

  for i in 0 ..< reuseableCoverageMap.len:
    # Only friendly ownership is rendered in this slot's tinted map.
    reuseableCoverageMap[i] = reuseableOwnershipMap[i] != 1'u8

  # Generate the tile edges using marching squares
  for i in 0 ..< aoeMap.indexData.len:
    let x = i mod width
    let y = i div width

    proc get(map: seq[bool], x: int, y: int): int =
      if x < 0 or y < 0 or x >= width or y >= height:
        return 1  # Outside bounds = no coverage
      if map[y * width + x]:
        return 1
      return 0

    var tile: uint8 = 0
    if reuseableCoverageMap[y * width + x]:
      tile = 49  # Fully covered/empty tile
    else:
      let
        pattern = (
          1 * reuseableCoverageMap.get(x-1, y-1) + # NW
          2 * reuseableCoverageMap.get(x, y-1) + # N
          4 * reuseableCoverageMap.get(x+1, y-1) + # NE
          8 * reuseableCoverageMap.get(x+1, y) + # E
          16 * reuseableCoverageMap.get(x+1, y+1) + # SE
          32 * reuseableCoverageMap.get(x, y+1) + # S
          64 * reuseableCoverageMap.get(x-1, y+1) + # SW
          128 * reuseableCoverageMap.get(x-1, y) # W
        )
      tile = patternToTile[pattern].uint8
    aoeMap.indexData[i] = tile

proc generateAoeMap(slotId: int): TileMap {.measure.} =
  ## Generate an AoE tilemap for a specific slot.
  let
    width = ceil(replay.mapSize[0].float32 / 32.0f).int * 32
    height = ceil(replay.mapSize[1].float32 / 32.0f).int * 32

  var aoeMap = newTileMap(
    width = width,
    height = height,
    tileSize = 64,
    atlasPath = dataDir / "aoe7x8.png"
  )
  aoeMap.rebuildAoeMap(slotId)
  aoeMap.setupGPU()
  return aoeMap

proc updateAoeMap*(aoeMap: TileMap, slotId: int) {.measure.} =
  ## Update the AoE map.
  aoeMap.rebuildAoeMap(slotId)
  aoeMap.updateGPU()

proc initAoeMaps*() {.measure.} =
  ## Initialize all AoE tilemaps (including neutral).
  let count = getNumCollectives() + 1
  aoeMaps = newSeq[TileMap](count)
  for slotId in 0 ..< count:
    aoeMaps[slotId] = generateAoeMap(slotId)
  aoeMapStep = step
  aoeMapHiddenCollectives = settings.hiddenCollectiveAoe

proc updateAoeMaps*() {.measure.} =
  ## Update all AoE tilemaps if step or hidden collectives changed.
  for slotId in 0 ..< aoeMaps.len:
    aoeMaps[slotId].updateAoeMap(slotId)
  aoeMapStep = step
  aoeMapHiddenCollectives = settings.hiddenCollectiveAoe

proc drawAoeMaps*() {.measure.} =
  ## Draw all enabled AoE tilemaps with their respective tint colors.
  ## Only shows influence AoE (not attack AoE).
  ## When a selected object has influence AoE, shows only that object's AoE.
  ## Otherwise shows combined AoE for all enabled collectives.
  if replay.isNil:
    return

  # Initialize maps if needed (empty seq or collective count changed)
  let expectedCount = getNumCollectives() + 1
  if aoeMaps.len != expectedCount:
    initAoeMaps()

  # Check if we need to rebuild (including when selection changes)
  let currentSelectionId = if selection != nil: selection.id else: -1
  let needsRebuild = aoeMapStep != step or
    aoeMapHiddenCollectives != settings.hiddenCollectiveAoe or
    aoeMapSelectionId != currentSelectionId
  if needsRebuild:
    updateAoeMaps()
    aoeMapSelectionId = currentSelectionId

  # Determine if selection has influence AoE to decide what to draw
  let selectionHasInfluence = selection != nil and hasInfluenceAoe(selection)
  let numCollectives = getNumCollectives()

  # Draw each map with its tint color
  for slotId in 0 ..< aoeMaps.len:
    let shouldDraw = if selectionHasInfluence:
      # Only draw the selected object's slot
      collectiveToSlot(selection.collectiveId.at(step)) == slotId
    else:
      # Draw visible collectives; neutral slot is never shown in combined mode
      slotId < numCollectives and slotId notin settings.hiddenCollectiveAoe
    if shouldDraw:
      aoeMaps[slotId].draw(
        getProjectionView(),
        zoom = 2.0f,
        zoomThreshold = 1.5f,
        tint = getCollectiveColor(slotId).color
      )

proc useSelections*(zoomInfo: ZoomInfo) {.measure.} =
  ## Reads the mouse position and selects the thing under it.
  let modifierDown = when defined(macosx):
    window.buttonDown[KeyLeftSuper] or window.buttonDown[KeyRightSuper]
  else:
    window.buttonDown[KeyLeftControl] or window.buttonDown[KeyRightControl]

  let shiftDown = window.buttonDown[KeyLeftShift] or window.buttonDown[KeyRightShift]
  let rDown = window.buttonDown[KeyR]

  # Track mouse down position to distinguish clicks from drags.
  if window.buttonPressed[MouseLeft] and not modifierDown:
    mouseDownPos = window.mousePos.vec2

  # Focus agent on double-click.
  if window.buttonPressed[DoubleClick] and not modifierDown:
    settings.lockFocus = not settings.lockFocus
    if settings.lockFocus and selection != nil:
      centerAt(zoomInfo, selection)

  # Only select on mouse up, and only if we didn't drag much.
  if window.buttonReleased[MouseLeft] and not modifierDown:
    let mouseDragDistance = (window.mousePos.vec2 - mouseDownPos).length
    const maxClickDragDistance = 5.0
    if mouseDragDistance < maxClickDragDistance:
      selection = nil
      let
        mousePos = getTransform().inverse * window.mousePos.vec2
        gridPos = (mousePos + vec2(0.5, 0.5)).ivec2
      if gridPos.x >= 0 and gridPos.x < replay.mapSize[0] and
        gridPos.y >= 0 and gridPos.y < replay.mapSize[1]:
        let obj = getObjectAtLocation(gridPos)

        if obj != nil:
          selectObject(obj)

  if window.buttonPressed[MouseRight] or (window.buttonPressed[MouseLeft] and modifierDown):
    if selection != nil and selection.isAgent:
      let
        mousePos = getTransform().inverse * window.mousePos.vec2
        gridPos = (mousePos + vec2(0.5, 0.5)).ivec2
      if gridPos.x >= 0 and gridPos.x < replay.mapSize[0] and
        gridPos.y >= 0 and gridPos.y < replay.mapSize[1]:
        let startPos = selection.location.at(step).xy

        # Determine if this is a Bump or Move objective.
        let targetObj = getObjectAtLocation(gridPos)
        var objective: Objective
        if targetObj != nil:
          let typeName = targetObj.typeName
          if typeName != "agent" and typeName != "wall":
            # Calculate which quadrant of the tile was clicked.
            # The tile center is at gridPos, and mousePos has fractional parts.
            let
              tileCenterX = gridPos.x.float32
              tileCenterY = gridPos.y.float32
              offsetX = mousePos.x - tileCenterX
              offsetY = mousePos.y - tileCenterY
            # Divide the tile into 4 quadrants at 45-degree angles (diamond shape).
            # If the click is more horizontal than vertical, use left/right approach.
            # If the click is more vertical than horizontal, use top/bottom approach.
            var approachDir: IVec2
            if abs(offsetX) > abs(offsetY):
              # Left or right quadrant.
              if offsetX > 0:
                approachDir = ivec2(1, 0)   # Clicked right, approach from right.
              else:
                approachDir = ivec2(-1, 0)  # Clicked left, approach from left.
            else:
              # Top or bottom quadrant.
              if offsetY > 0:
                approachDir = ivec2(0, 1)   # Clicked bottom, approach from bottom.
              else:
                approachDir = ivec2(0, -1)  # Clicked top, approach from top.
            objective = Objective(kind: Bump, pos: gridPos, approachDir: approachDir, repeat: rDown)
          else:
            objective = Objective(kind: Move, pos: gridPos, approachDir: ivec2(0, 0), repeat: rDown)
        else:
          objective = Objective(kind: Move, pos: gridPos, approachDir: ivec2(0, 0), repeat: rDown)

        if shiftDown:
          # Queue up additional objectives.
          if not agentObjectives.hasKey(selection.agentId) or agentObjectives[selection.agentId].len == 0:
            # No existing objectives, start fresh.
            agentObjectives[selection.agentId] = @[objective]
            recomputePath(selection.agentId, startPos)
          else:
            # Append to existing objectives.
            agentObjectives[selection.agentId].add(objective)
            # Recompute path to include all objectives.
            recomputePath(selection.agentId, startPos)
        else:
          # Replace the entire objective queue.
          agentObjectives[selection.agentId] = @[objective]
          recomputePath(selection.agentId, startPos)

proc inferOrientation*(agent: Entity, step: int): Orientation =
  ## Get the orientation of the agent based on position changes.
  ## Looks backwards from current step to find the last movement.
  if agent.location.len < 2:
    return S
  for i in countdown(step, 1):
    let
      loc0 = agent.location.at(i - 1)
      loc1 = agent.location.at(i)
      dx = loc1.x - loc0.x
      dy = loc1.y - loc0.y
    if dx != 0 or dy != 0:
      # Found a movement - determine direction
      if dx > 0:
        return E
      elif dx < 0:
        return W
      elif dy > 0:
        return S
      else:
        return N
  return S

# stripTeamSuffix, stripTeamPrefix, normalizeTypeName are imported from common

proc smoothPos*(entity: Entity): Vec2 =
  ## Interpolate between floor(stepFloat) and the next step.
  if entity.isNil:
    return vec2(0, 0)
  let
    baseStep = floor(stepFloat).int
    stepFrac = clamp(stepFloat - baseStep.float32, 0.0f, 1.0f)
    pos0 = entity.location.at(baseStep).xy.vec2
    pos1 = entity.location.at(baseStep + 1).xy.vec2
  pos0 + (pos1 - pos0) * stepFrac

proc smoothOrientation*(agent: Entity): Orientation =
  ## Switch orientation halfway through the interpolated move.
  if agent.isNil:
    return S
  let
    baseStep = floor(stepFloat).int
    stepFrac = clamp(stepFloat - baseStep.float32, 0.0f, 1.0f)
    orientation0 = inferOrientation(agent, baseStep)
    orientation1 = inferOrientation(agent, baseStep + 1)
  if stepFrac >= 0.05f:
    orientation1
  else:
    orientation0

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

proc drawObjects*() {.measure.} =
  ## Draw the objects on the map, sorted for correct draw order.

  # Sort: lower Y first (farther away, drawn behind), buildings before agents
  # at same Y, then by object ID ascending.

  # Collect non-wall, alive objects into a sortable list.
  var objects = newSeqOfCap[Entity](replay.objects.len)
  for obj in replay.objects:
    if obj.typeName == "wall":
      continue
    if not obj.alive.at:
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
      # Find last orientation action.
      var agentImage = "agents/" & agentRigName(agent) & "." & smoothOrientation(agent).char

      px.drawSprite(
        agentImage,
        (pos * TileSize.float32 + SpriteOffset.vec2).ivec2
      )

    elif normalizeTypeName(thing.typeName) == "junction":
      let
        collectiveName = getCollectiveName(thing.collectiveId.at(step)).toLowerAscii()
        spriteName =
          if collectiveName.contains("clip") and "objects/junction.clipped1" in px:
            "objects/junction.clipped1"
          elif collectiveName.contains("cog") and "objects/junction.working" in px:
            "objects/junction.working"
          elif "objects/" & thing.typeName in px:
            "objects/" & thing.typeName
          elif "objects/" & stripTeamPrefix(thing.typeName) in px:
            "objects/" & stripTeamPrefix(thing.typeName)
          elif "objects/" & stripTeamSuffix(thing.typeName) in px:
            "objects/" & stripTeamSuffix(thing.typeName)
          else:
            "objects/unknown"
      px.drawSprite(
        spriteName,
        (pos * TileSize.float32 + SpriteOffset.vec2).ivec2
      )

    else:
      let spriteName =
        if "objects/" & thing.typeName in px:
          "objects/" & thing.typeName
        elif "objects/" & stripTeamPrefix(thing.typeName) in px:
          "objects/" & stripTeamPrefix(thing.typeName)
        elif "objects/" & stripTeamSuffix(thing.typeName) in px:
          "objects/" & stripTeamSuffix(thing.typeName)
        else:
          "objects/unknown"
      px.drawSprite(
        spriteName,
        (pos * TileSize.float32 + SpriteOffset.vec2).ivec2
      )

proc drawVisualRanges*(alpha = 0.5) {.measure.} =
  ## Draw the visual ranges of the selected agent.

  if visibilityMap == nil:
    visibilityMapStep = step
    visibilityMapSelectionId = if selection != nil: selection.id else: -1
    visibilityMap = generateVisibilityMap()

  let
    currentSelectionId = if selection != nil: selection.id else: -1
    needsRebuild = visibilityMapStep != step or visibilityMapSelectionId != currentSelectionId

  if needsRebuild:
    visibilityMapStep = step
    visibilityMapSelectionId = currentSelectionId
    visibilityMap.updateVisibilityMap()

  visibilityMap.draw(
    getProjectionView(),
    zoom = 2.0f,
    zoomThreshold = 1.5f,
    tint = color(0, 0, 0, alpha)
  )

proc drawFogOfWar*() {.measure.} =
  ## Draw exploration fog of war.
  if explorationFogMap == nil:
    explorationFogMapStep = step
    explorationFogMapSelectionId = if selection != nil: selection.id else: -1
    explorationFogMap = generateExplorationFogMap()

  let
    currentSelectionId = if selection != nil: selection.id else: -1
    needsRebuild = explorationFogMapStep != step or explorationFogMapSelectionId != currentSelectionId

  if needsRebuild:
    explorationFogMapStep = step
    explorationFogMapSelectionId = currentSelectionId
    explorationFogMap.updateExplorationFogMap()

  explorationFogMap.draw(
    getProjectionView(),
    zoom = 2.0f,
    zoomThreshold = 1.5f,
    tint = color(0, 0, 0, 1.0)
  )

proc drawTrajectory*() {.measure.} =
  ## Draw the trajectory of the selected object, with footprints or a future arrow.
  if selection != nil and selection.location.len > 1:
    var prevDirection = S
    for i in 1 ..< replay.maxSteps:
      let
        loc0 = selection.location.at(i - 1)
        loc1 = selection.location.at(i)
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
  # Draw health and energy bars, and frozen status.
  const
    MaxHp = 100
    MaxEnergy = 20
    NumPips = 10
  let prevStep = max(0, step - 1)
  for agent in replay.agents:
    if not agent.alive.at:
      continue
    let pos = (agent.smoothPos * TileSize.float32).ivec2
    let tint = getCollectiveColor(agent.collectiveId.at(step))
    # HP bar - large pips, colored by collective
    let hp = getInventoryItem(agent, "hp")
    let hpPrev = getInventoryItem(agent, "hp", prevStep)
    drawBar(ivec2(pos.x, pos.y - 68), tint, NumPips, MaxHp, hp, hpPrev, LargePip)
    # Energy bar - medium pips, yellow
    let energy = getInventoryItem(agent, "energy")
    let energyPrev = getInventoryItem(agent, "energy", prevStep)
    drawBar(ivec2(pos.x, pos.y - 61), colors.Yellow, NumPips, MaxEnergy, energy, energyPrev, MediumPip)

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

proc drawPlannedPath*() {.measure.} =
  ## Draw the planned paths for all agents.
  ## Only show paths when in realtime mode and viewing the latest step.
  if playMode != Realtime or step != replay.maxSteps - 1:
    return
  for agentId, pathActions in agentPaths:
    if pathActions.len == 0:
      continue

    # Get agent's current position.
    let agent = getAgentById(agentId)
    var currentPos = agent.location.at(step).xy

    for action in pathActions:
      if action.kind != Move:
        continue
      # Draw arrow from current position to target position.
      let
        pos0 = currentPos
        pos1 = action.pos
        dx = pos1.x - pos0.x
        dy = pos1.y - pos0.y

      var rotation: float32 = 0
      if dx > 0 and dy == 0:
        rotation = 0
      elif dx < 0 and dy == 0:
        rotation = Pi
      elif dx == 0 and dy > 0:
        rotation = -Pi / 2
      elif dx == 0 and dy < 0:
        rotation = Pi / 2

      px.drawSprite(
        "agents/path",
        pos0.ivec2 * TileSize
      )
      currentPos = action.pos

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

      # Draw approach arrows for bump objectives.
      for objective in objectives:
        if objective.kind == Bump and (objective.approachDir.x != 0 or objective.approachDir.y != 0):
          let approachPos = ivec2(objective.pos.x + objective.approachDir.x, objective.pos.y + objective.approachDir.y)
          let offset = vec2(-objective.approachDir.x.float32 * 0.35, -objective.approachDir.y.float32 * 0.35)
          var rotation: float32 = 0
          if objective.approachDir.x > 0:
            rotation = Pi / 2
          elif objective.approachDir.x < 0:
            rotation = -Pi / 2
          elif objective.approachDir.y > 0:
            rotation = 0
          elif objective.approachDir.y < 0:
            rotation = Pi
          px.drawSprite(
            "agents/arrow",
            approachPos.ivec2 * TileSize + offset.ivec2
          )

proc drawSelection*() {.measure.} =
  # Draw selection.
  if selection != nil:
    px.drawSprite(
      "objects/selection",
      (selection.smoothPos * TileSize.float32).ivec2,
    )

proc drawPolicyTarget*() {.measure.} =
  ## Draw the policy target highlight and a path from the selected agent to that target.
  if not isSome(policyTarget):
    return
  if selection.isNil or not selection.isAgent:
    return

  let
    targetPos = get(policyTarget)
    agentPos = selection.location.at(step).xy.ivec2
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
  ## Draw the terrain, space and asteroid tiles using the terrainMap tilemap.
  if terrainMap == nil:
    terrainMap = generateTerrainMap()
    px = newPixelator(
      dataDir / "atlas.png",
      dataDir / "atlas.json"
    )
    pxMini = newPixelator(
      dataDir / "atlas_mini.png",
      dataDir / "atlas_mini.json"
    )

  terrainMap.draw(getProjectionView(), 2.0f, 1.5f)

proc drawObjectPips*() {.measure.} =
  ## Draw the pips for the objects on the minimap using the mini pixelator.
  ## Junction pips are colored by their collective.
  for obj in replay.objects:
    if obj.typeName == "wall":
      continue
    if not obj.alive.at:
      continue
    var pipName = "minimap/" & obj.typeName
    if pipName notin pxMini:
      pipName = "minimap/" & stripTeamSuffix(obj.typeName)
    if pipName notin pxMini:
      pipName = "minimap/" & stripTeamPrefix(obj.typeName)
    if pipName notin pxMini:
      pipName = "minimap/unknown"
    let loc = obj.location.at(step).xy
    # Color agent and junction pips by collective (everything else keeps default white)
    let normalized = normalizeTypeName(obj.typeName)
    let pipTint = if normalized in ["junction", "agent"]:
      getCollectiveColor(obj.collectiveId.at(step))
    else:
      WhiteTint
    pxMini.drawSprite(
      pipName,
      loc.ivec2 * MiniTileSize,
      pipTint
    )

proc drawWorldMini*() {.measure.} =
  ## Draw the world map at minimap zoom level using pxMini.
  drawTerrain()
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

  drawObjectPips()

  pxMini.flush(getProjectionView() * scale(vec3(Mts, Mts, 1.0f)))

  # Overlays (drawn after minimap pips so fog/range can cover icons).
  if settings.showFogOfWar:
    drawFogOfWar()
  if settings.showVisualRange:
    drawVisualRanges()

proc centerAt*(zoomInfo: ZoomInfo, entity: Entity) =
  ## Center the map on the given entity.
  if entity.isNil:
    return
  let location = entity.smoothPos
  let rectW = zoomInfo.rect.w.float32
  let rectH = zoomInfo.rect.h.float32
  if rectW <= 0 or rectH <= 0:
    return
  let z = zoomInfo.zoom * zoomInfo.zoom
  zoomInfo.pos.x = rectW / 2.0f - location.x * z
  zoomInfo.pos.y = rectH / 2.0f - location.y * z

proc keepSelectedAgentInView*(zoomInfo: ZoomInfo) =
  ## Keep selected agent inside a zoom-aware safe margin.
  if selection.isNil or not selection.isAgent:
    return

  let
    rectW = zoomInfo.rect.w.float32
    rectH = zoomInfo.rect.h.float32
    z = zoomInfo.zoom * zoomInfo.zoom
  if rectW <= 0 or rectH <= 0 or z <= 0:
    return

  let
    agentPos = selection.smoothPos
    maxMarginPx = FollowMarginMaxWorldTiles * z
    marginX = min(rectW * FollowMarginScreenFraction, maxMarginPx)
    marginY = min(rectH * FollowMarginScreenFraction, maxMarginPx)
    minX = marginX
    maxX = rectW - marginX
    minY = marginY
    maxY = rectH - marginY

  var
    agentScreenX = agentPos.x * z + zoomInfo.pos.x
    agentScreenY = agentPos.y * z + zoomInfo.pos.y
    moved = false

  if agentScreenX < minX:
    zoomInfo.pos.x = minX - agentPos.x * z
    moved = true
  elif agentScreenX > maxX:
    zoomInfo.pos.x = maxX - agentPos.x * z
    moved = true

  if agentScreenY < minY:
    zoomInfo.pos.y = minY - agentPos.y * z
    moved = true
  elif agentScreenY > maxY:
    zoomInfo.pos.y = maxY - agentPos.y * z
    moved = true

  if moved:
    clampMapPan(zoomInfo)

proc drawWorldMain*() {.measure.} =
  ## Draw the world map.

  drawStarfield()
  drawTerrain()
  drawAoeMaps()

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
    centerAt(zoomInfo, selection)

  keepSelectedAgentInView(zoomInfo)

  zoomInfo.beginPanAndZoom()

  if zoomInfo.hasMouse:
    useSelections(zoomInfo)

  agentControls()

  if zoomInfo.zoom < MiniViewZoomThreshold:
    drawWorldMini()
  else:
    drawWorldMain()

  zoomInfo.endPanAndZoom()
