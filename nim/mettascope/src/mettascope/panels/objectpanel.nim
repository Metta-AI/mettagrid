import
  std/[json, algorithm, tables, sets, strutils, strformat],
  vmath, silky, windy,
  ../common, ../replays, ../configs, ../cognames, ../collectives, ../colors,
  widgets

type
  ResourceLimitGroup* = object
    name*: string
    minLimit*: int
    maxLimit*: int
    resources*: seq[string]
    modifiers*: Table[string, int]

proc getJsonInt(node: JsonNode): int =
  ## Get an int from a JSON node, handling both JInt and JFloat.
  if node.kind == JInt:
    result = node.getInt
  elif node.kind == JFloat:
    result = node.getFloat.int
  else:
    result = 0

proc parseResourceLimits(mgConfig: JsonNode): seq[ResourceLimitGroup] =
  ## Parse inventory limits from the agent config.
  result = @[]
  if mgConfig.isNil:
    return
  if "game" notin mgConfig or "agents" notin mgConfig["game"]:
    return
  let agents = mgConfig["game"]["agents"]
  if agents.kind != JArray or agents.len == 0:
    return
  let agentConfig = agents[0]
  if "inventory" notin agentConfig:
    return
  let invConfig = agentConfig["inventory"]
  if "limits" notin invConfig:
    return
  let limits = invConfig["limits"]
  if limits.kind != JObject:
    return
  for groupName, groupConfig in limits.pairs:
    var group = ResourceLimitGroup(name: groupName, minLimit: 0, maxLimit: 65535)
    if groupConfig.hasKey("min"):
      group.minLimit = getJsonInt(groupConfig["min"])
    if groupConfig.hasKey("max"):
      group.maxLimit = getJsonInt(groupConfig["max"])
    if groupConfig.hasKey("resources"):
      for r in groupConfig["resources"]:
        group.resources.add(r.getStr)
    if groupConfig.hasKey("modifiers"):
      group.modifiers = initTable[string, int]()
      for k, v in groupConfig["modifiers"].pairs:
        group.modifiers[k] = getJsonInt(v)
    result.add(group)

proc getItemName(itemAmount: ItemAmount): string =
  ## Safely resolve an item name from the replay data.
  if replay.isNil:
    return "item#" & $itemAmount.itemId
  if itemAmount.itemId >= 0 and itemAmount.itemId < replay.itemNames.len:
    replay.itemNames[itemAmount.itemId]
  else:
    "item#" & $itemAmount.itemId

proc getHeartCount(outputs: seq[ItemAmount]): int =
  ## Returns total hearts produced by this protocol.
  let heartId = replay.itemNames.find("heart")
  if heartId == -1:
    return 0
  for output in outputs:
    if output.itemId == heartId:
      return output.count
  return 0

proc protocolCmp(a, b: Protocol): int =
  ## Sort protocols: heart-producing ones first (most hearts first), then others.
  let
    aHearts = getHeartCount(a.outputs)
    bHearts = getHeartCount(b.outputs)
  if aHearts > 0 and bHearts == 0:
    return -1
  if aHearts == 0 and bHearts > 0:
    return 1
  cmp(bHearts, aHearts)

proc getObjConfig(cur: Entity): JsonNode =
  ## Get the object config from mg_config for the given entity.
  if replay.isNil or replay.mgConfig.isNil:
    return nil
  if "game" notin replay.mgConfig or "objects" notin replay.mgConfig["game"]:
    return nil
  let objects = replay.mgConfig["game"]["objects"]
  if cur.typeName in objects:
    return objects[cur.typeName]
  return nil

