## Generic stacked area chart for per-collective stats over time.
## Displays a normalized stacked area chart showing the relative share
## of a stat across collectives at each timestep.
## Includes "neutral" as a virtual collective for unaligned objects.

import
  std/[tables, strformat],
  chroma, vmath, windy, silky, bumpy,
  common, replays, aoepanel

const
  MinStatChartHeight* = 20f
  MaxStatChartHeight* = 200f
  BackgroundColor = parseHtmlColor("#1A2A3A").rgbx
  PositionLineColor = rgbx(255, 255, 255, 200)
  NeutralColor = parseHtmlColor("#808080").color  # Grey for neutral
  DragHandleHeight = 6f  # Height of the drag handle at the top
  DragHandleColor = parseHtmlColor("#3A4A5A").rgbx

var
  isDraggingStatChart*: bool = false
  dragStartY: float32 = 0
  dragStartHeight: float32 = 0

proc StatChartHeight*(): float32 =
  ## Get current stat chart height from settings.
  settings.statChartHeight

type
  StatChart* = object
    statName*: string       ## e.g. "aligned.junction"
    objectType*: string     ## e.g. "junction" - used to count total objects
    label*: string          ## display label for tooltip
    # Cached series: [collectiveIdx][step] = normalized value (0..1)
    # Index 0 is always "neutral", rest are collectives
    collectiveNames*: seq[string]
    cachedStacked*: seq[seq[float32]]  ## [collectiveIdx][step] = cumulative top edge (0..1)
    lastReplayPtr: pointer
    lastMaxSteps: int

proc newStatChart*(statName, objectType, label: string): StatChart =
  StatChart(
    statName: statName,
    objectType: objectType,
    label: label,
    lastReplayPtr: nil,
    lastMaxSteps: 0,
  )

proc countObjectsOfType(objectType: string): int =
  ## Count objects of a given type in the replay.
  if replay.isNil:
    return 0
  for obj in replay.objects:
    if obj.typeName == objectType and obj.removedAtStep < 0:
      result += 1

proc rebuildCache(chart: var StatChart) =
  ## Rebuild the cached stacked series from replay data.
  ## Includes neutral as index 0, then collectives.
  chart.collectiveNames = @[]
  chart.cachedStacked = @[]

  if replay.isNil:
    return

  let numCollectives = getNumCollectives()

  # Always include neutral first, then collectives.
  chart.collectiveNames.add("neutral")
  for i in 0 ..< numCollectives:
    chart.collectiveNames.add(getCollectiveName(i))

  let totalSlots = numCollectives + 1  # +1 for neutral
  let maxSteps = replay.maxSteps
  if maxSteps <= 0:
    return

  # Count total objects of the tracked type.
  let totalObjects = countObjectsOfType(chart.objectType).float32

  # Build raw values: [slotIdx][step] = stat value
  # Index 0 = neutral, Index 1+ = collectives
  var raw: seq[seq[float32]] = newSeq[seq[float32]](totalSlots)
  for i in 0 ..< totalSlots:
    raw[i] = newSeq[float32](maxSteps)

  # Fill from snapshots for each collective (indices 1+).
  for i in 0 ..< numCollectives:
    let name = getCollectiveName(i)
    if name notin replay.collectiveStats:
      continue
    let snapshots = replay.collectiveStats[name]
    var snapshotIdx = 0
    var currentValue: float32 = 0
    for s in 0 ..< maxSteps:
      while snapshotIdx < snapshots.len and snapshots[snapshotIdx].step <= s:
        if chart.statName in snapshots[snapshotIdx].stats:
          currentValue = snapshots[snapshotIdx].stats[chart.statName].float32
        snapshotIdx += 1
      raw[i + 1][s] = currentValue  # +1 because index 0 is neutral

  # Compute neutral = total - sum(all collectives).
  for s in 0 ..< maxSteps:
    var alignedSum: float32 = 0
    for i in 1 ..< totalSlots:
      alignedSum += raw[i][s]
    raw[0][s] = max(0, totalObjects - alignedSum)

  # Normalize and compute cumulative stacked values.
  chart.cachedStacked = newSeq[seq[float32]](totalSlots)
  for i in 0 ..< totalSlots:
    chart.cachedStacked[i] = newSeq[float32](maxSteps)

  for s in 0 ..< maxSteps:
    var total: float32 = 0
    for i in 0 ..< totalSlots:
      total += raw[i][s]
    var cumulative: float32 = 0
    for i in 0 ..< totalSlots:
      let normalized = if total > 0: raw[i][s] / total else: 0
      cumulative += normalized
      chart.cachedStacked[i][s] = cumulative

  chart.lastReplayPtr = cast[pointer](replay)
  chart.lastMaxSteps = maxSteps

proc ensureCache*(chart: var StatChart) =
  if cast[pointer](replay) != chart.lastReplayPtr or
     replay.maxSteps != chart.lastMaxSteps:
    chart.rebuildCache()

