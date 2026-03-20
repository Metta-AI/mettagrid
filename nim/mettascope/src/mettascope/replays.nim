import std/[algorithm, json, os, tables, strutils],
  zippy, vmath, jsony, silky, chroma,
  ./validation

# If you update this, also update REPLAY_FORMAT_VERSION in
# mettagrid/python/src/mettagrid/simulator/replay_log_writer.py
const FormatVersion* = 4

type

  ActionConfig* = object
    enabled*: bool

  Protocol* = object
    minAgents*: int
    vibes*: seq[int]
    inputs*: seq[ItemAmount]
    outputs*: seq[ItemAmount]
    cooldown*: int

  RecipeInfoConfig* = tuple[pattern: seq[string], protocol: Protocol]

  TeamInfo* = object
    name*: string
    tagId*: int
    color*: ColorRGBX

  ObsConfig* = object
    width*: int
    height*: int
    tokenDim*: int
    numTokens*: int
    tokenValueBase*: int

  TerritoryControl* = object
    territory*: string
    strength*: int
    decay*: int

  ObjectConfig* = object
    name*: string
    typeId*: int
    mapChar*: string
    renderName*: string
    renderSymbol*: string
    tags*: seq[string]
    `type`*: string
    swappable*: bool
    recipes*: seq[RecipeInfoConfig]
    territory_controls*: seq[TerritoryControl]

  RenderHudConfig* = object
    resource*: string
    short_name*: string
    max*: int
    rank*: int

  RenderStatusBarConfig* = object
    resource*: string
    short_name*: string
    bar_type*: string
    max*: int
    divisions*: int
    rank*: int

  RenderAssetRule* = object
    asset*: string
    resources*: seq[string]
    tags*: seq[string]

  RenderConfig* = object
    hud1*: RenderHudConfig
    hud2*: RenderHudConfig
    agent_huds*: Table[string, RenderHudConfig]
    object_status*: Table[string, Table[string, RenderStatusBarConfig]]

  GameConfig* = object
    resourceNames*: seq[string]
    vibeNames*: seq[string]
    numAgents*: int
    maxSteps*: int
    obs*: ObsConfig
    actions*: Table[string, ActionConfig]
    objects*: Table[string, ObjectConfig]
    render*: RenderConfig

  Config* = object
    label*: string
    game*: GameConfig
    desync_episodes*: bool

  ItemAmount* = object
    itemId*: int
    count*: int

  CapacityAmount* = object
    capacityId*: int
    limit*: int

type
  Entity* = ref object
    # Common keys.
    id*: int
    typeName*: string
    renderName*: string
    groupId*: int
    agentId*: int
    location*: seq[IVec2]
    orientation*: seq[int]
    inventory*: seq[seq[ItemAmount]]
    inventoryMax*: int
    inventoryCapacities*: seq[seq[CapacityAmount]]
    color*: seq[int]
    vibeId*: seq[int]

    # Agent specific keys.
    actionId*: seq[int]
    actionParameter*: seq[int]
    actionSuccess*: seq[bool]
    animationId*: seq[int]  ## Per-step animation index into animationNames.
    currentReward*: seq[float]
    totalReward*: seq[float]
    isFrozen*: seq[bool]
    frozenProgress*: seq[int]
    frozenTime*: int
    visionSize*: int

    # Building specific keys.
    inputResources*: seq[ItemAmount]
    outputResources*: seq[ItemAmount]
    recipeMax*: int
    productionProgress*: seq[int]
    productionTime*: int
    cooldownProgress*: seq[int]
    cooldownTime*: int

    # Lifecycle fields.
    alive*: seq[bool]  ## Whether the object is alive at each step (default: true).

    # Hub specific keys.
    cooldownRemaining*: seq[int]
    cooldownDuration*: int
    usesCount*: seq[int]
    maxUses*: int
    allowPartialUsage*: bool
    exhaustion*: seq[bool]
    cooldownMultiplier*: seq[float]
    currentRecipeId*: int
    protocols*: seq[Protocol]

    # Tag fields.
    tagIds*: seq[seq[int]]

    # Policy info (per-step arbitrary metadata from policy).
    policyInfos*: seq[JsonNode]
    dialogueAppend*: seq[string]
    dialogueReset*: seq[bool]

    # Computed fields.
    gainMap*: seq[seq[ItemAmount]]
    isAgent*: bool

  Replay* = ref object
    version*: int
    numAgents*: int
    maxSteps*: int
    mapSize*: (int, int)
    fileName*: string
    typeNames*: seq[string]
    actionNames*: seq[string]
    itemNames*: seq[string]
    groupNames*: seq[string]
    capacityNames*: seq[string]  ## Maps capacity_id to group name (e.g., "cargo", "gear").
    animationNames*: seq[string]  ## Maps animation index to name (e.g., "none", "bump").
    tags*: Table[string, int]  ## Maps tag name to tag ID.
    typeImages*: Table[string, string]
    actionImages*: seq[string]
    actionAttackImages*: seq[string]
    actionIconImages*: seq[string]
    itemImages*: seq[string]
    traceImages*: seq[string]
    objects*: seq[Entity]
    rewardSharingMatrix*: seq[seq[float]]

    agents*: seq[Entity]

    teams*: seq[TeamInfo]
    drawnAgentActionMask*: uint64
    mgConfig*: JsonNode
    config*: Config
    tutorialOverlay*: string
    tutorialOverlayPhases*: seq[string]
    tutorialOverlayPhase*: int

    objectConfigsByName*: Table[string, JsonNode]
    territoryControlsByName*: Table[string, seq[TerritoryControl]]
    renderAssetsByType*: Table[string, seq[RenderAssetRule]]

    # Cached render config, sorted by rank at load time.
    sortedHudItems*: seq[RenderHudConfig]
    sortedStatusItems*: Table[string, seq[RenderStatusBarConfig]]
    # Cached action IDs for common actions.
    noopActionId*: int
    attackActionId*: int
    putItemsActionId*: int
    getItemsActionId*: int
    moveNorthActionId*: int
    moveSouthActionId*: int
    moveWestActionId*: int
    moveEastActionId*: int

  ReplayEntity* = ref object
    ## Replay entity does not have time series and only has the current step value.
    id*: int
    typeName*: string
    renderName*: string
    typeId*: int
    groupId*: int
    agentId*: int
    location*: IVec2
    orientation*: int
    inventory*: seq[ItemAmount]
    inventoryMax*: int
    inventoryCapacities*: seq[CapacityAmount]  ## Per-capacity-group effective limits (current step).
    color*: int
    vibeId*: int

    # Agent specific keys.
    actionId*: int
    actionParameter*: int
    actionSuccess*: bool
    animationId*: int
    currentReward*: float
    totalReward*: float
    isFrozen*: bool
    frozenProgress*: int
    frozenTime*: int
    visionSize*: int

    # Building specific keys.
    inputResources*: seq[ItemAmount]
    outputResources*: seq[ItemAmount]
    recipeMax*: int
    productionProgress*: int
    productionTime*: int
    cooldownProgress*: int
    cooldownTime*: int

    # Lifecycle fields.
    alive*: bool = true  ## Whether the object is alive this step.

    # Hub specific keys.
    cooldownRemaining*: int
    cooldownDuration*: int
    usesCount*: int
    maxUses*: int
    allowPartialUsage*: bool
    protocols*: seq[Protocol]

    # Tag fields.
    tagIds*: seq[int]

    # Policy info (arbitrary metadata from policy).
    policyInfos*: JsonNode
    dialogueAppend*: string = ""
    dialogueReset*: bool = false

  ReplayStep* = ref object
    step*: int
    objects*: seq[ReplayEntity]
    tutorial_overlay*: string = ""
    tutorial_overlay_phases*: seq[string] = @[]