proc drawOnUseHandlers(objConfig: JsonNode) =
  ## Draw the on_use_handlers section from config, showing what interactions are available.
  if objConfig.isNil or "on_use_handlers" notin objConfig:
    return
  let handlers = objConfig["on_use_handlers"]
  if handlers.kind != JObject or handlers.len == 0:
    return

  text("Interactions")
  for handlerName, handlerConfig in handlers.pairs:
    var parts: seq[string] = @[]

    # Show filter requirements (resource filters on actor).
    if "filters" in handlerConfig and handlerConfig["filters"].kind == JArray:
      for filter in handlerConfig["filters"]:
        if filter.kind != JObject:
          continue
        let filterType = if "filter_type" in filter: filter["filter_type"].getStr else: ""
        let target = if "target" in filter: filter["target"].getStr else: ""
        if filterType == "resource" and "resources" in filter:
          var reqs: seq[string] = @[]
          for resName, resCount in filter["resources"].pairs:
            var count = 0
            if resCount.kind == JInt: count = resCount.getInt
            elif resCount.kind == JFloat: count = resCount.getFloat.int
            reqs.add(&"{resName} x{count}")
          let targetLabel = if target == "actor": "agent" elif target.contains("collective"): "collective" else: target
          parts.add("requires " & targetLabel & ": " & reqs.join(", "))
        elif filterType == "alignment":
          let alignment = if "alignment" in filter: filter["alignment"].getStr else: ""
          if alignment.len > 0:
            parts.add(alignment.replace("_", " "))

    # Show mutation effects.
    if "mutations" in handlerConfig and handlerConfig["mutations"].kind == JArray:
      for mutation in handlerConfig["mutations"]:
        if mutation.kind != JObject:
          continue
        let mutType = if "mutation_type" in mutation: mutation["mutation_type"].getStr else: ""
        let target = if "target" in mutation: mutation["target"].getStr else: ""
        case mutType
        of "resource_transfer":
          let fromTarget = if "from_target" in mutation: mutation["from_target"].getStr else: ""
          let toTarget = if "to_target" in mutation: mutation["to_target"].getStr else: ""
          if "resources" in mutation and mutation["resources"].kind == JObject:
            var transfers: seq[string] = @[]
            for resName, resCount in mutation["resources"].pairs:
              var count = 0
              if resCount.kind == JInt: count = resCount.getInt
              elif resCount.kind == JFloat: count = resCount.getFloat.int
              transfers.add(&"{resName} x{count}")
            let fromLabel = fromTarget.replace("_", " ")
            let toLabel = toTarget.replace("_", " ")
            parts.add(&"{fromLabel} -> {toLabel}: {transfers.join(\", \")}")
          let removeWhenEmpty = if "remove_source_when_empty" in mutation: mutation["remove_source_when_empty"].getBool else: false
          if removeWhenEmpty:
            parts.add("depletes source")
        of "resource_delta":
          if "deltas" in mutation and mutation["deltas"].kind == JObject:
            var deltas: seq[string] = @[]
            for resName, resDelta in mutation["deltas"].pairs:
              var delta = 0
              if resDelta.kind == JInt: delta = resDelta.getInt
              elif resDelta.kind == JFloat: delta = resDelta.getFloat.int
              let sign = if delta >= 0: "+" else: ""
              deltas.add(&"{resName} {sign}{delta}")
            let targetLabel = target.replace("_", " ")
            parts.add(&"{targetLabel}: {deltas.join(\", \")}")
        of "alignment":
          let alignTo = if "align_to" in mutation: mutation["align_to"].getStr else: ""
          let targetLabel = target.replace("_", " ")
          parts.add(&"align {targetLabel} to {alignTo.replace(\"_\", \" \")}")
        of "clear_inventory":
          let limitName = if "limit_name" in mutation: mutation["limit_name"].getStr else: "all"
          let targetLabel = target.replace("_", " ")
          parts.add(&"clear {targetLabel} {limitName}")
        else:
          if mutType.len > 0:
            parts.add(mutType.replace("_", " "))

    text(&"  {handlerName}:")
    for part in parts:
      text(&"    {part}")