proc handleStatChartDrag*(pos: Vec2, height: float32) =
  ## Handle drag-to-resize for the stat chart.
  let mousePos = window.mousePos.vec2
  let dragHandleRect = rect(pos.x, pos.y, window.size.x.float32, DragHandleHeight)

  # Check if mouse is over drag handle.
  let overHandle = mousePos.x >= dragHandleRect.x and
                   mousePos.x <= dragHandleRect.x + dragHandleRect.w and
                   mousePos.y >= dragHandleRect.y and
                   mousePos.y <= dragHandleRect.y + dragHandleRect.h

  # Start dragging.
  if window.buttonPressed[MouseLeft] and overHandle:
    isDraggingStatChart = true
    dragStartY = mousePos.y
    dragStartHeight = settings.statChartHeight

  # Stop dragging.
  if not window.buttonDown[MouseLeft]:
    isDraggingStatChart = false

  # Update height while dragging.
  if isDraggingStatChart:
    let deltaY = dragStartY - mousePos.y  # Dragging up increases height
    settings.statChartHeight = clamp(
      dragStartHeight + deltaY,
      MinStatChartHeight,
      MaxStatChartHeight
    )
    sk.cursor = Cursor(kind: ResizeUpDownCursor)
  elif overHandle:
    sk.cursor = Cursor(kind: ResizeUpDownCursor)

proc drawStatChart*(chart: var StatChart, pos, size: Vec2) =
  ## Draw the stacked area chart with drag handle.
  chart.ensureCache()

  let stacked = chart.cachedStacked
  let names = chart.collectiveNames
  if stacked.len == 0:
    return

  let maxSteps = replay.maxSteps
  if maxSteps <= 0:
    return

  let numCollectives = stacked.len

  # Handle drag-to-resize.
  handleStatChartDrag(pos, size.y)

  # Draw drag handle at top.
  sk.drawRect(pos, vec2(size.x, DragHandleHeight), DragHandleColor)

  # Draw chart content below handle.
  let chartPos = vec2(pos.x, pos.y + DragHandleHeight)
  let chartSize = vec2(size.x, size.y - DragHandleHeight)

  ribbon(chartPos, chartSize, BackgroundColor):
    let barPos = sk.pos
    let barSize = sk.size

    # Draw stacked area: iterate each x-pixel.
    let pixelWidth = barSize.x
    for px in 0 ..< pixelWidth.int:
      let xRatio = px.float32 / pixelWidth
      let stepF = xRatio * maxSteps.float32
      let s = clamp(stepF.int, 0, maxSteps - 1)

      var prevY: float32 = 0
      for i in 0 ..< numCollectives:
        let topY = stacked[i][s]
        let y0 = barPos.y + barSize.y * (1.0 - topY)
        let y1 = barPos.y + barSize.y * (1.0 - prevY)
        let bandHeight = y1 - y0
        if bandHeight > 0.5:
          # Index 0 is neutral (grey), rest use collective colors.
          let aoeColor = if i == 0: NeutralColor else: getAoeColor(i - 1)
          let col = rgbx(
            (aoeColor.r * 255).uint8,
            (aoeColor.g * 255).uint8,
            (aoeColor.b * 255).uint8,
            200
          )
          sk.drawRect(vec2(barPos.x + px.float32, y0), vec2(1, bandHeight), col)
        prevY = topY

    # Draw current position indicator.
    let posX = (step.float32 / maxSteps.float32) * barSize.x
    sk.drawRect(
      vec2(barPos.x + posX - 0.5, barPos.y),
      vec2(1, barSize.y),
      PositionLineColor,
    )

    # Tooltip on mouseover.
    let mousePos = window.mousePos.vec2
    if mouseInsideClip(rect(barPos, barSize)):
      let mouseXRatio = (mousePos.x - barPos.x) / barSize.x
      let mouseStep = clamp((mouseXRatio * maxSteps.float32).int, 0, maxSteps - 1)
      let mouseYRatio = 1.0 - (mousePos.y - barPos.y) / barSize.y

      # Find which band the mouse is in.
      var hoveredCollective = -1
      var prevTop: float32 = 0
      for i in 0 ..< numCollectives:
        let topY = stacked[i][mouseStep]
        if mouseYRatio >= prevTop and mouseYRatio < topY:
          hoveredCollective = i
          break
        prevTop = topY

      if hoveredCollective >= 0:
        let prevVal = if hoveredCollective > 0: stacked[hoveredCollective - 1][mouseStep] else: 0f
        let pct = (stacked[hoveredCollective][mouseStep] - prevVal) * 100
        let label = &"{names[hoveredCollective]}: {pct:.0f}%"
        sk.at = vec2(mousePos.x + 8, barPos.y - 20)
        text(label)