## Empty replays is used before a real replay is loaded,
## so that we don't need to check for nil everywhere.
let EmptyReplay* = Replay(
  version: FormatVersion,
  numAgents: 0,
  maxSteps: 0,
  mapSize: (0, 0),
  fileName: "",
)

proc getInt*(obj: JsonNode, key: string, default: int = 0): int =
  ## Get an integer field from JsonNode with a default value if key is missing.
  if key in obj: obj[key].getInt else: default

proc getString*(obj: JsonNode, key: string, default: string = ""): string =
  ## Get a string field from JsonNode with a default value if key is missing.
  if key in obj: obj[key].getStr else: default

proc getFloat*(obj: JsonNode, key: string, default: float = 0.0): float =
  ## Get a float field from JsonNode with a default value if key is missing.
  ## Accepts integers and converts them to floats.
  if key in obj:
    if obj[key].kind == JFloat: obj[key].getFloat
    elif obj[key].kind == JInt: obj[key].getInt.float
    else: default
  else: default

proc getBool*(obj: JsonNode, key: string, default: bool = false): bool =
  ## Get a boolean field from JsonNode with a default value if key is missing.
  if key in obj and obj[key].kind == JBool: obj[key].getBool else: default

proc getJsonNode*(obj: JsonNode, key: string, default: JsonNode = nil): JsonNode =
  ## Get any JsonNode field with a default value if key is missing.
  if key in obj: obj[key] else: default

proc getArray*(obj: JsonNode, key: string, default: JsonNode = nil): JsonNode =
  ## Get an array JsonNode field with a default value if key is missing.
  if key in obj and obj[key].kind == JArray: obj[key] else: default

proc getJsonNodeOr*(obj: JsonNode, key1: string, key2: string, default: JsonNode = nil): JsonNode =
  ## Get JsonNode field, trying key1 first, then key2, then default.
  if key1 in obj: obj[key1]
  elif key2 in obj: obj[key2]
  else: default

proc getMapSize*(obj: JsonNode, default: (int, int) = (0, 0)): (int, int) =
  ## Get map_size [width, height] with bounds checking.
  if "map_size" in obj:
    let mapSize = obj["map_size"]
    if mapSize.kind == JArray and mapSize.len >= 2:
      let w = if mapSize[0].kind == JInt: mapSize[0].getInt else: 0
      let h = if mapSize[1].kind == JInt: mapSize[1].getInt else: 0
      return (w, h)
  default

proc getTerritoryControls*(replay: Replay, typeName: string): seq[TerritoryControl] =
  ## Return typed territory controls for a given object type.
  if replay.isNil:
    return @[]
  if typeName notin replay.territoryControlsByName:
    return @[]
  replay.territoryControlsByName[typeName]

proc getRenderName*(replay: Replay, typeName: string): string =
  ## Resolve render name for a type, falling back to typeName.
  if typeName in replay.config.game.objects:
    let cfg = replay.config.game.objects[typeName]
    if cfg.renderName.len > 0:
      return cfg.renderName
  typeName

proc parseStringArray(node: JsonNode, key: string, context: string): seq[string] =
  ## Parse a string array field from a JSON object.
  if key notin node:
    return @[]
  let arr = node[key]
  if arr.kind != JArray:
    raise newException(
      ValueError,
      "Invalid " & context & "." & key & ": expected an array of strings"
    )
  for i, item in arr.getElems():
    if item.kind != JString:
      raise newException(
        ValueError,
        "Invalid " & context & "." & key & "[" & $i & "]: expected a string"
      )
    result.add(item.getStr)

proc parseRenderAssetRule(node: JsonNode, context: string): RenderAssetRule =
  ## Parse a render asset rule from string/object JSON.
  if node.kind == JString:
    return RenderAssetRule(asset: node.getStr)
  if node.kind != JObject:
    raise newException(
      ValueError,
      "Invalid " & context & ": expected a string or object"
    )
  result.asset = getString(node, "asset")
  if result.asset.len == 0:
    raise newException(
      ValueError,
      "Invalid " & context & ".asset: expected a non-empty string"
    )
  result.resources = parseStringArray(node, "resources", context)
  result.tags = parseStringArray(node, "tags", context)

proc parseRenderAssets(renderNode: JsonNode): Table[string, seq[RenderAssetRule]] =
  ## Parse game.render.assets map from JSON.
  if renderNode.isNil or "assets" notin renderNode:
    return
  let assetsNode = renderNode["assets"]
  if assetsNode.kind != JObject:
    raise newException(
      ValueError,
      "Invalid game.render.assets: expected an object"
    )
  for key, val in assetsNode:
    let context = "game.render.assets." & key
    if val.kind == JArray:
      for i, entry in val.getElems():
        result.mgetOrPut(key, @[]).add(
          parseRenderAssetRule(entry, context & "[" & $i & "]")
        )
    else:
      result[key] = @[parseRenderAssetRule(val, context)]

proc normalizeRenderTypeName(typeName: string): string =
  ## Normalize team-prefixed/suffixed type names for asset lookup.
  let colonIdx = typeName.find(':')
  if colonIdx >= 0 and colonIdx < typeName.len - 1:
    result = typeName[colonIdx + 1 .. ^1]
  else:
    result = typeName
  const teamPrefixes = ["cogs_green_", "cogs_blue_", "cogs_red_", "cogs_yellow_", "clips_"]
  for prefix in teamPrefixes:
    if result.len > prefix.len and result[0 ..< prefix.len] == prefix:
      result = result[prefix.len .. ^1]
      break
  if result.len >= 2 and result[^2] == '_' and result[^1] in {'0'..'9'}:
    result = result[0 .. ^3]
  if result.endsWith("_station"):
    result = result[0 ..< (result.len - "_station".len)]

proc entityHasResource*(replay: Replay, entity: Entity, resourceName: string, atStep: int): bool =
  ## Return true if entity has a positive amount of a resource.
  let resourceId = replay.itemNames.find(resourceName)
  if resourceId < 0:
    return false
  let inventoryAtStep =
    if entity.inventory.len == 0:
      @[]
    else:
      entity.inventory[atStep.clamp(0, entity.inventory.len - 1)]
  for item in inventoryAtStep:
    if item.itemId == resourceId and item.count > 0:
      return true
  false

