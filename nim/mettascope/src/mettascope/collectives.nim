## Collectives module - utilities for working with collectives (teams/factions).
## Provides functions to get collective names, colors, configs, and stats.

import
  std/[algorithm, json, tables],
  chroma,
  common, replays

const NumCollectives* = 2

proc getCollectivesNode*(): JsonNode =
  ## Get the collectives JSON node (dict) from the replay config.
  if replay.isNil or replay.mgConfig.isNil:
    return nil
  if "game" notin replay.mgConfig or "collectives" notin replay.mgConfig["game"]:
    return nil
  let collectives = replay.mgConfig["game"]["collectives"]
  if collectives.kind != JObject:
    return nil
  return collectives

proc getNumCollectives*(): int =
  ## Get the number of collectives from the replay config.
  let collectives = getCollectivesNode()
  if collectives.isNil:
    return 0
  return collectives.len

proc getCollectiveName*(collectiveId: int): string =
  ## Get the collective name by ID from the mg_config.
  ## IDs are assigned alphabetically (matching C++/Python), so we sort keys first.
  let collectives = getCollectivesNode()
  if collectives.isNil or collectiveId < 0:
    return ""
  var names: seq[string] = @[]
  for key in collectives.keys:
    names.add(key)
  names.sort()
  if collectiveId < names.len:
    return names[collectiveId]
  return ""

proc getCollectiveConfig*(collectiveId: int): JsonNode =
  ## Get the collective config by ID from the mg_config.
  ## IDs are assigned alphabetically (matching C++/Python), so we sort keys first.
  let collectives = getCollectivesNode()
  if collectives.isNil or collectiveId < 0:
    return nil
  var names: seq[string] = @[]
  for key in collectives.keys:
    names.add(key)
  names.sort()
  if collectiveId < names.len:
    return collectives[names[collectiveId]]
  return nil

proc getCollectiveColor*(collectiveId: int): ColorRGBX =
  ## Get the color for a collective by ID.
  case collectiveId
  of 0: rgbx(230, 51, 51, 255)              # Clips = red
  of 1: rgbx(51, 204, 51, 255)              # Cogs = green
  else: rgbx(128, 128, 128, 255)            # Others = grey

# Alias for backward compatibility
proc getAoeColor*(collectiveId: int): ColorRGBX =
  getCollectiveColor(collectiveId)

type
  CollectiveStats* = object
    collectiveId*: int
    name*: string
    inventory*: Table[string, int]       ## itemName -> count
    buildingsByType*: Table[string, int] ## typeName -> count
    agentsByRig*: Table[string, int]     ## rigName -> count

proc getCollectiveInventory*(collectiveId: int): Table[string, int] =
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
