## Custom HUD rendering for configurable status bars in the center panel.
## Used only when object_status is explicitly set in the render config.
import
  std/[tables],
  vmath, silky, silky/atlas, chroma,
  ../[common, replays, colors]

proc getInventoryItem(entity: Entity, itemName: string, atStep: int = step): int =
  ## Get the count of a named item in the entity's inventory at a given step.
  let itemId = replay.itemNames.find(itemName)
  if itemId < 0:
    return 0
  let inv = entity.inventory.at(atStep)
  for item in inv:
    if item.itemId == itemId:
      return item.count
  return 0

proc hasCustomHuds*(replay: Replay): bool =
  ## True when agent_huds is explicitly configured.
  replay.sortedHudItems.len > 0

proc hasCustomStatus*(replay: Replay, entity: Entity): bool =
  ## True when object_status is configured for this entity type.
  if replay.isNil or entity.isNil:
    return false
  entity.typeName in replay.sortedStatusItems or
    normalizeTypeName(entity.typeName) in replay.sortedStatusItems

proc drawCustomStatBar*(panelPos: Vec2, label: string, value: int,
    maxValue: int, divisions: int, delta: int) =
  ## Draw a labeled segmented stat bar in the center panel.
  const
    LabelOffset = vec2(0, -17)
    OuterOffset = vec2(39, 0)
    OuterSize = vec2(260, 20)
    BorderPx = 1
    InnerGapPx = 1
    SegmentGapPx = 1
  let
    outerPos = panelPos + OuterOffset
    safeMax = max(maxValue, 1)
    safeDivisions = max(divisions, 1)
    totalFilled = clamp(
      value.float32 / safeMax.float32 * safeDivisions.float32,
      0.0f, safeDivisions.float32)
    previousValue = value - delta
    previousFilled = clamp(
      previousValue.float32 / safeMax.float32 * safeDivisions.float32,
      0.0f, safeDivisions.float32)
    deltaStart = min(totalFilled, previousFilled)
    deltaEnd = max(totalFilled, previousFilled)
    outerX = outerPos.x.int
    outerY = outerPos.y.int
    outerW = OuterSize.x.int
    outerH = OuterSize.y.int
    innerX = outerX + BorderPx + InnerGapPx
    innerY = outerY + BorderPx + InnerGapPx
    innerW = max(0, outerW - 2 * (BorderPx + InnerGapPx))
    innerH = max(0, outerH - 2 * (BorderPx + InnerGapPx))
    text =
      if label.len >= 2:
        label[0..1]
      else:
        label
  discard sk.drawText("pixelated", text, panelPos + LabelOffset, Yellow,
    clip = false)
  # Stroke-only border.
  sk.drawRect(
    vec2(outerX.float32, outerY.float32),
    vec2(outerW.float32, BorderPx.float32), Yellow)
  sk.drawRect(
    vec2(outerX.float32, (outerY + outerH - BorderPx).float32),
    vec2(outerW.float32, BorderPx.float32), Yellow)
  sk.drawRect(
    vec2(outerX.float32, outerY.float32),
    vec2(BorderPx.float32, outerH.float32), Yellow)
  sk.drawRect(
    vec2((outerX + outerW - BorderPx).float32, outerY.float32),
    vec2(BorderPx.float32, outerH.float32), Yellow)
  # Segmented fill with 1px gaps and integer pixel widths.
  let
    totalGap = SegmentGapPx * (safeDivisions - 1)
    usableW = max(0, innerW - totalGap)
    baseSegW =
      if safeDivisions > 0: usableW div safeDivisions
      else: 0
    remainder =
      if safeDivisions > 0: usableW mod safeDivisions
      else: 0
  var segmentX = innerX
  for i in 0 ..< safeDivisions:
    let segmentW = baseSegW + (if i < remainder: 1 else: 0)
    if segmentW > 0:
      let segmentFillRatio = clamp(totalFilled - i.float32, 0.0f, 1.0f)
      let segmentFillW = clamp(
        (segmentW.float32 * segmentFillRatio + 0.5f).int, 0, segmentW)
      if segmentFillW > 0:
        sk.drawRect(
          vec2(segmentX.float32, innerY.float32),
          vec2(segmentFillW.float32, innerH.float32),
          Yellow)
      # White delta segment at the changing edge.
      let
        segmentDeltaStart = clamp(deltaStart - i.float32, 0.0f, 1.0f)
        segmentDeltaEnd = clamp(deltaEnd - i.float32, 0.0f, 1.0f)
        segmentDeltaW = clamp(
          (segmentW.float32 * (segmentDeltaEnd - segmentDeltaStart) + 0.5f).int,
          0, segmentW)
      if segmentDeltaW > 0:
        let segmentDeltaX = segmentX + clamp(
          (segmentW.float32 * segmentDeltaStart + 0.5f).int, 0, segmentW)
        sk.drawRect(
          vec2(segmentDeltaX.float32, innerY.float32),
          vec2(segmentDeltaW.float32, innerH.float32),
          rgbx(255, 255, 255, 255))
    segmentX += segmentW + SegmentGapPx

proc drawCustomStatusBars*(selected: Entity, bcPos: Vec2): int =
  ## Draw custom status bars for the selected entity. Returns bar count.
  let
    prevStep = max(0, step - 1)
    statusConfigs = replay.statusItems(selected)
  for i, statusCfg in statusConfigs:
    let
      hud = getInventoryItem(selected, statusCfg.resource)
      prevHud = getInventoryItem(selected, statusCfg.resource, prevStep)
      deltaHud = hud - prevHud
      yOffset = 84 + i * 34
    drawCustomStatBar(
      bcPos + vec2(69, yOffset.float32),
      statusCfg.short_name,
      hud,
      statusCfg.max,
      statusCfg.divisions,
      deltaHud,
    )
  statusConfigs.len

proc customStatusResources*(selected: Entity): seq[string] =
  ## Resources shown by custom status bars, to exclude from the resource list.
  let statusConfigs = replay.statusItems(selected)
  for statusCfg in statusConfigs:
    result.add(statusCfg.resource)

type CustomResources* = tuple
  resources: seq[tuple[icon: string, amount: int]]
  anchor: Vec2

proc collectCustomResources*(
    selected: Entity, bcPos: Vec2): CustomResources =
  ## Collect inventory items for a custom-status entity, excluding status bars.
  let statusResources = customStatusResources(selected)
  var resources: seq[tuple[icon: string, amount: int]] = @[]
  for item in selected.inventory.at:
    if item.count <= 0 or item.itemId < 0 or
        item.itemId >= replay.itemNames.len:
      continue
    let
      itemName = replay.itemNames[item.itemId]
      itemIcon = "resources/" & itemName
    if itemName in @["hp", "energy", "solar"]:
      continue
    if itemName in statusResources:
      continue
    if itemIcon notin sk.atlas.entries:
      continue
    resources.add((icon: itemIcon, amount: item.count))
  let statusCount = replay.statusItems(selected).len
  result = (
    resources: resources,
    anchor: vec2(
      bcPos.x + 59,
      bcPos.y + max(112, 88 + statusCount * 34).float32
    )
  )
