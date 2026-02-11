## Collectives module - utilities for working with collectives (teams/factions).
## Provides functions to get collective names, colors, and stats.
## Collective data (name, color) is cached in replay.collectives at load time.

import
  std/tables,
  chroma,
  common, replays, colors

proc getNumCollectives*(): int =
  ## Get the number of collectives from the cached replay data.
  if replay.isNil:
    return 0
  return replay.collectives.len

proc getCollectiveName*(collectiveId: int): string =
  ## Get the collective name by ID from the cached replay data.
  if replay.isNil or collectiveId < 0 or collectiveId >= replay.collectives.len:
    return ""
  return replay.collectives[collectiveId].name

proc getCollectiveColor*(collectiveId: int): ColorRGBX =
  ## Get the color for a collective from the cached replay data.
  if replay.isNil or collectiveId < 0 or collectiveId >= replay.collectives.len:
    return Gray
  return replay.collectives[collectiveId].color

type
  CollectiveStats* = object
    collectiveId*: int
    name*: string
    inventory*: Table[string, int]       ## itemName -> count
    buildingsByType*: Table[string, int] ## typeName -> count
    agentsByRig*: Table[string, int]     ## rigName -> count

proc getAgentRigName*(agent: Entity): string =
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

  let numCollectives = replay.collectives.len
  if numCollectives == 0:
    return

  # Initialize stats for each collective.
  for i in 0 ..< numCollectives:
    var stats = CollectiveStats(
      collectiveId: i,
      name: replay.collectives[i].name,
      inventory: initTable[string, int](),
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