proc drawObjectInfo*(panel: Panel, frameId: string, contentPos: Vec2, contentSize: Vec2) =
  ## Draws the object info panel using silky widgets.
  frame(frameId, contentPos, contentSize):
    if selection.isNil:
      text("No selection")
      return

    if replay.isNil:
      text("Replay not loaded")
      return

    let cur = selection

    button("Open Config"):
      if cur.isNil:
        return
      let cfgText =
        if replay.isNil or replay.mgConfig.isNil:
          "No replay config found."
        else:
          let typeName = cur.typeName
          if typeName == "agent":
            let agentConfig = replay.mgConfig["game"]["agent"]
            agentConfig.pretty
          else:
            if "game" notin replay.mgConfig or "objects" notin replay.mgConfig["game"]:
              "No object config found."
            elif typeName notin replay.mgConfig["game"]["objects"]:
              "Object config not found for type: " & typeName
            else:
              let objConfig = replay.mgConfig["game"]["objects"][typeName]
              objConfig.pretty
      openTempTextFile(cur.typeName & "_config.json", cfgText)

    # Basic identity
    if cur.isAgent:
      let cogName = getCogName(cur.agentId)
      if cogName.len > 0:
        h1text(&"{cogName} ({cur.agentId})")
      else:
        h1text(&"Agent {cur.agentId}")
    else:
      h1text(cur.typeName)
      text(&"  Object ID: {cur.id}")
    # Display collective with name and color
    let curCollectiveId = cur.collectiveId.at
    if curCollectiveId >= 0:
      let collectiveColor = getCollectiveColor(curCollectiveId)
      let collectiveName = getCollectiveName(curCollectiveId)
      let labelText = if collectiveName.len > 0:
        &"  Collective: {collectiveName}"
      else:
        &"  Collective: ({curCollectiveId})"
      let textSize = sk.drawText(sk.textStyle, labelText, sk.at, collectiveColor)
      sk.advance(textSize)

    # Show AoE fields if this object type has them
    if not replay.mgConfig.isNil and "game" in replay.mgConfig:
      let game = replay.mgConfig["game"]
      if "objects" in game and cur.typeName in game["objects"]:
        let objConfig = game["objects"][cur.typeName]
        if "aoes" in objConfig and objConfig["aoes"].kind == JObject:
          let aoes = objConfig["aoes"]
          if aoes.len > 0:
            text("  AOEs:")
            for aoeName, aoeConfig in aoes.pairs:
              var radius = 0
              if "radius" in aoeConfig:
                if aoeConfig["radius"].kind == JInt:
                  radius = aoeConfig["radius"].getInt
                elif aoeConfig["radius"].kind == JFloat:
                  radius = aoeConfig["radius"].getFloat.int
              text(&"    {aoeName} (radius: {radius})")

    if cur.isAgent:
      # Agent-specific info.
      let reward = cur.totalReward.at
      text(&"  Total reward: {formatFloat(reward, ffDecimal, 2)}")
      let rigName = getAgentRigName(cur)
      if rigName != "agent":
        text(&"  Rig: {rigName}")
      let vibeId = cur.vibeId.at
      if vibeId >= 0 and vibeId < replay.config.game.vibeNames.len:
        let vibeName = getVibeName(vibeId)
        text("  Vibe: " & vibeName)
    else:
      # Building info.
      let objConfig = getObjConfig(cur)

      if not cur.alive.at:
        text("  Dead")

    sk.advance(vec2(0, sk.theme.spacing.float32))

    let currentInventory = cur.inventory.at
    if currentInventory.len > 0:
      text("Inventory")
      if cur.isAgent:
        let resourceLimitGroups = parseResourceLimits(replay.mgConfig)

        var itemByName = initTable[string, ItemAmount]()
        for itemAmount in currentInventory:
          if itemAmount.itemId >= 0 and itemAmount.itemId < replay.itemNames.len:
            itemByName[replay.itemNames[itemAmount.itemId]] = itemAmount

        var shownItems = initOrderedSet[string]()

        # Get dynamic capacity data for the current step.
        let currentCapacities = cur.inventoryCapacities.at

        for group in resourceLimitGroups:
          var usedAmount = 0
          var groupItems: seq[ItemAmount] = @[]
          for resourceName in group.resources:
            if resourceName in itemByName:
              let itemAmount = itemByName[resourceName]
              usedAmount += itemAmount.count
              groupItems.add(itemAmount)
            shownItems.incl(resourceName)

          # Look up dynamic capacity by matching group name to capacity_names.
          # Falls back to static config maxLimit for old replays without capacity_names.
          var groupCapacity = group.maxLimit
          if replay.capacityNames.len > 0:
            let capIdx = replay.capacityNames.find(group.name)
            if capIdx >= 0:
              for cap in currentCapacities:
                if cap.capacityId == capIdx:
                  groupCapacity = cap.limit
                  break

          # Always show the group (capacities are dynamic, so empty groups are informative).
          text(&"  {group.name}: {usedAmount}/{groupCapacity}")
          if groupItems.len > 0:
            for itemAmount in groupItems:
              let itemName = getItemName(itemAmount)
              let iconPath =
                if group.name == "gear":
                  "icons/agents/" & itemName
                elif group.name in ["heart", "energy", "cargo"]:
                  "resources/" & itemName
                else:
                  "icons/" & itemName
              smallIconLabel(iconPath, &"{itemName}: {itemAmount.count}")
          else:
            let emptySize = sk.drawText(sk.textStyle, "    empty", sk.at, Gray)
            sk.advance(emptySize)

        var ungroupedItems: seq[ItemAmount] = @[]
        for itemAmount in currentInventory:
          if itemAmount.itemId >= 0 and itemAmount.itemId < replay.itemNames.len:
            let itemName = replay.itemNames[itemAmount.itemId]
            if itemName notin shownItems:
              ungroupedItems.add(itemAmount)

        if ungroupedItems.len > 0:
          text("  Other:")
          for itemAmount in ungroupedItems:
            let itemName = getItemName(itemAmount)
            smallIconLabel("icons/" & itemName, &"{itemName}: {itemAmount.count}")
      else:
        for itemAmount in currentInventory:
          let itemName = getItemName(itemAmount)
          smallIconLabel("resources/" & itemName, &"{itemName}: {itemAmount.count}")

    sk.advance(vec2(0, sk.theme.spacing.float32))

    # Protocols
    if cur.protocols.len > 0:
      text("Protocols")
      var sortedProtocols = cur.protocols
      sortedProtocols.sort(protocolCmp)

      for protocol in sortedProtocols:
        let protocol = protocol
        group(vec2(4, 4), LeftToRight):
          if protocol.vibes.len > 0:
            #var vibeLine = "  Vibes: "
            # Group the vibes by type.
            var vibeGroups: Table[string, int]
            for vibe in protocol.vibes:
              let vibeName = getVibeName(vibe)
              if vibeName notin vibeGroups:
                vibeGroups[vibeName] = 1
              else:
                vibeGroups[vibeName] = vibeGroups[vibeName] + 1
            for vibeName, numVibes in vibeGroups:
              icon("vibe/" & vibeName)
              text("x" & $numVibes)

            icon("ui/add")

          if protocol.inputs.len > 0:
            for i, resource in protocol.inputs:
              icon("resources/" & replay.config.game.resourceNames[resource.itemId])
              text("x" & $resource.count)

            icon("ui/right-arrow")

          if protocol.outputs.len > 0:
            for i, resource in protocol.outputs:
              icon("resources/" & replay.config.game.resourceNames[resource.itemId])
              text("x" & $resource.count)

    # On-use handlers from config (for non-agent objects).
    if not cur.isAgent:
      sk.advance(vec2(0, sk.theme.spacing.float32))
      let objConfigForHandlers = getObjConfig(cur)
      drawOnUseHandlers(objConfigForHandlers)


proc selectObject*(obj: Entity) =
  selection = obj
  if obj != nil:
    let cid = obj.collectiveId.at(step)
    if cid >= 0:
      activeCollective = cid
  saveUIState()
