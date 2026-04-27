import
  std/[json, algorithm, tables, sets, strutils, strformat],
  vmath, silky, windy,
  ../common, ../replays, ../configs, ../cognames, ../colors,
  ../gamemode/[team, sound],
  widgets

type
  ResourceLimitGroup* = object
    name*: string
    minLimit*: int
    maxLimit*: int
    resources*: seq[string]
    modifiers*: Table[string, int]

const
  AmongCogsAliveResource = "alive"
  AmongCogsCorpseResource = "corpse"
  AmongCogsCrewResource = "crew"
  AmongCogsEjectedResource = "ejected"
  AmongCogsImpostorResource = "impostor"
  AmongCogsKillCooldownResource = "kill_cooldown"
  AmongCogsLightsAlertResource = "lights_alert"
  AmongCogsMeetingActiveResource = "meeting_active"
  AmongCogsMeetingBallotResource = "meeting_ballot"
  AmongCogsMeetingDiscussionResource = "meeting_discussion"
  AmongCogsMeetingReportedBodyResource = "meeting_reported_body"
  AmongCogsMeetingTimerResource = "meeting_timer"
  AmongCogsMeetingTokenResource = "meeting_token"
  AmongCogsSabotageCooldownResource = "sabotage_cooldown"
  AmongCogsTaskProgressResource = "task_progress"
  AmongCogsVentCooldownResource = "vent_cooldown"
  AmongCogsVotedResource = "voted"
  AmongCogsVoteImpostorResource = "vote_impostor"
  AmongCogsVoteSkipResource = "vote_skip"
  AmongCogsVoteTargetResourcePrefix = "vote_target_"
  AmongCogsRequiredResources = [
    AmongCogsMeetingActiveResource,
    AmongCogsMeetingBallotResource,
    AmongCogsVotedResource,
    AmongCogsVoteImpostorResource,
    AmongCogsVoteSkipResource,
  ]

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

proc amongCogsDataLoaded(): bool =
  ## Returns true when replay data exposes the Amongcogs meeting contract.
  if replay.isNil:
    return false
  for resourceName in AmongCogsRequiredResources:
    if replay.itemNames.find(resourceName) < 0:
      return false
  return true

proc itemCount(cur: Entity, resourceName: string): int =
  ## Return the current amount of a named inventory resource.
  if replay.isNil or cur.isNil:
    return 0
  replay.entityResourceCount(cur, resourceName, step)

proc parsePrefixedInt(value, prefix: string): int =
  ## Parse a non-negative integer after a known resource-name prefix.
  if not value.startsWith(prefix):
    return -1
  let suffix = value[prefix.len .. ^1]
  if suffix.len == 0:
    return -1
  for ch in suffix:
    if ch < '0' or ch > '9':
      return -1
  return parseInt(suffix)

proc amongCogsVoteTarget(agent: Entity): int =
  ## Return the named meeting vote target for an agent, or -1 when absent.
  if replay.isNil:
    return -1
  for resourceName in replay.itemNames:
    let agentId = parsePrefixedInt(
      resourceName,
      AmongCogsVoteTargetResourcePrefix
    )
    if agentId >= 0 and itemCount(agent, resourceName) > 0:
      return agentId
  return -1

proc amongCogsRoleLabel(agent: Entity): string =
  ## Return the Amongcogs role label for an agent.
  if itemCount(agent, AmongCogsImpostorResource) > 0:
    return "impostor"
  if itemCount(agent, AmongCogsCrewResource) > 0:
    return "crew"
  return "unknown"

proc amongCogsAgentLabel(agent: Entity): string =
  ## Return the display label for an Amongcogs agent.
  let cogName = getCogName(agent.agentId)
  if cogName.len > 0:
    return cogName
  return "Agent " & $agent.agentId

proc amongCogsVoteLabel(agent: Entity): string =
  ## Return the visible meeting vote/status label for an agent.
  if itemCount(agent, AmongCogsEjectedResource) > 0:
    return "ejected"
  if itemCount(agent, AmongCogsCorpseResource) > 0:
    return "body"
  if itemCount(agent, AmongCogsVotedResource) > 0:
    let voteTarget = amongCogsVoteTarget(agent)
    if voteTarget >= 0:
      return "vote Agent " & $voteTarget
    if itemCount(agent, AmongCogsVoteSkipResource) > 0:
      return "skip"
    if itemCount(agent, AmongCogsVoteImpostorResource) > 0:
      return "accuse"
    return "voted"
  if itemCount(agent, AmongCogsMeetingBallotResource) > 0:
    return "waiting"
  if itemCount(agent, AmongCogsMeetingDiscussionResource) > 0:
    return "discussing"
  if itemCount(agent, AmongCogsMeetingActiveResource) > 0:
    return "meeting"
  if itemCount(agent, AmongCogsAliveResource) == 0:
    return "dead"
  return "ready"