proc entityHasTag*(replay: Replay, entity: Entity, tagName: string, atStep: int): bool =
  ## Return true if entity has the named tag.
  if tagName notin replay.tags:
    return false
  if entity.tagIds.len == 0:
    return false
  let tagIdsAtStep = entity.tagIds[atStep.clamp(0, entity.tagIds.len - 1)]
  replay.tags[tagName] in tagIdsAtStep

proc matchesRenderAssetRule(
  replay: Replay,
  entity: Entity,
  rule: RenderAssetRule,
  atStep: int
): bool =
  ## Return true if entity satisfies resource/tag requirements.
  for resourceName in rule.resources:
    if not replay.entityHasResource(entity, resourceName, atStep):
      return false
  for tagName in rule.tags:
    if not replay.entityHasTag(entity, tagName, atStep):
      return false
  true

proc resolveRenderAsset*(replay: Replay, entity: Entity, atStep: int): string =
  ## Resolve render asset name from game.render.assets.
  if replay.isNil or entity.isNil:
    return ""
  var keys = @[entity.typeName]
  let normalizedTypeName = normalizeRenderTypeName(entity.typeName)
  if normalizedTypeName.len > 0 and normalizedTypeName != entity.typeName:
    keys.add(normalizedTypeName)
  for typeName in keys:
    if typeName notin replay.renderAssetsByType:
      continue
    for rule in replay.renderAssetsByType[typeName]:
      if replay.matchesRenderAssetRule(entity, rule, atStep):
        return rule.asset
  ""

proc sortByRank*(configs: Table[string, RenderHudConfig]): seq[RenderHudConfig] =
  ## Sort HUD configs by rank, filtering empty resources.
  var ordered: seq[tuple[key: string, rank: int]]
  for key, hud in configs:
    if hud.resource.len == 0:
      continue
    ordered.add((key: key, rank: hud.rank))
  sort(ordered, proc(a, b: tuple[key: string, rank: int]): int =
    let byRank = cmp(a.rank, b.rank)
    if byRank != 0: return byRank
    cmp(a.key, b.key)
  )
  for item in ordered:
    result.add(configs[item.key])

proc sortByRank*(configs: Table[string, RenderStatusBarConfig]): seq[RenderStatusBarConfig] =
  ## Sort status bar configs by rank, filtering empty resources.
  var ordered: seq[tuple[key: string, rank: int]]
  for key, status in configs:
    if status.resource.len == 0:
      continue
    ordered.add((key: key, rank: status.rank))
  sort(ordered, proc(a, b: tuple[key: string, rank: int]): int =
    let byRank = cmp(a.rank, b.rank)
    if byRank != 0: return byRank
    cmp(a.key, b.key)
  )
  for item in ordered:
    result.add(configs[item.key])

proc hudItem1*(replay: Replay): RenderHudConfig =
  ## HUD config for the primary bar.
  if replay.config.game.render.hud1.resource.len > 0:
    return replay.config.game.render.hud1
  RenderHudConfig(resource: "hp", short_name: "HP", max: 100)

proc hudItem2*(replay: Replay): RenderHudConfig =
  ## HUD config for the secondary bar.
  if replay.config.game.render.hud2.resource.len > 0:
    return replay.config.game.render.hud2
  RenderHudConfig(resource: "energy", short_name: "E", max: 20)

proc hudItems*(replay: Replay): seq[RenderHudConfig] =
  ## Pre-sorted custom HUD configs in display order.
  replay.sortedHudItems

proc statusItems*(replay: Replay, entity: Entity): seq[RenderStatusBarConfig] =
  ## Pre-sorted custom status configs in display order for an entity type.
  if replay.isNil or entity.isNil:
    return @[]
  if entity.typeName in replay.sortedStatusItems:
    return replay.sortedStatusItems[entity.typeName]
  let normalized = normalizeRenderTypeName(entity.typeName)
  if normalized in replay.sortedStatusItems:
    return replay.sortedStatusItems[normalized]
  @[]

proc parseTerritoryControls(objConfig: JsonNode, objectName: string): seq[TerritoryControl] =
  ## Parse and validate territory_controls from object config.
  if "territory_controls" notin objConfig:
    return @[]
  let controls = objConfig["territory_controls"]
  if controls.kind != JArray:
    raise newException(
      ValueError,
      "Invalid territory_controls for object '" & objectName & "': expected an array"
    )
  for i, controlNode in controls.getElems():
    if controlNode.kind != JObject:
      raise newException(
        ValueError,
        "Invalid territory_controls[" & $i & "] for object '" & objectName & "': expected an object"
      )
    var control = TerritoryControl(territory: "", strength: 1, decay: 1)
    if "territory" in controlNode:
      if controlNode["territory"].kind != JString:
        raise newException(
          ValueError,
          "Invalid territory_controls[" & $i & "].territory for object '" & objectName & "': expected a string"
        )
      control.territory = controlNode["territory"].getStr
    if "strength" in controlNode:
      let strengthNode = controlNode["strength"]
      if strengthNode.kind == JInt:
        control.strength = strengthNode.getInt
      elif strengthNode.kind == JFloat:
        control.strength = strengthNode.getFloat.int
      else:
        raise newException(
          ValueError,
          "Invalid territory_controls[" & $i & "].strength for object '" & objectName & "': expected a number"
        )
    if "decay" in controlNode:
      let decayNode = controlNode["decay"]
      if decayNode.kind == JInt:
        control.decay = decayNode.getInt
      elif decayNode.kind == JFloat:
        control.decay = decayNode.getFloat.int
      else:
        raise newException(
          ValueError,
          "Invalid territory_controls[" & $i & "].decay for object '" & objectName & "': expected a number"
        )
    if control.decay <= 0:
      raise newException(
        ValueError,
        "Invalid territory_controls[" & $i & "].decay for object '" & objectName & "': expected > 0"
      )
    if control.strength <= 0:
      continue
    result.add(control)

proc parseHook*(s: string, i: var int, v: var IVec2) =
  var arr: array[2, int32]
  parseHook(s, i, arr)
  v = ivec2(arr[0], arr[1])

proc parseHook*(s: string, i: var int, v: var IVec3) =
  var arr: array[3, int32]
  parseHook(s, i, arr)
  v = ivec3(arr[0], arr[1], arr[2])

proc parseHook*(s: string, i: var int, v: var ItemAmount) =
  var arr: array[2, int32]
  parseHook(s, i, arr)
  v = ItemAmount(itemId: arr[0], count: arr[1])

proc parseHook*(s: string, i: var int, v: var CapacityAmount) =
  var arr: array[2, int32]
  parseHook(s, i, arr)
  v = CapacityAmount(capacityId: arr[0], limit: arr[1])

