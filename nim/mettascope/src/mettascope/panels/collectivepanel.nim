## Collectives panel displays information about each collective (team/faction).
## Shows inventory, buildings, and agents grouped by rig type.

import
  std/[strformat, strutils, tables, algorithm],
  silky, vmath, chroma, bumpy,
  ../common, ../collectives,
  widgets

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
      let color = getCollectiveColor(stats.collectiveId)
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