proc amongCogsAgentIcon(agent: Entity): string =
  ## Return a minimap icon path for an Amongcogs agent.
  let resolvedAsset = replay.resolveRenderAsset(agent, step)
  if resolvedAsset.len > 0:
    return "minimap/" & resolvedAsset
  if itemCount(agent, AmongCogsImpostorResource) > 0:
    return "minimap/impostor"
  return "minimap/crewmate"

proc amongCogsMeetingPhase(): string =
  ## Return the current global Amongcogs meeting phase label.
  var
    activeCount = 0
    ballotCount = 0
    discussionCount = 0
    ejectedCount = 0
  for agent in replay.agents:
    activeCount += itemCount(agent, AmongCogsMeetingActiveResource)
    ballotCount += itemCount(agent, AmongCogsMeetingBallotResource)
    discussionCount += itemCount(agent, AmongCogsMeetingDiscussionResource)
    ejectedCount += itemCount(agent, AmongCogsEjectedResource)
  if activeCount == 0:
    if ejectedCount > 0:
      return "result"
    return "idle"
  if ballotCount > 0:
    return "voting"
  if discussionCount > 0:
    return "discussion"
  return "meeting"

proc amongCogsPanelRelevant(cur: Entity): bool =
  ## Return true if the selected object should expose the Amongcogs panel.
  if not amongCogsDataLoaded():
    return false
  if cur.isAgent:
    return true
  return cur.typeName == "emergency_button" or cur.typeName.endsWith("_vent")

proc amongCogsMeetingRosterVisible(): bool =
  ## Return true when the meeting roster should be shown.
  var
    activeCount = 0
    votedCount = 0
    reportedBodyCount = 0
  for agent in replay.agents:
    activeCount += itemCount(agent, AmongCogsMeetingActiveResource)
    votedCount += itemCount(agent, AmongCogsVotedResource)
    reportedBodyCount += itemCount(agent, AmongCogsMeetingReportedBodyResource)
  return activeCount > 0 or votedCount > 0 or reportedBodyCount > 0

proc amongCogsVoteTargetSummary(targetCounts: Table[int, int]): string =
  ## Return a compact summary of named target vote totals.
  var targets: seq[int] = @[]
  for target in targetCounts.keys:
    targets.add(target)
  targets.sort()
  for target in targets:
    if result.len > 0:
      result.add(", ")
    result.add(&"Agent {target} {targetCounts[target]}")
  if result.len == 0:
    result = "none"

proc drawAmongCogsPanel(cur: Entity): bool =
  ## Draw Amongcogs meeting, vote, and action state in the object panel.
  if not amongCogsPanelRelevant(cur):
    return false
  result = true
  text("Amongcogs")

  if cur.isAgent:
    let
      meetingTimer = itemCount(cur, AmongCogsMeetingTimerResource)
      killTimer = itemCount(cur, AmongCogsKillCooldownResource)
      sabotageTimer = itemCount(cur, AmongCogsSabotageCooldownResource)
      ventTimer = itemCount(cur, AmongCogsVentCooldownResource)
      lightsAlert = itemCount(cur, AmongCogsLightsAlertResource)
    text(
      &"  Role: {amongCogsRoleLabel(cur)}  State: {amongCogsVoteLabel(cur)}"
    )
    text(
      &"  Timers: meeting {meetingTimer} kill {killTimer}"
    )
    text(
      &"  Cooldowns: sabotage {sabotageTimer} vent {ventTimer}"
    )
    text(
      &"  Tasks: progress {itemCount(cur, AmongCogsTaskProgressResource)} " &
        &"button calls {itemCount(cur, AmongCogsMeetingTokenResource)}"
    )
    text(
      &"  Vision: radius {cur.visionSize div 2} lights {lightsAlert}"
    )
  elif cur.typeName == "emergency_button":
    text("  Emergency button: selected")
    text("  Meeting calls: tracked on each agent")
  else:
    text("  Vent: selected")
    text("  Network: linked vents; cooldown tracked on impostors")

  var
    activeCount = 0
    votedCount = 0
    accuseCount = 0
    skipCount = 0
    maxTimer = 0
    reportedBodyCount = 0
    targetVoteCounts = initTable[int, int]()
  for agent in replay.agents:
    activeCount += itemCount(agent, AmongCogsMeetingActiveResource)
    votedCount += itemCount(agent, AmongCogsVotedResource)
    let voteTarget = amongCogsVoteTarget(agent)
    if voteTarget >= 0:
      if voteTarget in targetVoteCounts:
        inc targetVoteCounts[voteTarget]
      else:
        targetVoteCounts[voteTarget] = 1
    else:
      accuseCount += itemCount(agent, AmongCogsVoteImpostorResource)
    skipCount += itemCount(agent, AmongCogsVoteSkipResource)
    reportedBodyCount += itemCount(agent, AmongCogsMeetingReportedBodyResource)
    maxTimer = max(maxTimer, itemCount(agent, AmongCogsMeetingTimerResource))

  text(
    &"  Meeting: {amongCogsMeetingPhase()}  timer {maxTimer} " &
      &"reported bodies {reportedBodyCount}"
  )
  text(
    &"  Votes: {votedCount}/{activeCount}  accuse {accuseCount} " &
      &"skip {skipCount}"
  )
  if targetVoteCounts.len > 0:
    text("  Targets: " & amongCogsVoteTargetSummary(targetVoteCounts))

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
  if replay.isNil:
    return nil
  if cur.typeName in replay.objectConfigsByName:
    return replay.objectConfigsByName[cur.typeName]
  return nil