proc expand[T](data: JsonNode, numSteps: int, defaultValue: T): seq[T] =
  if data == nil:
    # Use the default value.
    return @[defaultValue]
  elif data.kind == JArray:
    # For coordinates, we need to expand the sequence.
    if (data.len == 0):
      return @[defaultValue]
    elif (data[0].kind != JArray):
      # Its just a single array like value.
      return @[data.to(T)]
    else:
      # Expand the sequence.
      # A sequence of pairs is expanded to a sequence of values.
      var j = 0
      var v: T = defaultValue
      for i in 0 ..< numSteps:
        if j < data.len and data[j].kind == JArray and data[j].len >= 2 and
            data[j][0].kind == JInt and data[j][0].getInt == i:
          v = data[j][1].to(T)
          j += 1
        result.add(v)
  else:
    # A single value is a valid sequence.
    return @[data.to(T)]

proc expandInventory(data: JsonNode, numSteps: int): seq[seq[seq[int]]] =
  ## Expand inventory data, handling both static and time series formats.
  ## Static: [[itemId, count], [itemId, count], ...]
  ## Time series: [[step, [[itemId, count], ...]], [step, [[itemId, count], ...]], ...]
  if data == nil or data.kind != JArray:
    return @[]

  if data.len == 0:
    return @[newSeq[seq[int]]()]

  # Check if this is time series format by looking at the structure.
  var isTimeSeries = false
  if data[0].kind == JArray and data[0].len >= 2:
    let first = data[0][0]
    let second = data[0][1]
    if first.kind == JInt and second.kind == JArray:
      # Looks like time series: [step, inventory_array].
      isTimeSeries = true

  if isTimeSeries:
    # Time series format: use the standard expand function which handles carry-over correctly.
    let expandedRaw = expand[seq[seq[int]]](data, numSteps, @[])  # Default to empty inventory.
    return expandedRaw
  else:
    # Static format: same inventory for all steps.
    var staticInventory: seq[seq[int]]
    for itemAmount in data:
      if itemAmount.kind == JArray and itemAmount.len >= 2:
        let itemId = itemAmount[0]
        let count = itemAmount[1]
        if itemId.kind == JInt and count.kind == JInt:
          staticInventory.add(@[itemId.getInt, count.getInt])

    # Return the same static inventory for all steps.
    var expandedInventory: seq[seq[seq[int]]]
    for i in 0..<numSteps:
      expandedInventory.add(staticInventory)
    return expandedInventory

proc getExpandedIntSeq*(obj: JsonNode, key: string, maxSteps: int, default: seq[int] = @[0]): seq[int] =
  ## Get an expanded integer sequence field from JsonNode with a default if key is missing.
  if key in obj: expand[int](obj[key], maxSteps, 0) else: default

let drawnAgentActionNames =
  ["attack", "attack_nearest", "put_items", "get_items", "swap"]

proc expandSequenceV2(sequence: JsonNode, numSteps: int): JsonNode =
  ## Expand an array of [step, value] pairs into an array of values per step.
  if sequence.kind != JArray:
    return sequence
  var expanded = newJArray()
  var j = 0
  var v: JsonNode = newJNull()
  for i in 0 ..< numSteps:
    if j < sequence.len and sequence[j].kind == JArray and sequence[j][0].kind == JInt and
        sequence[j][0].getInt == i:
      v = sequence[j][1]
      inc j
    expanded.add(v)
  return expanded

proc getAttrV1(obj: JsonNode, attr: string, atStep: int, defaultValue: JsonNode): JsonNode =
  ## Gets an attribute from a grid object, respecting the current step.
  if not (attr in obj):
    return defaultValue
  let prop = obj[attr]
  if prop.kind != JArray:
    return prop
  # When the value is an array (already expanded per-step), index by step.
  if atStep >= 0 and atStep < prop.len:
    return prop[atStep]
  return defaultValue

