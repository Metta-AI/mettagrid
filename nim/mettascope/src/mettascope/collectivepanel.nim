## Collectives panel displays information about each collective (team/faction).
## Shows inventory, buildings, and agents grouped by rig type.

import
  std/[strformat, strutils, tables, algorithm, json],
  silky, silky/atlas, vmath, chroma, bumpy,
  common, panels, replays, aoepanel

const IconSize = 32.0f

proc drawImageScaled(sk: Silky, name: string, pos: Vec2, size: Vec2, color = rgbx(255, 255, 255, 255)) =
  ## Draw an image scaled to a specific size using silky.
  if name notin sk.atlas.entries:
    return
  let uv = sk.atlas.entries[name]
  sk.drawQuad(
    pos,
    size,
    vec2(uv.x.float32, uv.y.float32),
    vec2(uv.width.float32, uv.height.float32),
    color
  )

template smallIconLabel(imageName: string, labelText: string) =
  ## Draw a small icon with a text label, properly aligned.
  ## Icon is drawn at IconSize x IconSize, text is vertically centered.
  let startX = sk.at.x
  let startY = sk.at.y
  sk.at.x += 8  # Indent
  # Draw icon
  if imageName in sk.atlas.entries:
    drawImageScaled(sk, imageName, sk.at, vec2(IconSize, IconSize))
  sk.at.x += IconSize + 6  # Advance past icon + gap
  sk.at.y += 6  # Center text vertically with icon
  text(labelText)
  sk.at.x = startX  # Reset x for next line
  sk.at.y = startY + IconSize + 2  # Move to next line based on icon height

type
  CollectiveStats* = object
    collectiveId*: int
    name*: string
    inventory*: Table[string, int]       ## itemName -> count
    buildingsByType*: Table[string, int] ## typeName -> count
    agentsByRig*: Table[string, int]     ## rigName -> count

proc getCollectiveInventory(collectiveId: int): Table[string, int] =
  ## Get the inventory of a collective from the config.
  result = initTable[string, int]()
  let collectiveConfig = getCollectiveConfig(collectiveId)
  if collectiveConfig.isNil or collectiveConfig.kind != JObject:
    return
  if "inventory" notin collectiveConfig:
    return
  let inventoryConfig = collectiveConfig["inventory"]
  if inventoryConfig.kind != JObject or "initial" notin inventoryConfig:
    return
  let initial = inventoryConfig["initial"]
  if initial.kind != JObject:
    return
  for key, value in initial.pairs:
    if value.kind == JInt:
      result[key] = value.getInt

proc getAgentRigName(agent: Entity): string =
  ## Get the rig of the agent by looking at inventory.
  ## Returns "scout", "miner", "aligner", "scrambler", or "agent" if no rig.
  if agent.inventory.len == 0:
    return "agent"
  for item in agent.inventory.at(step):
    if item.itemId < 0 or item.itemId >= replay.itemNames.len:
      continue
    let itemName = replay.itemNames[item.itemId]
    if itemName in ["scout", "miner", "aligner", "scrambler"]:
      return itemName
  return "agent"

proc getCollectiveStats*(): seq[CollectiveStats] =
  ## Collect statistics for all collectives from the replay.
  result = @[]
  if replay.isNil:
    return

  let numCollectives = getNumCollectives()
  if numCollectives == 0:
    return

  # Initialize stats for each collective.
  for i in 0 ..< numCollectives:
    let collectiveName = getCollectiveName(i)
    var stats = CollectiveStats(
      collectiveId: i,
      name: collectiveName,
      inventory: getCollectiveInventory(i),
      buildingsByType: initTable[string, int](),
      agentsByRig: initTable[string, int]()
    )
    result.add(stats)

  # Iterate all objects and aggregate stats by collective.
  for obj in replay.objects:
    let cid = obj.collectiveId.at(step)
    if cid < 0 or cid >= numCollectives:
      continue

    if obj.isAgent:
      # Count agents by rig type.
      let rigName = getAgentRigName(obj)
      if result[cid].agentsByRig.hasKey(rigName):
        result[cid].agentsByRig[rigName] += 1
      else:
        result[cid].agentsByRig[rigName] = 1
    else:
      # Count buildings by type (normalize team prefixes/suffixes).
      let typeName = normalizeTypeName(obj.typeName)
      # Skip walls and other non-building types.
      if typeName == "wall":
        continue
      if result[cid].buildingsByType.hasKey(typeName):
        result[cid].buildingsByType[typeName] += 1
      else:
        result[cid].buildingsByType[typeName] = 1

proc drawCollectivesPanel*(panel: Panel, frameId: string, contentPos: Vec2, contentSize: Vec2) =
  ## Draw the collectives panel showing stats for each collective.
  frame(frameId, contentPos, contentSize):
    if replay.isNil:
      text("Replay not loaded")
      return

    let numCollectives = getNumCollectives()
    if numCollectives == 0:
      text("No collectives configured")
      return

    let allStats = getCollectiveStats()
    for stats in allStats:
      # Skip collectives with nothing to show.
      let hasInventory = stats.inventory.len > 0
      let hasBuildings = stats.buildingsByType.len > 0
      let hasAgents = stats.agentsByRig.len > 0
      if not hasInventory and not hasBuildings and not hasAgents:
        continue

      # Header with collective name and color.
      let displayName = if stats.name.len > 0: stats.name.toUpperAscii else: &"Collective {stats.collectiveId}"
      let color = getAoeColor(stats.collectiveId)
      let tint = rgbx(color.r, color.g, color.b, 255)
      discard sk.drawText(sk.textStyle, displayName, sk.at, tint)
      sk.advance(vec2(0, sk.theme.spacing.float32 + 16))

      # Inventory section (only if there's inventory).
      if hasInventory:
        text("Inventory:")
        var sortedItems: seq[(string, int)] = @[]
        for itemName, count in stats.inventory.pairs:
          sortedItems.add((itemName, count))
        sortedItems.sort(proc(a, b: (string, int)): int = cmp(a[0], b[0]))
        for (itemName, count) in sortedItems:
          smallIconLabel("resources/" & itemName, &"{itemName}: {count}")
        sk.advance(vec2(0, 4))

      # Buildings section (only if there are buildings).
      if hasBuildings:
        text("Buildings:")
        var sortedTypes: seq[(string, int)] = @[]
        for typeName, count in stats.buildingsByType.pairs:
          sortedTypes.add((typeName, count))
        sortedTypes.sort(proc(a, b: (string, int)): int = cmp(b[1], a[1]))
        for (typeName, count) in sortedTypes:
          smallIconLabel("icons/objects/" & typeName, &"{typeName}: {count}")
        sk.advance(vec2(0, 4))

      # Agents by rig section (only if there are agents).
      if hasAgents:
        text("Agents:")
        var sortedRigs: seq[(string, int)] = @[]
        for rigName, count in stats.agentsByRig.pairs:
          sortedRigs.add((rigName, count))
        sortedRigs.sort(proc(a, b: (string, int)): int = cmp(b[1], a[1]))
        for (rigName, count) in sortedRigs:
          smallIconLabel("icons/agents/" & rigName, &"{rigName}: {count}")

      sk.advance(vec2(0, sk.theme.spacing.float32 * 2))
