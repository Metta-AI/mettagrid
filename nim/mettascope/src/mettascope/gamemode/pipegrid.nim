import
  std/[algorithm, heapqueue, math, tables, sets],
  chroma, vmath, silky,
  ../[common, replays, colors],
  ./[team, pixelator]

const
  TileSize = 128
  MiniTileSize = 16
  PipeTurnPenalty = 0.75f
  PipeDistanceWeight = 1.0f
  PipeMaxRewiresPerTeamPerStep = 2
  PipeMaxNewEdgesPerTeamPerStep = 3
  PipeRootDepthPenalty = 1
  PipeDisconnectedParentPenalty = 6
  PipeRouteDirections = [ivec2(0, -1), ivec2(1, 0), ivec2(0, 1), ivec2(-1, 0)]

type
  PipeDirection = enum
    Invalid, North, East, South, West

  PipeNodeRole = enum
    NoRole, Junction, Hub

  PipeNetworkKey = int

  PipeJunction = object
    id: int
    pos: IVec2
    range: float32
    isHub: bool

  PipeRouteNode = object
    pos: IVec2
    gCost: int
    fCost: int

  PipeEdge = object
    aId: int
    bId: int
    path: seq[IVec2]

  PipeNetworkState = ref object
    edges: seq[PipeEdge]
    nodePosById: Table[int, IVec2]

  PipeTileSpriteCommand = object
    tile: IVec2
    sprite: string
    fallback: string

  PipeMiniPipCommand = object
    tile: IVec2
    tint: ColorRGBX

  PipeRenderNetworkCache = object
    worldCommands: seq[PipeTileSpriteCommand]
    miniCommands: seq[PipeMiniPipCommand]

var
  pipeNetworks: Table[PipeNetworkKey, PipeNetworkState]
  pipeNetworkHistory: seq[Table[PipeNetworkKey, PipeNetworkState]]
  pipeNetworkMaxComputedStep: int = -1
  lastPipeNetworkStep: int = -1
  pipeNodeRole: seq[PipeNodeRole]  # Indexed by entity id.
  pipeNodeIdsCached: bool = false
  pipeRenderCacheByNetwork: Table[PipeNetworkKey, PipeRenderNetworkCache]
  pipeRenderCacheOrder: seq[PipeNetworkKey]
  pipeRenderCachedStep: int = -1

proc pipeEdgeKey(aId: int, bId: int): int64 =
  ## Build a stable key for an undirected pipe edge.
  let lo = min(aId, bId).int64
  let hi = max(aId, bId).int64
  (lo shl 32) or hi