proc convertReplayV1ToV2(replayData: JsonNode): JsonNode {.measure.} =
  ## Converts a replay from version 1 to version 2.
  echo "Converting replay from version 1 to version 2..."
  var data = newJObject()
  data["version"] = newJInt(2)

  # Action names (with renames).
  var actionNames = newJArray()
  let actionNamesArr = getArray(replayData, "action_names")
  if actionNamesArr != nil:
    for nameNode in actionNamesArr:
      var name = nameNode.getStr
      if name == "put_recipe_items":
        name = "put_items"
      elif name == "get_output":
        name = "get_items"
      actionNames.add(newJString(name))
  data["action_names"] = actionNames

  # Item names.
  let invItems = getArray(replayData, "inventory_items")
  if invItems != nil and invItems.len > 0:
    data["item_names"] = invItems
  else:
    var items = newJArray()
    for s in [
      "ore.red", "ore.blue", "ore.green", "battery", "heart", "armor", "laser", "blueprint"
    ]:
      items.add(newJString(s))
    data["item_names"] = items

  data["type_names"] = getArray(replayData, "object_types", newJArray())
  data["num_agents"] = newJInt(getInt(replayData, "num_agents", 0))
  data["max_steps"] = newJInt(getInt(replayData, "max_steps", 0))

  let maxSteps = getInt(data, "max_steps", 0)

  # Helpers.
  proc pair(a, b: JsonNode): JsonNode = (result = newJArray(); result.add(a); result.add(b))

  var objects = newJArray()
  var maxX = 0
  var maxY = 0
  let gridObjectsArr = getArray(replayData, "grid_objects", newJArray())
  for gridObject in gridObjectsArr:
    # Expand position and layer series if present.
    if "c" in gridObject:
      gridObject["c"] = expandSequenceV2(gridObject["c"], maxSteps)
    if "r" in gridObject:
      gridObject["r"] = expandSequenceV2(gridObject["r"], maxSteps)

    var location = newJArray()
    for step in 0 ..< maxSteps:
      let xNode = getAttrV1(gridObject, "c", step, newJInt(0))
      let yNode = getAttrV1(gridObject, "r", step, newJInt(0))
      let x = if xNode.kind == JInt: xNode.getInt else: 0
      let y = if yNode.kind == JInt: yNode.getInt else: 0
      var double = newJArray()
      double.add(newJInt(x))
      double.add(newJInt(y))
      location.add(pair(newJInt(step), double))
      if x > maxX: maxX = x
      if y > maxY: maxY = y

    # Inventory per step.
    var inventory = newJArray()
    let itemNames = data["item_names"]
    for i in 0 ..< itemNames.len:
      let inventoryName = itemNames[i].getStr
      let invKey = "inv:" & inventoryName
      let agentInvKey = "agent:inv:" & inventoryName
      if invKey in gridObject:
        gridObject[invKey] = expandSequenceV2(gridObject[invKey], maxSteps)
      elif agentInvKey in gridObject:
        gridObject[invKey] = expandSequenceV2(gridObject[agentInvKey], maxSteps)

    for step in 0 ..< maxSteps:
      var inventoryList = newJArray()
      for i in 0 ..< itemNames.len:
        let inventoryName = itemNames[i].getStr
        let invKey = "inv:" & inventoryName
        let amountNode = getAttrV1(gridObject, invKey, step, newJInt(0))
        var amt = 0
        if amountNode.kind == JInt:
          amt = amountNode.getInt
        if amt != 0:
          var pairNode = newJArray()
          pairNode.add(newJInt(i))
          pairNode.add(newJInt(amt))
          inventoryList.add(pairNode)
      inventory.add(pair(newJInt(step), inventoryList))

    # Build v2 object.
    var obj = newJObject()
    obj["id"] = newJInt(getInt(gridObject, "id", 0))

    let typeId = getInt(gridObject, "type", -1)
    obj["type_id"] = newJInt(typeId)
    if typeId >= 0 and "object_types" in replayData and typeId < replayData["object_types"].len:
      obj["type_name"] = replayData["object_types"][typeId]
    else:
      obj["type_name"] = newJString("")
    obj["location"] = location
    obj["inventory"] = inventory
    # Ensure orientation exists; default to 0 if missing.
    if "orientation" in gridObject:
      obj["orientation"] = gridObject["orientation"]
    else:
      obj["orientation"] = newJInt(0)

    # Default inventory_max to 0 for v1 (required by Nim loader).
    obj["inventory_max"] = newJInt(0)

    # Agent-specific fields.
    if "agent_id" in gridObject:
      obj["agent_id"] = gridObject["agent_id"]

      # is_frozen can be a series or a single value; coerce to bools.
      if "agent:frozen" in gridObject:
        let frozen = gridObject["agent:frozen"]
        if frozen.kind == JArray:
          var fr = newJArray()
          for p in frozen:
            var b = false
            if p[1].kind == JBool:
              b = p[1].getBool
            elif p[1].kind == JInt:
              b = p[1].getInt != 0
            fr.add(pair(p[0], newJBool(b)))
          obj["is_frozen"] = fr
        else:
          var b = if frozen.kind == JBool: frozen.getBool else: (if frozen.kind == JInt: frozen.getInt != 0 else: false)
          obj["is_frozen"] = newJBool(b)

      # color: prefer agent color; ensure presence for loader.
      if "agent:color" in gridObject:
        obj["color"] = gridObject["agent:color"]
      elif "color" in gridObject:
        obj["color"] = gridObject["color"]
      else:
        obj["color"] = newJInt(0)

      if "action_success" in gridObject:
        obj["action_success"] = gridObject["action_success"]
      if "animation_id" in gridObject:
        obj["animation_id"] = gridObject["animation_id"]
      obj["group_id"] = newJInt(getInt(gridObject, "agent:group", 0))
      if "agent:orientation" in gridObject:
        obj["orientation"] = gridObject["agent:orientation"]
      if "hp" in gridObject:
        obj["hp"] = gridObject["hp"]
      if "reward" in gridObject:
        obj["current_reward"] = gridObject["reward"]
      if "total_reward" in gridObject:
        obj["total_reward"] = gridObject["total_reward"]

      # Action id/param per step from combined action.
      if "action" in gridObject:
        gridObject["action"] = expandSequenceV2(gridObject["action"], maxSteps)
      var actionId = newJArray()
      var actionParam = newJArray()
      for step in 0 ..< maxSteps:
        let action = getAttrV1(gridObject, "action", step, newJNull())
        if action.kind == JArray and action.len >= 2:
          actionId.add(pair(newJInt(step), action[0]))
          actionParam.add(pair(newJInt(step), action[1]))
      obj["action_id"] = actionId
      obj["action_param"] = actionParam

    else:
      # Non-agent: ensure color exists for loader.
      if "color" in gridObject:
        obj["color"] = gridObject["color"]
      else:
        obj["color"] = newJInt(0)

    objects.add(obj)

  data["objects"] = objects
  var mapSize = newJArray()
  mapSize.add(newJInt(maxX + 1))
  mapSize.add(newJInt(maxY + 1))
  data["map_size"] = mapSize

  var mg = newJObject()
  mg["label"] = newJString("Unlabeled Replay")
  data["mg_config"] = mg

  return data

proc computeGainMap(replay: Replay) {.measure.} =
  ## Compute gain/loss for agents.
  var items = [
    newSeq[int](replay.itemNames.len),
    newSeq[int](replay.itemNames.len)
  ]
  for agent in replay.agents:
    agent.gainMap = newSeq[seq[ItemAmount]](replay.maxSteps)

    # Gain map for step 0.
    if agent.inventory.len == 1:
      let inventory = agent.inventory[0]
      var gainMap = newSeq[ItemAmount]()
      if inventory.len > 0:
        for i in 0 ..< items[0].len:
          items[0][i] = 0
        for item in inventory:
          gainMap.add(item)
          items[0][item.itemId] = item.count
      agent.gainMap[0] = gainMap

    # Gain map for step > 1.
    for i in 1 ..< replay.maxSteps:
      var gainMap = newSeq[ItemAmount]()
      if agent.inventory.len > i:
        let inventory = agent.inventory[i]
        let n = i mod 2
        for j in 0 ..< items[n].len:
          items[n][j] = 0
        for item in inventory:
          items[n][item.itemId] = item.count
        let m = 1 - n
        for j in 0 ..< replay.itemNames.len:
          if items[n][j] != items[m][j]:
            gainMap.add(ItemAmount(itemId: j, count: items[n][j] - items[m][j]))
      agent.gainMap[i] = gainMap

proc isInventoryCompressed(inventory: JsonNode): bool =
  ## Check if inventory is already in V3 compressed format [[itemId, count], ...]
  if inventory.kind != JArray or inventory.len == 0:
    return false

  for item in inventory.getElems():
    if item.kind != JArray or item.len != 2:
      return false
    let itemId = item[0]
    let count = item[1]
    if itemId.kind != JInt or count.kind != JInt:
      return false
  return true

proc compressInventoryArray(inventory: JsonNode): JsonNode =
  ## Compress a flat inventory array [itemId, itemId, ...] to [[itemId, count], ...]
  result = newJArray()
  if inventory.kind != JArray:
    return result

  var counts: seq[int]
  for itemId in inventory.getElems():
    if itemId.kind == JInt:
      let id = itemId.getInt()
      if id < 0:
        continue
      if id >= counts.len:
        counts.setLen(id + 1)
      counts[id] += 1

  for itemId, count in counts.pairs():
    if count > 0:
      var pair = newJArray()
      pair.add(newJInt(itemId))
      pair.add(newJInt(count))
      result.add(pair)

proc convertInventoryField(obj: JsonNode, fieldName: string) =
  ## Convert a single inventory field from V2 to V3 format.
  if fieldName notin obj:
    return

  let field = obj[fieldName]
  if field.kind == JArray and field.len > 0:
    # Check if this is a time series format [[step, inventory_array], ...]
    let firstItem = field[0]
    if firstItem.kind == JArray and firstItem.len == 2:
      # Time series format: convert each inventory array if needed
      var newTimeSeries = newJArray()
      var needsConversion = false
      for item in field.getElems():
        if item.kind == JArray and item.len == 2:
          let step = item[0]
          let inventoryArray = item[1]
          if inventoryArray.kind == JArray and not isInventoryCompressed(inventoryArray):
            let compressed = compressInventoryArray(inventoryArray)
            var newItem = newJArray()
            newItem.add(step)
            newItem.add(compressed)
            newTimeSeries.add(newItem)
            needsConversion = true
          else:
            newTimeSeries.add(item)
        else:
          newTimeSeries.add(item)
      if needsConversion:
        obj[fieldName] = newTimeSeries
    else:
      # Single inventory array: convert directly if needed
      if not isInventoryCompressed(field):
        obj[fieldName] = compressInventoryArray(field)
  elif field.kind == JArray and field.len == 0:
    # Empty array stays empty
    discard