proc drawOnUseHandlers(objConfig: JsonNode) =
  ## Draw the on_use_handler section showing available interactions.
  if objConfig.isNil or "on_use_handler" notin objConfig:
    return
  let handler = objConfig["on_use_handler"]
  if handler.kind != JObject:
    return
  var handlers: JsonNode
  if "handlers" in handler and handler["handlers"].kind == JArray:
    handlers = handler["handlers"]
  else:
    handlers = newJArray()
    handlers.add(handler)
  if handlers.len == 0:
    return

  text("Interactions")
  for handlerConfig in handlers:
    if handlerConfig.kind != JObject:
      continue
    let handlerName =
      if "name" in handlerConfig: handlerConfig["name"].getStr
      else: ""
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
          let targetLabel = if target == "actor": "agent" else: target
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
    if selected.isNil:
      text("Nothing selected")
      return

    if replay.isNil:
      text("Replay not loaded")
      return

    let cur = selected

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
            if typeName notin replay.objectConfigsByName:
              "Object config not found for type: " & typeName
            else:
              replay.objectConfigsByName[typeName].pretty
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

    # Show tags for this object at the current step.
    let currentTagIds = cur.tagIds.at
    if currentTagIds.len > 0:
      var tagNames: seq[string] = @[]
      for tagId in currentTagIds:
        var found = false
        for name, id in replay.tags:
          if id == tagId:
            tagNames.add(name)
            found = true
            break
        if not found:
          tagNames.add("tag#" & $tagId)
      tagNames.sort()
      text("  Tags: " & tagNames.join(", "))

    # Show territory controls if this object type has them.
    let controls = replay.getTerritoryControls(cur.typeName)
    if controls.len > 0:
      text("  Territory:")
      for control in controls:
        text(&"    {control.territory} (strength: {control.strength}, decay: {control.decay})")

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
      if not cur.alive.at:
        text("  Dead")

    if drawAmongCogsPanel(cur):
      if amongCogsMeetingRosterVisible():
        for agent in replay.agents:
          if itemCount(agent, AmongCogsMeetingActiveResource) > 0 or
              itemCount(agent, AmongCogsEjectedResource) > 0:
            let label =
              &"{amongCogsAgentLabel(agent)}: {amongCogsRoleLabel(agent)}, " &
                amongCogsVoteLabel(agent)
            smallIconLabel(amongCogsAgentIcon(agent), label)
      sk.advance(vec2(0, sk.theme.spacing.float32))

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
              let iconPath = "resources/" & itemName
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
            smallIconLabel("resources/" & itemName, &"{itemName}: {itemAmount.count}")
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
  if obj != nil and not obj.alive.at:
    return
  selected = obj
  if obj != nil:
    let teamIdx = getEntityTeamIndex(obj)
    if teamIdx >= 0:
      let teamName = getTeamName(teamIdx)
      if teamName.startsWith("cogs"):
        lastSelectedTeam = teamIdx
  settings.lockFocus = not obj.isNil
  saveUIState()
  playEntitySound(obj)