proc pipeTileKey(pos: IVec2): int64 =
  ## Pack a tile coordinate into a hash-friendly key.
  (int64(pos.x) shl 32) xor (int64(pos.y) and 0xFFFF_FFFF'i64)

proc pipeTileFromKey(key: int64): IVec2 =
  ## Unpack a tile key into a tile coordinate.
  ivec2((key shr 32).int32, (key and 0xFFFF_FFFF'i64).int32)

proc manhattanDistance(a: IVec2, b: IVec2): int =
  ## Return Manhattan distance in tiles.
  abs(a.x.int - b.x.int) + abs(a.y.int - b.y.int)

proc pipeConnectRange(a: PipeJunction, b: PipeJunction): float32 =
  ## 2x maximum node AoE radius.
  max(a.range, b.range) * 2.0f

proc canPipeNodesConnect(a: PipeJunction, b: PipeJunction): bool =
  ## Return true when nodes are within connection range.
  let connectRange = pipeConnectRange(a, b)
  if connectRange <= 0.0f:
    return false
  let
    dx = (b.pos.x - a.pos.x).float32
    dy = (b.pos.y - a.pos.y).float32
    distance = sqrt(dx * dx + dy * dy)
  distance <= connectRange + 1e-3f

proc directionBetween(fromPos: IVec2, toPos: IVec2): PipeDirection =
  ## Return cardinal direction from one tile to another.
  if toPos.x > fromPos.x:
    return East
  if toPos.x < fromPos.x:
    return West
  if toPos.y > fromPos.y:
    return South
  if toPos.y < fromPos.y:
    return North
  Invalid

proc pipeDirectionDrawOrder(): array[4, PipeDirection] =
  ## Return a stable draw order for cardinal directions.
  [North, East, South, West]

proc pipeDirMask(dir: PipeDirection): uint8 =
  ## Convert a cardinal direction to a bitmask.
  case dir
  of North:
    1'u8
  of East:
    2'u8
  of South:
    4'u8
  of West:
    8'u8
  else:
    0'u8

proc pipeDirCount(mask: uint8): int =
  ## Count how many cardinal directions are set in a bitmask.
  if (mask and pipeDirMask(North)) != 0'u8:
    inc result
  if (mask and pipeDirMask(East)) != 0'u8:
    inc result
  if (mask and pipeDirMask(South)) != 0'u8:
    inc result
  if (mask and pipeDirMask(West)) != 0'u8:
    inc result

proc pipeNthDirection(mask: uint8, idx: int): PipeDirection =
  ## Return the idx-th direction in stable draw order.
  var at = 0
  for dir in pipeDirectionDrawOrder():
    if (mask and pipeDirMask(dir)) == 0'u8:
      continue
    if at == idx:
      return dir
    inc at
  Invalid

proc pipegridSpriteName(prevDir: PipeDirection, nextDir: PipeDirection): string =
  ## Resolve a pipegrid sprite name from incoming/outgoing directions.
  let
    a = if prevDir == Invalid: nextDir else: prevDir
    b = if nextDir == Invalid: prevDir else: nextDir
  if (a == East and b == West) or (a == West and b == East):
    return "terrain/pipegrid.ee"
  if (a == North and b == South) or (a == South and b == North):
    return "terrain/pipegrid.nn"
  if a == b:
    case a
    of North:
      return "terrain/pipegrid.nn"
    of East:
      return "terrain/pipegrid.ee"
    of South:
      return "terrain/pipegrid.ss"
    of West:
      return "terrain/pipegrid.ww"
    else:
      return "terrain/pipegrid.nn"
  if (a == East and b == North) or (a == North and b == East):
    return "terrain/pipegrid.se"
  if (a == North and b == West) or (a == West and b == North):
    return "terrain/pipegrid.en"
  if (a == South and b == East) or (a == East and b == South):
    return "terrain/pipegrid.ws"
  if (a == West and b == South) or (a == South and b == West):
    return "terrain/pipegrid.nw"
  "terrain/pipegrid.nn"

proc pipegridStubSpriteName(dir: PipeDirection): string =
  ## Resolve a directional edge-to-center pipe stub.
  case dir
  of North:
    "terrain/pipegrid.end.n"
  of East:
    "terrain/pipegrid.end.e"
  of South:
    "terrain/pipegrid.end.s"
  of West:
    "terrain/pipegrid.end.w"
  else:
    "terrain/pipegrid.end.n"

proc inPipeBounds(pos: IVec2): bool =
  ## Return true when a tile is inside the map bounds.
  pos.x >= 0 and pos.x < replay.mapSize[0] and pos.y >= 0 and pos.y < replay.mapSize[1]

proc pathTurnCount(path: seq[IVec2]): int =
  ## Count 90-degree bends in a tile path.
  if path.len < 3:
    return 0
  var
    prevDx = 0'i32
    prevDy = 0'i32
  for i in 1 ..< path.len:
    let
      dx = path[i].x - path[i - 1].x
      dy = path[i].y - path[i - 1].y
    if i > 1 and (dx != prevDx or dy != prevDy):
      inc result
    prevDx = dx
    prevDy = dy

proc addPathToOccupied(path: seq[IVec2], occupied: var HashSet[int64], allowed: HashSet[int64]) =
  ## Add internal non-junction path tiles to occupancy set.
  if path.len < 3:
    return
  for i in 1 ..< path.high:
    let key = pipeTileKey(path[i])
    if key in allowed:
      continue
    occupied.incl(key)

proc sortedSetIds(ids: HashSet[int]): seq[int] =
  ## Convert a hash set to a stable, sorted id list.
  for id in ids:
    result.add(id)
  result.sort(proc(a, b: int): int = cmp(a, b))

proc buildPipeDepthsFromRoot(
  rootId: int,
  adjacency: Table[int, seq[int]],
  connected: HashSet[int]
): Table[int, int] =
  ## Compute BFS depth from root for each connected node.
  result = initTable[int, int]()
  if rootId notin connected:
    return
  var
    queue = @[rootId]
    at = 0
  result[rootId] = 0
  while at < queue.len:
    let current = queue[at]
    inc at
    let currentDepth = result.getOrDefault(current, 0)
    for nxt in adjacency.getOrDefault(current, @[]):
      if nxt notin connected or nxt in result:
        continue
      result[nxt] = currentDepth + 1
      queue.add(nxt)


proc choosePipeRootId(junctions: seq[PipeJunction]): int =
  ## Choose the root hub nearest map center, else nearest junction to map center.
  if junctions.len == 0:
    return -1
  let mapCenter = ivec2((replay.mapSize[0] div 2).int32, (replay.mapSize[1] div 2).int32)
  var
    bestHubId = -1
    bestHubDist = high(int)
  for node in junctions:
    if not node.isHub:
      continue
    let d = manhattanDistance(node.pos, mapCenter)
    if d < bestHubDist or (d == bestHubDist and (bestHubId < 0 or node.id < bestHubId)):
      bestHubDist = d
      bestHubId = node.id
  if bestHubId >= 0:
    return bestHubId

  var
    bestId = junctions[0].id
    bestDist = manhattanDistance(junctions[0].pos, mapCenter)
  for node in junctions:
    let d = manhattanDistance(node.pos, mapCenter)
    if d < bestDist or (d == bestDist and node.id < bestId):
      bestDist = d
      bestId = node.id
  bestId

proc `<`(a, b: PipeRouteNode): bool =
  ## Min-heap ordering: lowest fCost wins, then lowest gCost, then position.
  if a.fCost != b.fCost: return a.fCost < b.fCost
  if a.gCost != b.gCost: return a.gCost < b.gCost
  if a.pos.y != b.pos.y: return a.pos.y < b.pos.y
  a.pos.x < b.pos.x

proc routePipePath(
  startPos: IVec2,
  goalPos: IVec2,
  blocked: HashSet[int64],
  occupied: HashSet[int64],
  allowed: HashSet[int64]
): seq[IVec2] =
  ## Route a non-overlapping cardinal path between two junction tiles.
  if startPos == goalPos:
    return @[startPos]
  if not inPipeBounds(startPos) or not inPipeBounds(goalPos):
    return @[]

  var
    open = initHeapQueue[PipeRouteNode]()
    cameFrom = initTable[IVec2, IVec2]()
    bestG = initTable[IVec2, int]()
  bestG[startPos] = 0
  open.push(PipeRouteNode(
    pos: startPos,
    gCost: 0,
    fCost: manhattanDistance(startPos, goalPos) * 2
  ))

  while open.len > 0:
    let current = open.pop()
    if current.pos == goalPos:
      var cursor = goalPos
      result = @[cursor]
      while cursor != startPos:
        cursor = cameFrom[cursor]
        result.add(cursor)
      result.reverse()
      return result

    if current.gCost > bestG.getOrDefault(current.pos, high(int)):
      continue

    for dir in PipeRouteDirections:
      let neighbor = current.pos + dir
      if not inPipeBounds(neighbor):
        continue
      let key = pipeTileKey(neighbor)
      if key notin allowed and key in blocked:
        continue
      if key in allowed and neighbor != startPos and neighbor != goalPos:
        # Do not route through intermediate junctions.
        continue

      let
        isOccupied = key in occupied and key notin allowed
        stepCost = if isOccupied: 1 else: 2
      let newG = current.gCost + stepCost
      if newG >= bestG.getOrDefault(neighbor, high(int)):
        continue
      bestG[neighbor] = newG
      cameFrom[neighbor] = current.pos
      let turns = if cameFrom.hasKey(current.pos):
        let prev = cameFrom[current.pos]
        let currentDir = directionBetween(current.pos, neighbor)
        let prevDir = directionBetween(prev, current.pos)
        if currentDir != prevDir: 1 else: 0
      else:
        0
      let turnCost = int(round(PipeTurnPenalty * turns.float32))
      open.push(PipeRouteNode(
        pos: neighbor,
        gCost: newG,
        fCost: newG + turnCost + manhattanDistance(neighbor, goalPos) * 2
      ))
  @[]

proc isValidPipePath(path: seq[IVec2], blocked: HashSet[int64], allowed: HashSet[int64]): bool =
  ## Validate that a path is contiguous and doesn't cross blockers.
  if path.len < 2:
    return false
  for i, tile in path:
    if not inPipeBounds(tile):
      return false
    let key = pipeTileKey(tile)
    if key notin allowed and key in blocked:
      return false
    if i > 0 and i < path.high and key in allowed:
      # Junction tiles are only valid as path endpoints.
      return false
    if i > 0 and manhattanDistance(path[i - 1], tile) != 1:
      return false
  true

proc cachePipeNodeIds() =
  ## Precompute which entity IDs are junctions or hubs once per loaded replay.
  if pipeNodeIdsCached:
    return
  pipeNodeIdsCached = true
  var maxId = 0
  for obj in replay.objects:
    maxId = max(maxId, obj.id)
  pipeNodeRole = newSeq[PipeNodeRole](maxId + 1)
  for obj in replay.objects:
    let normalized = normalizeTypeName(obj.typeName)
    if normalized == "junction":
      pipeNodeRole[obj.id] = Junction
    elif normalized == "hub":
      pipeNodeRole[obj.id] = Hub

proc resetPipegridRenderCache() =
  ## Drop cached draw commands so they are rebuilt for the next frame.
  pipeRenderCacheByNetwork.clear()
  pipeRenderCacheOrder.setLen(0)
  pipeRenderCachedStep = -1

proc resetPipegridState*() =
  ## Reset persistent pipegrid state.
  pipeNetworks.clear()
  pipeNetworkHistory.setLen(0)
  pipeNetworkMaxComputedStep = -1
  lastPipeNetworkStep = -1
  pipeNodeRole.setLen(0)
  pipeNodeIdsCached = false
  resetPipegridRenderCache()

proc clonePipeNetworkState(state: PipeNetworkState): PipeNetworkState =
  ## Deep-copy a team pipe network state.
  result = PipeNetworkState(
    edges: @[],
    nodePosById: initTable[int, IVec2]()
  )
  for edge in state.edges:
    var copiedPath: seq[IVec2] = @[]
    for tile in edge.path:
      copiedPath.add(tile)
    result.edges.add(PipeEdge(
      aId: edge.aId,
      bId: edge.bId,
      path: copiedPath
    ))
  for nodeId, nodePos in state.nodePosById:
    result.nodePosById[nodeId] = nodePos

proc clonePipeNetworks(
  src: Table[PipeNetworkKey, PipeNetworkState]
): Table[PipeNetworkKey, PipeNetworkState] =
  ## Deep-copy all team network states.
  result = initTable[PipeNetworkKey, PipeNetworkState]()
  for networkKey, state in src:
    result[networkKey] = clonePipeNetworkState(state)

proc savePipeNetworkSnapshot(stepIdx: int) =
  ## Store a deep-copied snapshot for the given step.
  if pipeNetworkHistory.len <= stepIdx:
    pipeNetworkHistory.setLen(stepIdx + 1)
  pipeNetworkHistory[stepIdx] = clonePipeNetworks(pipeNetworks)

proc loadPipeNetworkSnapshot(stepIdx: int) =
  ## Restore a deep-copied snapshot for the given step.
  pipeNetworks = clonePipeNetworks(pipeNetworkHistory[stepIdx])

proc updatePipeNetwork(networkKey: PipeNetworkKey, junctions: seq[PipeJunction], blocked: HashSet[int64]) =
  ## Incrementally update one team's pipe network.
  let state = pipeNetworks.mgetOrPut(
    networkKey,
    PipeNetworkState(
      edges: @[],
      nodePosById: initTable[int, IVec2]()
    )
  )
  if junctions.len == 0:
    state.edges.setLen(0)
    state.nodePosById.clear()
    return

  var
    nodeById = initTable[int, PipeJunction]()
    nodeIds = initHashSet[int]()
    junctionTiles = initHashSet[int64]()
  for node in junctions:
    nodeById[node.id] = node
    nodeIds.incl(node.id)
    junctionTiles.incl(pipeTileKey(node.pos))
    state.nodePosById[node.id] = node.pos

  let rootId = choosePipeRootId(junctions)
  if rootId < 0:
    state.edges.setLen(0)
    return

  var
    invalidRemoved = 0
    seenEdgeKeys = initHashSet[int64]()
    occupied = initHashSet[int64]()
    filteredEdges: seq[PipeEdge] = @[]
  for edge in state.edges:
    if edge.aId == edge.bId:
      inc invalidRemoved
      continue
    if edge.aId notin nodeIds or edge.bId notin nodeIds:
      inc invalidRemoved
      continue

    let
      aPos = nodeById[edge.aId].pos
      bPos = nodeById[edge.bId].pos
      aNode = nodeById[edge.aId]
      bNode = nodeById[edge.bId]
    if edge.path.len < 2:
      inc invalidRemoved
      continue
    if not canPipeNodesConnect(aNode, bNode):
      inc invalidRemoved
      continue
    var path = edge.path
    if path[0] == bPos and path[^1] == aPos:
      path.reverse()
    if path[0] != aPos or path[^1] != bPos:
      inc invalidRemoved
      continue
    if not isValidPipePath(path, blocked, junctionTiles):
      inc invalidRemoved
      continue

    let key = pipeEdgeKey(edge.aId, edge.bId)
    if key in seenEdgeKeys:
      continue
    seenEdgeKeys.incl(key)
    filteredEdges.add(PipeEdge(
      aId: edge.aId,
      bId: edge.bId,
      path: path
    ))
    addPathToOccupied(path, occupied, junctionTiles)
  state.edges = filteredEdges

  var
    connected = initHashSet[int]()
    adjacency = initTable[int, seq[int]]()

  proc commitEdge(aId: int, bId: int, path: seq[IVec2]) =
    ## Add a new edge and update adjacency, occupancy, and connected ids.
    state.edges.add(PipeEdge(
      aId: aId,
      bId: bId,
      path: path
    ))
    adjacency.mgetOrPut(aId, @[]).add(bId)
    adjacency.mgetOrPut(bId, @[]).add(aId)
    addPathToOccupied(path, occupied, junctionTiles)
    connected.incl(aId)
    connected.incl(bId)

  connected.incl(rootId)
  for edge in state.edges:
    connected.incl(edge.aId)
    connected.incl(edge.bId)
    adjacency.mgetOrPut(edge.aId, @[]).add(edge.bId)
    adjacency.mgetOrPut(edge.bId, @[]).add(edge.aId)

  var budget = PipeMaxNewEdgesPerTeamPerStep + min(PipeMaxRewiresPerTeamPerStep, invalidRemoved)

  while budget > 0:
    var
      components: seq[seq[int]] = @[]
      seen = initHashSet[int]()
      rootComponentIdx = -1
    let connectedIds = sortedSetIds(connected)
    for id in connectedIds:
      if id in seen:
        continue
      var
        queue = @[id]
        at = 0
        component: seq[int] = @[]
        hasRoot = false
      seen.incl(id)
      while at < queue.len:
        let current = queue[at]
        inc at
        component.add(current)
        if current == rootId:
          hasRoot = true
        for nxt in adjacency.getOrDefault(current, @[]):
          if nxt notin connected or nxt in seen:
            continue
          seen.incl(nxt)
          queue.add(nxt)
      component.sort(proc(a, b: int): int = cmp(a, b))
      components.add(component)
      if hasRoot:
        rootComponentIdx = components.high

    if components.len <= 1:
      break

    var
      bestParent = -1
      bestChild = -1
      bestRank = (high(int), high(int), high(int), high(float32))
      bestPath: seq[IVec2] = @[]

    for ci in 0 ..< components.len:
      for cj in ci + 1 ..< components.len:
        let rootBridgeRank =
          if rootComponentIdx >= 0 and ((ci == rootComponentIdx) xor (cj == rootComponentIdx)):
            0
          else:
            1
        for aId in components[ci]:
          for bId in components[cj]:
            let
              aNode = nodeById[aId]
              bNode = nodeById[bId]
            if not canPipeNodesConnect(aNode, bNode):
              continue
            let candidatePath = routePipePath(
              aNode.pos,
              bNode.pos,
              blocked,
              occupied,
              junctionTiles
            )
            if candidatePath.len < 2:
              continue
            let
              distance = candidatePath.len - 1
              turns = pathTurnCount(candidatePath)
              score = distance.float32 * PipeDistanceWeight + turns.float32 * PipeTurnPenalty
              rank = (rootBridgeRank, distance, turns, score)
            if rank < bestRank:
              bestRank = rank
              bestParent = aId
              bestChild = bId
              bestPath = candidatePath

    if bestParent < 0 or bestPath.len < 2:
      break

    commitEdge(bestParent, bestChild, bestPath)
    dec budget

  var unconnectedIds: seq[int] = @[]
  for node in junctions:
    if node.id in connected:
      continue
    unconnectedIds.add(node.id)
  let rootPos = nodeById[rootId].pos
  unconnectedIds.sort(proc(a, b: int): int =
    let da = manhattanDistance(nodeById[a].pos, rootPos)
    let db = manhattanDistance(nodeById[b].pos, rootPos)
    if da == db: cmp(a, b) else: cmp(da, db)
  )

  var
    rootDepthById = initTable[int, int]()
    rootDepthReady = false

  proc ensureRootDepthById() =
    ## Lazily compute root depths only if attachment scoring needs it.
    if rootDepthReady:
      return
    rootDepthById = buildPipeDepthsFromRoot(rootId, adjacency, connected)
    rootDepthReady = true

  proc chooseBestAttachment(
    nodeId: int,
    parentIds: seq[int],
    skipLinkedParents: bool
  ): tuple[parentId: int, path: seq[IVec2]] =
    result = (parentId: -1, path: @[])
    ensureRootDepthById()
    var bestRank = (high(int), high(int), high(int), high(int), high(float32))
    for parentId in parentIds:
      if parentId == nodeId:
        continue
      if skipLinkedParents and parentId in adjacency.getOrDefault(nodeId, @[]):
        continue
      let
        parentNode = nodeById[parentId]
        node = nodeById[nodeId]
      if not canPipeNodesConnect(parentNode, node):
        continue
      let candidatePath = routePipePath(
        parentNode.pos,
        node.pos,
        blocked,
        occupied,
        junctionTiles
      )
      if candidatePath.len < 2:
        continue
      let
        hubRank = if parentNode.isHub: 0 else: 1
        distance = candidatePath.len - 1
        rootDepth = rootDepthById.getOrDefault(parentId, high(int))
        depthPenalty =
          if rootDepth == high(int):
            PipeDisconnectedParentPenalty
          else:
            rootDepth * PipeRootDepthPenalty
        effectiveDistance = distance + depthPenalty
        turns = pathTurnCount(candidatePath)
        score = distance.float32 * PipeDistanceWeight + turns.float32 * PipeTurnPenalty
        rank = (hubRank, effectiveDistance, distance, turns, score)
      if rank < bestRank:
        bestRank = rank
        result.parentId = parentId
        result.path = candidatePath

  proc attachNodes(ids: seq[int], candidateIds: seq[int], skipLinkedParents: bool) =
    ## Try to attach each node to the best candidate, updating depth along the way.
    for nodeId in ids:
      if adjacency.getOrDefault(nodeId, @[]).len > 0 and skipLinkedParents:
        continue
      let attachment = chooseBestAttachment(nodeId, candidateIds, skipLinkedParents)
      if attachment.parentId < 0 or attachment.path.len < 2:
        continue
      commitEdge(attachment.parentId, nodeId, attachment.path)
      let parentDepth = rootDepthById.getOrDefault(attachment.parentId, high(int))
      if parentDepth != high(int):
        rootDepthById[nodeId] = parentDepth + 1

  attachNodes(unconnectedIds, sortedSetIds(connected), false)

  # Invariant: if a junction can connect to any in-range node, it should not be left dangling.
  var danglingIds: seq[int] = @[]
  for node in junctions:
    if adjacency.getOrDefault(node.id, @[]).len == 0:
      danglingIds.add(node.id)
  danglingIds.sort(proc(a, b: int): int =
    let da = manhattanDistance(nodeById[a].pos, rootPos)
    let db = manhattanDistance(nodeById[b].pos, rootPos)
    if da == db: cmp(a, b) else: cmp(da, db)
  )
  attachNodes(danglingIds, sortedSetIds(nodeIds), true)

  var staleNodeIds: seq[int] = @[]
  for nodeId in state.nodePosById.keys:
    if nodeId notin nodeIds:
      staleNodeIds.add(nodeId)
  for nodeId in staleNodeIds:
    state.nodePosById.del(nodeId)

proc updatePipegridStateForStep(stepIdx: int) =
  ## Incrementally update persistent pipegrid networks for one simulation step.
  var
    allowedTeams = initHashSet[PipeNetworkKey]()
    junctionsByTeam = initTable[PipeNetworkKey, seq[PipeJunction]]()
    blockedTiles = initHashSet[int64]()

  for obj in replay.objects:
    if not obj.alive.at(stepIdx):
      continue
    if obj.isAgent:
      continue
    let pos = obj.location.at(stepIdx).xy
    blockedTiles.incl(pipeTileKey(pos))
    let role = if obj.id < pipeNodeRole.len: pipeNodeRole[obj.id] else: NoRole
    if role == NoRole:
      continue
    let isHub = role == Hub
    let teamIdx = getEntityTeamIndexAtStep(obj, stepIdx)
    if teamIdx < 0:
      continue
    allowedTeams.incl(teamIdx)
    let maxAoeRange = maxInfluenceRange(obj)
    if maxAoeRange <= 0.0f:
      continue
    junctionsByTeam.mgetOrPut(teamIdx, @[]).add(PipeJunction(
      id: obj.id,
      pos: pos,
      range: maxAoeRange,
      isHub: isHub
    ))

  for _, nodes in mpairs(junctionsByTeam):
    nodes.sort(proc(a, b: PipeJunction): int = cmp(a.id, b.id))

  var sortedTeams: seq[PipeNetworkKey] = @[]
  for teamIdx in allowedTeams:
    sortedTeams.add(teamIdx)
  sortedTeams.sort()
  for teamIdx in sortedTeams:
    updatePipeNetwork(teamIdx, junctionsByTeam.getOrDefault(teamIdx, @[]), blockedTiles)

  var staleTeams: seq[PipeNetworkKey] = @[]
  for teamIdx in pipeNetworks.keys:
    if teamIdx notin allowedTeams:
      staleTeams.add(teamIdx)
  for teamIdx in staleTeams:
    pipeNetworks.del(teamIdx)

proc updatePipegridState*() =
  ## Update persistent pipegrids deterministically for the current step.
  if replay.isNil:
    return
  if replay.maxSteps <= 0:
    resetPipegridState()
    return
  cachePipeNodeIds()

  let targetStep = clamp(step, 0, replay.maxSteps - 1)
  if targetStep == lastPipeNetworkStep:
    return

  if targetStep <= pipeNetworkMaxComputedStep:
    loadPipeNetworkSnapshot(targetStep)
    lastPipeNetworkStep = targetStep
    return

  let startStep =
    if pipeNetworkMaxComputedStep >= 0:
      if lastPipeNetworkStep != pipeNetworkMaxComputedStep:
        loadPipeNetworkSnapshot(pipeNetworkMaxComputedStep)
      pipeNetworkMaxComputedStep + 1
    else:
      pipeNetworks.clear()
      0

  for stepIdx in startStep .. targetStep:
    updatePipegridStateForStep(stepIdx)
    savePipeNetworkSnapshot(stepIdx)
    pipeNetworkMaxComputedStep = stepIdx

  lastPipeNetworkStep = targetStep

proc ensurePipegridRenderCache() =
  ## Build per-network draw commands when the pipe state changes.
  if pipeRenderCachedStep == lastPipeNetworkStep:
    return

  pipeRenderCacheByNetwork.clear()
  pipeRenderCacheOrder.setLen(0)
  if pipeNetworks.len == 0:
    pipeRenderCachedStep = lastPipeNetworkStep
    return

  for networkKey in pipeNetworks.keys:
    pipeRenderCacheOrder.add(networkKey)
  pipeRenderCacheOrder.sort()

  for networkKey in pipeRenderCacheOrder:
    let state = pipeNetworks[networkKey]
    var
      junctionTiles = initHashSet[int64]()
      tileDirMasks = initTable[int64, uint8]()
      pipeTiles = initHashSet[int64]()

    proc addTileDir(tile: IVec2, dir: PipeDirection) =
      let dirMask = pipeDirMask(dir)
      if dirMask == 0'u8:
        return
      let key = pipeTileKey(tile)
      tileDirMasks[key] = tileDirMasks.getOrDefault(key, 0'u8) or dirMask

    for _, nodePos in state.nodePosById:
      junctionTiles.incl(pipeTileKey(nodePos))
    for edge in state.edges:
      for tile in edge.path:
        pipeTiles.incl(pipeTileKey(tile))
      if edge.path.len < 2:
        continue
      for i in 0 ..< edge.path.high:
        let
          a = edge.path[i]
          b = edge.path[i + 1]
        addTileDir(a, directionBetween(a, b))
        addTileDir(b, directionBetween(b, a))

    var drawKeys: seq[int64] = @[]
    for key in tileDirMasks.keys:
      drawKeys.add(key)
    drawKeys.sort(proc(a, b: int64): int = cmp(a, b))

    var worldCommands: seq[PipeTileSpriteCommand] = @[]
    for key in drawKeys:
      let
        tile = pipeTileFromKey(key)
        dirMask = tileDirMasks.getOrDefault(key, 0'u8)
      if dirMask == 0'u8:
        continue

      if key in junctionTiles:
        for dir in pipeDirectionDrawOrder():
          if (dirMask and pipeDirMask(dir)) == 0'u8:
            continue
          worldCommands.add(PipeTileSpriteCommand(
            tile: tile,
            sprite: pipegridStubSpriteName(dir),
            fallback: "terrain/pipegrid.end.n"
          ))
        continue

      let dirCount = pipeDirCount(dirMask)
      if dirCount == 1:
        let dir = pipeNthDirection(dirMask, 0)
        worldCommands.add(PipeTileSpriteCommand(
          tile: tile,
          sprite: pipegridSpriteName(dir, dir),
          fallback: "terrain/pipegrid.nn"
        ))
      elif dirCount == 2:
        let dirA = pipeNthDirection(dirMask, 0)
        let dirB = pipeNthDirection(dirMask, 1)
        worldCommands.add(PipeTileSpriteCommand(
          tile: tile,
          sprite: pipegridSpriteName(dirA, dirB),
          fallback: "terrain/pipegrid.nn"
        ))
      elif dirCount == 3:
        let hub =
          if (dirMask and pipeDirMask(South)) != 0'u8:
            South
          elif (dirMask and pipeDirMask(North)) != 0'u8:
            North
          elif (dirMask and pipeDirMask(East)) != 0'u8:
            East
          else:
            West
        var
          branchA = Invalid
          branchB = Invalid
        for dir in pipeDirectionDrawOrder():
          if dir == hub or (dirMask and pipeDirMask(dir)) == 0'u8:
            continue
          if branchA == Invalid:
            branchA = dir
          else:
            branchB = dir
        doAssert branchA != Invalid and branchB != Invalid
        worldCommands.add(PipeTileSpriteCommand(
          tile: tile,
          sprite: pipegridSpriteName(hub, branchA),
          fallback: "terrain/pipegrid.nn"
        ))
        worldCommands.add(PipeTileSpriteCommand(
          tile: tile,
          sprite: pipegridSpriteName(hub, branchB),
          fallback: "terrain/pipegrid.nn"
        ))
      else:
        worldCommands.add(PipeTileSpriteCommand(
          tile: tile,
          sprite: "terrain/pipegrid.nn",
          fallback: "terrain/pipegrid.nn"
        ))
        worldCommands.add(PipeTileSpriteCommand(
          tile: tile,
          sprite: "terrain/pipegrid.ee",
          fallback: "terrain/pipegrid.nn"
        ))

    let teamTint = getTeamColor(networkKey)
    let pipeTint = rgbx(
      ((DarkGray.r.int * 7 + teamTint.r.int * 3) div 10).uint8,
      ((DarkGray.g.int * 7 + teamTint.g.int * 3) div 10).uint8,
      ((DarkGray.b.int * 7 + teamTint.b.int * 3) div 10).uint8,
      255
    )

    var miniKeys: seq[int64] = @[]
    for key in pipeTiles:
      if key in junctionTiles:
        continue
      miniKeys.add(key)
    miniKeys.sort(proc(a, b: int64): int = cmp(a, b))

    var miniCommands: seq[PipeMiniPipCommand] = @[]
    for key in miniKeys:
      miniCommands.add(PipeMiniPipCommand(
        tile: pipeTileFromKey(key),
        tint: pipeTint
      ))

    pipeRenderCacheByNetwork[networkKey] = PipeRenderNetworkCache(
      worldCommands: worldCommands,
      miniCommands: miniCommands
    )

  pipeRenderCachedStep = lastPipeNetworkStep

proc drawPipegrids*(px: Pixelator) {.measure.} =
  ## Draw ground pipegrid tiles for cached team junction render data.
  updatePipegridState()
  ensurePipegridRenderCache()
  if px.isNil or pipeRenderCacheOrder.len == 0:
    return

  for networkKey in pipeRenderCacheOrder:
    if networkKey notin pipeRenderCacheByNetwork:
      continue
    let renderCache = pipeRenderCacheByNetwork[networkKey]
    for cmd in renderCache.worldCommands:
      if cmd.sprite notin px:
        px.drawSprite(cmd.fallback, cmd.tile * TileSize)
      else:
        px.drawSprite(cmd.sprite, cmd.tile * TileSize)

proc drawMinimapPipePips*(pxMini: Pixelator) {.measure.} =
  ## Draw one minimap pip per cached pipe tile, excluding junction tiles.
  updatePipegridState()
  ensurePipegridRenderCache()
  if pxMini.isNil or pipeRenderCacheOrder.len == 0:
    return

  for networkKey in pipeRenderCacheOrder:
    if networkKey notin pipeRenderCacheByNetwork:
      continue
    let renderCache = pipeRenderCacheByNetwork[networkKey]
    for cmd in renderCache.miniCommands:
      pxMini.drawSprite(
        "minimap/dot",
        cmd.tile * MiniTileSize,
        cmd.tint
      )