proc convertReplayV2ToV3*(replayData: JsonNode): JsonNode {.measure.} =
  ## Convert a V2 replay to V3 format by compressing inventory arrays.
  ## V2: inventory as [itemId, itemId, ...] (repeated IDs)
  ## V3: inventory as [[itemId, count], [itemId, count], ...] (compressed pairs)
  echo "Converting replay from version 2 to version 3..."

  # Create a deep copy of the data.
  var data = replayData.copy()

  # Update version to 3.
  data["version"] = newJInt(3)

  # Convert inventory fields in all objects.
  if "objects" in data and data["objects"].kind == JArray:
    for obj in data["objects"].getElems():
      if obj.kind != JObject:
        continue

      # Convert inventory field
      convertInventoryField(obj, "inventory")

      # Convert recipe_input field
      convertInventoryField(obj, "recipe_input")

      # Convert recipe_output field
      convertInventoryField(obj, "recipe_output")

      # Convert input_resources and output_resources (legacy building fields)
      convertInventoryField(obj, "input_resources")

      convertInventoryField(obj, "output_resources")

  return data

proc convertReplayV3ToV4*(replayData: JsonNode): JsonNode {.measure.} =
  ## Convert a V3 replay to V4 format by ensuring new V4 fields exist.
  ## V4 adds: policy_env_interface, infos
  echo "Converting replay from version 3 to version 4..."

  # Create a deep copy of the data.
  var data = replayData.copy()

  # Update version to 4.
  data["version"] = newJInt(4)

  # Add policy_env_interface if missing (empty object as default).
  if "policy_env_interface" notin data:
    data["policy_env_interface"] = newJObject()

  # Add infos if missing (empty object as default).
  if "infos" notin data:
    data["infos"] = newJObject()

  # Add alive=[[0, true]] to all objects that don't have it.
  if "objects" in data and data["objects"].kind == JArray:
    for obj in data["objects"].getElems():
      if obj.kind == JObject and "alive" notin obj:
        var entry = newJArray()
        entry.add(newJInt(0))
        entry.add(newJBool(true))
        var aliveSeries = newJArray()
        aliveSeries.add(entry)
        obj["alive"] = aliveSeries

  return data

