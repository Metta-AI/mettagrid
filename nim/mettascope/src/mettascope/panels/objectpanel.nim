import
  std/[json, algorithm, tables, sets, strutils, strformat],
  vmath, silky, windy,
  ../common, ../replays, ../configs, ../cognames, ../collectives,
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
      # Hub-specific info.
      let cooldown = cur.cooldownRemaining.at
      if cooldown > 0:
        text(&"  Cooldown remaining: {cooldown}")
      if cur.cooldownDuration > 0:
        text(&"  Cooldown duration: {cur.cooldownDuration}")
      if cur.usesCount.at > 0:
        text(&"  Uses: {cur.usesCount.at}" &
          (if cur.maxUses > 0: "/" & $cur.maxUses else: ""))
      elif cur.maxUses > 0:
        text(&"  Max uses: {cur.maxUses}")
      if cur.allowPartialUsage:
        text("  Allows partial usage")

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

        for group in resourceLimitGroups:
          var usedAmount = 0
          var groupItems: seq[ItemAmount] = @[]
          for resourceName in group.resources:
            if resourceName in itemByName:
              let itemAmount = itemByName[resourceName]
              usedAmount += itemAmount.count
              groupItems.add(itemAmount)
            shownItems.incl(resourceName)

          # Only show the group if it has items
          if groupItems.len > 0:
            text(&"  {group.name}: {usedAmount}/{group.maxLimit}")
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


proc selectObject*(obj: Entity) =
  selection = obj
  saveUIState()