proc loadReplayString*(jsonData: string, fileName: string): Replay {.measure.} =
  ## Load a replay from a string.
  measurePush("loadReplayString.parseJson")
  var jsonObj = fromJson(jsonData)
  measurePop()

  measurePush("loadReplayString.versionConvert")
  if getInt(jsonObj, "version") == 1:
    jsonObj = convertReplayV1ToV2(jsonObj)

  if getInt(jsonObj, "version") == 2:
    jsonObj = convertReplayV2ToV3(jsonObj)

  if getInt(jsonObj, "version") == 3:
    jsonObj = convertReplayV3ToV4(jsonObj)
  measurePop()

  let fileVersion = getInt(jsonObj, "version")
  if fileVersion != FormatVersion:
    raise newException(ValueError, "Unsupported replay version. This app supports version " & $FormatVersion & ", but the file is version " & $fileVersion & ". Please update the app to load this replay.")

  measurePush("loadReplayString.validate")
  # Check for validation issues and log them to console.
  let issues = validateReplay(jsonObj)
  let showValidation = getEnv("METTASCOPE_SHOW_VALIDATION", "").toLowerAscii() in ["1", "true", "yes"]
  if showValidation:
    if issues.len > 0:
      issues.prettyPrint()
    else:
      echo "No validation issues found"
  measurePop()

  measurePush("loadReplayString.parseMetadata")
  # Safe access to required fields with defaults.
  let version = getInt(jsonObj, "version", FormatVersion)
  let actionNamesArr = getArray(jsonObj, "action_names")
  let actionNames = if actionNamesArr != nil: actionNamesArr.to(seq[string]) else: @[]
  let itemNamesArr = getArray(jsonObj, "item_names")
  let itemNames = if itemNamesArr != nil: itemNamesArr.to(seq[string]) else: @[]
  let typeNamesArr = getArray(jsonObj, "type_names")
  let typeNames = if typeNamesArr != nil: typeNamesArr.to(seq[string]) else: @[]
  let numAgents = getInt(jsonObj, "num_agents", 0)
  let maxSteps = getInt(jsonObj, "max_steps", 0)

  let replay = Replay(
    version: version,
    actionNames: actionNames,
    itemNames: itemNames,
    typeNames: typeNames,
    numAgents: numAgents,
    maxSteps: maxSteps,
    mapSize: getMapSize(jsonObj)
  )

  for actionName in drawnAgentActionNames:
    let idx = replay.actionNames.find(actionName)
    if idx != -1:
      replay.drawnAgentActionMask = replay.drawnAgentActionMask or (1'u64 shl idx)
  replay.fileName = getString(jsonObj, "file_name")

  let animationNamesArr = getArray(jsonObj, "animation_names")
  replay.animationNames = if animationNamesArr != nil: animationNamesArr.to(seq[string]) else: @["none", "bump"]

  let mgConfig = getJsonNode(jsonObj, "mg_config")
  if mgConfig != nil:
    replay.mgConfig = mgConfig
    replay.config = fromJson($mgConfig, Config)
    let renderNode =
      if "game" in mgConfig and "render" in mgConfig["game"]:
        mgConfig["game"]["render"]
      else:
        nil
    replay.renderAssetsByType = parseRenderAssets(renderNode)
    if "game" in mgConfig and "objects" in mgConfig["game"]:
      let objects = mgConfig["game"]["objects"]
      if objects.kind == JObject:
        for key, val in objects:
          let name =
            if "name" in val and val["name"].kind == JString:
              val["name"].getStr
            else:
              key
          let territoryControls = parseTerritoryControls(val, name)
          replay.objectConfigsByName[name] = val
          replay.territoryControlsByName[name] = territoryControls
          if key != name:
            replay.objectConfigsByName[key] = val
            replay.territoryControlsByName[key] = territoryControls

  # Parse tags.
  let tagsObj = getJsonNode(jsonObj, "tags")
  if tagsObj != nil and tagsObj.kind == JObject:
    for key, val in tagsObj:
      replay.tags[key] = val.getInt
  measurePop()

  # Parse capacity_names (maps capacity_id to group name like "cargo", "gear").
  let capacityNamesArr = getArray(jsonObj, "capacity_names")
  if capacityNamesArr != nil:
    for nameNode in capacityNamesArr:
      replay.capacityNames.add(nameNode.getStr)

  measurePush("loadReplayString.parseObjects")
  let objectsArr = getArray(jsonObj, "objects", newJArray())
  for obj in objectsArr:

    var inventory: seq[seq[ItemAmount]]
    if "inventory" in obj:
      let inventoryRaw = expandInventory(obj["inventory"], replay.maxSteps)
      for i in 0 ..< inventoryRaw.len:
        var itemAmounts: seq[ItemAmount]
        for itemPair in inventoryRaw[i]:
          if itemPair.len >= 2:
            itemAmounts.add(ItemAmount(
              itemId: itemPair[0],
              count: itemPair[1]
            ))
        inventory.add(itemAmounts)

    # Parse inventory_capacities: same format as inventory but capacity_id instead of item_id.
    var inventoryCapacities: seq[seq[CapacityAmount]]
    if "inventory_capacities" in obj:
      let capsRaw = expandInventory(obj["inventory_capacities"], replay.maxSteps)
      for i in 0 ..< capsRaw.len:
        var capAmounts: seq[CapacityAmount]
        for capPair in capsRaw[i]:
          if capPair.len >= 2:
            capAmounts.add(CapacityAmount(
              capacityId: capPair[0],
              limit: capPair[1]
            ))
        inventoryCapacities.add(capAmounts)

    var location: seq[IVec2]
    if "location" in obj:
      let locationRaw = expand[seq[int]](obj["location"], replay.maxSteps, @[0, 0])
      for coords in locationRaw:
        if coords.len >= 2:
          location.add(ivec2(coords[0].int32, coords[1].int32))
        else:
          location.add(ivec2(0, 0))
    else:
      location = @[ivec2(0, 0)]

    var resolvedTypeName = getString(obj, "type_name", "unknown")

    if resolvedTypeName == "unknown":
      let candidateId = getInt(obj, "type_id", -1)
      if candidateId >= 0 and candidateId < replay.typeNames.len:
        resolvedTypeName = replay.typeNames[candidateId]

    let entity = Entity(
      id: obj.getInt("id", 0),
      typeName: resolvedTypeName,
      renderName: replay.getRenderName(resolvedTypeName),
      location: location,
      orientation: obj.getExpandedIntSeq("orientation", replay.maxSteps),
      inventory: inventory,
      inventoryMax: obj.getInt("inventory_max", 0),
      inventoryCapacities: inventoryCapacities,
      color: obj.getExpandedIntSeq("color", replay.maxSteps),
    )
    entity.groupId = getInt(obj, "group_id", 0)

    let tagIdsField = getJsonNode(obj, "tag_ids")
    if tagIdsField != nil:
      entity.tagIds = expand[seq[int]](tagIdsField, replay.maxSteps, @[])

    entity.isAgent = resolvedTypeName == "agent"
    if "agent_id" in obj:
      entity.agentId = getInt(obj, "agent_id", 0)
      let frozenField = getJsonNodeOr(obj, "frozen", "is_frozen", newJBool(false))
      entity.isFrozen = expand[bool](frozenField, replay.maxSteps, false)
      let actionIdField = getJsonNode(obj, "action_id", newJInt(0))
      entity.actionId = expand[int](actionIdField, replay.maxSteps, 0)
      let actionParamField = getJsonNodeOr(obj, "action_parameter", "action_param", newJInt(0))
      entity.actionParameter = expand[int](actionParamField, replay.maxSteps, 0)
      let actionSuccessField = getJsonNode(obj, "action_success", newJBool(false))
      entity.actionSuccess = expand[bool](actionSuccessField, replay.maxSteps, false)
      let animationField = getJsonNode(obj, "animation_id", newJInt(0))
      entity.animationId = expand[int](animationField, replay.maxSteps, 0)
      let currentRewardField = getJsonNode(obj, "current_reward", newJFloat(0.0))
      entity.currentReward = expand[float](currentRewardField, replay.maxSteps, 0)
      let totalRewardField = getJsonNode(obj, "total_reward", newJFloat(0.0))
      entity.totalReward = expand[float](totalRewardField, replay.maxSteps, 0)
      let frozenProgressField = getJsonNode(obj, "frozen_progress")
      if frozenProgressField != nil:
        entity.frozenProgress = expand[int](frozenProgressField, replay.maxSteps, 0)
      else:
        entity.frozenProgress = @[0]
      entity.frozenTime = getInt(obj, "frozen_time", 0)
      entity.visionSize = getInt(obj, "vision_size", 13)

      let vibeIdField = getJsonNode(obj, "vibe_id")
      if vibeIdField != nil:
        entity.vibeId = expand[int](vibeIdField, replay.maxSteps, 0)

    if "input_resources" in obj:
      for pair in obj["input_resources"]:
        if pair.kind == JArray and pair.len >= 2:
          entity.inputResources.add(ItemAmount(
            itemId: if pair[0].kind == JInt: pair[0].getInt else: 0,
            count: if pair[1].kind == JInt: pair[1].getInt else: 0
          ))
    if "output_resources" in obj:
      for pair in obj["output_resources"]:
        if pair.kind == JArray and pair.len >= 2:
          entity.outputResources.add(ItemAmount(
            itemId: if pair[0].kind == JInt: pair[0].getInt else: 0,
            count: if pair[1].kind == JInt: pair[1].getInt else: 0
          ))
      if "recipe_max" in obj:
        entity.recipeMax = obj["recipe_max"].getInt
      else:
        entity.recipeMax = 0
      if "production_progress" in obj:
        entity.productionProgress = expand[int](obj["production_progress"],
            replay.maxSteps, 0)
      else:
        entity.productionProgress = @[0]
      if "production_time" in obj:
        entity.productionTime = obj["production_time"].getInt
      else:
        entity.productionTime = 0
      if "cooldown_progress" in obj:
        entity.cooldownProgress = expand[int](obj["cooldown_progress"],
            replay.maxSteps, 0)
      else:
        entity.cooldownProgress = @[0]
      if "cooldown_time" in obj:
        entity.cooldownTime = obj["cooldown_time"].getInt
      else:
        entity.cooldownTime = 0

    # Also read cooldown_duration for converters (overlaps with hub field).
    if "cooldown_duration" in obj and entity.cooldownDuration == 0:
      entity.cooldownDuration = getInt(obj, "cooldown_duration", 0)

    # Lifecycle: alive flag (defaults to true for backwards compatibility).
    if "alive" in obj:
      entity.alive = expand[bool](obj["alive"], replay.maxSteps, true)
    else:
      entity.alive = @[true]

    # Policy info is sourced from streamed replay steps only.
    entity.policyInfos = @[newJNull()]
    entity.dialogueAppend = if "dialogue_append" in obj: expand[string](obj["dialogue_append"], replay.maxSteps, "") else: @[""]
    entity.dialogueReset = if "dialogue_reset" in obj: expand[bool](obj["dialogue_reset"], replay.maxSteps, false) else: @[false]

    if "protocols" in obj:
      entity.protocols = fromJson($(obj["protocols"]), seq[Protocol])

    replay.objects.add(entity)

    # Populate the agents field for agent entities.
    if "agent_id" in obj:
      replay.agents.add(entity)
  measurePop()

  # Compute gain maps for static replays.
  computeGainMap(replay)

  # Cache common action IDs for fast lookup.
  replay.noopActionId = replay.actionNames.find("noop")
  replay.attackActionId = replay.actionNames.find("attack")
  replay.putItemsActionId = replay.actionNames.find("put_items")
  replay.getItemsActionId = replay.actionNames.find("get_items")
  replay.moveNorthActionId = replay.actionNames.find("move_north")
  replay.moveSouthActionId = replay.actionNames.find("move_south")
  replay.moveWestActionId = replay.actionNames.find("move_west")
  replay.moveEastActionId = replay.actionNames.find("move_east")

  # Pre-sort HUD and status bar configs by rank so render loops skip sorting.
  replay.sortedHudItems = sortByRank(replay.config.game.render.agent_huds)
  for typeName, statusMap in replay.config.game.render.object_status:
    replay.sortedStatusItems[typeName] = sortByRank(statusMap)

  return replay

proc loadReplay*(data: string, fileName: string): Replay {.measure.} =
  ## Load a replay from a string.
  if fileName.endsWith(".json"):
    return loadReplayString(data, fileName)

  if not (fileName.endsWith(".json.gz") or fileName.endsWith(".json.z")):
    # TODO: Show error to user.
    echo "Unrecognized replay extension: ", fileName
    return Replay()

  let expectedFormat =
    if fileName.endsWith(".json.gz"):
      dfGzip
    else: # fileName.endsWith(".json.z"):
      dfZlib

  let jsonData =
    try:
      zippy.uncompress(data, dataFormat = expectedFormat)
    except ZippyError:
      # TODO: Show error to user.
      echo "Error uncompressing replay: ", getCurrentExceptionMsg()
      return Replay()
  return loadReplayString(jsonData, fileName)

proc loadReplay*(fileName: string): Replay {.measure.} =
  ## Load a replay from a file.
  let data = readFile(fileName)
  return loadReplay(data, fileName)

proc apply*(replay: Replay, step: int, objects: seq[ReplayEntity]) {.measure.} =
  ## Apply a replay step to the replay.
  const agentTypeName = "agent"
  for obj in objects:
    let index = obj.id - 1
    while index >= replay.objects.len:
      replay.objects.add(Entity(id: obj.id))

    let entity = replay.objects[index]
    doAssert entity.id == obj.id, "Object id mismatch"

    var resolvedTypeName = obj.typeName
    if resolvedTypeName.len == 0 and obj.typeId >= 0 and obj.typeId < replay.typeNames.len:
      resolvedTypeName = replay.typeNames[obj.typeId]
    entity.typeName = resolvedTypeName
    entity.renderName = replay.getRenderName(resolvedTypeName)
    entity.isAgent = resolvedTypeName == agentTypeName
    entity.groupId = obj.groupId
    entity.tagIds.add(obj.tagIds)
    entity.agentId = obj.agentId
    entity.location.add(obj.location)
    entity.orientation.add(obj.orientation)
    entity.inventory.add(obj.inventory)
    entity.inventoryMax = obj.inventoryMax
    entity.inventoryCapacities.add(obj.inventoryCapacities)
    entity.color.add(obj.color)
    entity.vibeId.add(obj.vibeId)
    entity.actionId.add(obj.actionId)
    entity.actionParameter.add(obj.actionParameter)
    entity.actionSuccess.add(obj.actionSuccess)
    entity.animationId.add(obj.animationId)
    entity.currentReward.add(obj.currentReward)
    entity.totalReward.add(obj.totalReward)
    entity.isFrozen.add(obj.isFrozen)
    entity.frozenProgress.add(obj.frozenProgress)
    entity.frozenTime = obj.frozenTime
    entity.visionSize = obj.visionSize
    entity.inputResources = obj.inputResources
    entity.outputResources = obj.outputResources
    entity.recipeMax = obj.recipeMax
    entity.productionProgress.add(obj.productionProgress)
    entity.productionTime = obj.productionTime
    entity.cooldownProgress.add(obj.cooldownProgress)
    entity.cooldownTime = obj.cooldownTime

    entity.alive.add(obj.alive)

    entity.cooldownRemaining.add(obj.cooldownRemaining)
    entity.cooldownDuration = obj.cooldownDuration
    entity.usesCount.add(obj.usesCount)
    entity.maxUses = obj.maxUses
    entity.allowPartialUsage = obj.allowPartialUsage
    entity.protocols = obj.protocols
    if not obj.policyInfos.isNil:
      entity.policyInfos.add(obj.policyInfos)
    else:
      if entity.policyInfos.len > 0:
        entity.policyInfos.add(entity.policyInfos[^1])
      else:
        entity.policyInfos.add(newJNull())
    entity.dialogueAppend.add(obj.dialogueAppend)
    entity.dialogueReset.add(obj.dialogueReset)

  # Mark objects as dead if they existed before but weren't in this step.
  if replay.objects.len > 0:
    var seenIds = newSeq[bool](replay.objects.len)
    for obj in objects:
      let index = obj.id - 1
      if index < seenIds.len:
        seenIds[index] = true
    for i in 0 ..< replay.objects.len:
      let entity = replay.objects[i]
      if entity.alive.len > 0 and not seenIds[i]:
        # Static types like "wall" are only sent on step 0 by the Python
        # renderer (ignore_types = ["wall"]).  Their absence in later steps
        # does NOT mean they died, so skip them.
        if entity.typeName == "wall":
          continue
        # Object was not in this step - mark as dead if currently alive.
        if entity.alive[^1]:
          entity.alive.add(false)
        else:
          # Already dead, just extend the series.
          entity.alive.add(false)

  # Extend the max steps.
  replay.maxSteps = max(replay.maxSteps, step + 1)

  # Populate the agents field for agent entities.
  if replay.agents.len == 0:
    for obj in replay.objects:
      if obj.typeName == agentTypeName:
        replay.agents.add(obj)
    doAssert replay.agents.len == replay.numAgents, "Agents and numAgents mismatch"

  computeGainMap(replay)

proc apply*(replay: Replay, replayStepJsonData: string) =
  ## Apply a replay step to the replay.
  let replayStep = fromJson(replayStepJsonData, ReplayStep)
  if replayStep.tutorial_overlay_phases.len > 0:
    replay.tutorialOverlayPhases = replayStep.tutorial_overlay_phases
    replay.tutorialOverlayPhase = replay.tutorialOverlayPhase.clamp(0, replay.tutorialOverlayPhases.len - 1)
    replay.tutorialOverlay = replay.tutorialOverlayPhases[replay.tutorialOverlayPhase]
  elif replayStep.tutorial_overlay.len > 0:
    replay.tutorialOverlayPhases = @[replayStep.tutorial_overlay]
    replay.tutorialOverlayPhase = 0
    replay.tutorialOverlay = replayStep.tutorial_overlay
  replay.apply(replayStep.step, replayStep.objects)
