import
  std/[strformat, tables],
  opengl,
  bumpy, vmath, windy, silky, silky/atlas, chroma,
  common, worldmap, panels, configs,
  replays, collectives, colors, minimap, actions, cognames, timelineslider

var
  pendingCenter: Vec2
  hasPendingCenter = false
  moveToggleActive = false
  queueToggleActive = false
  repeatToggleActive = false
  timeLineDragging = false

proc applyModeSwitchCenter*(zoomInfo: ZoomInfo) =
  ## Applies the stored world center after a mode switch once the rect is set.
  if not hasPendingCenter:
    return

  let
    rectW = zoomInfo.rect.w.float32
    rectH = zoomInfo.rect.h.float32
    z = zoomInfo.zoom * zoomInfo.zoom

  if rectW > 0 and rectH > 0 and z > 0:
    zoomInfo.pos.x = rectW / 2.0f - pendingCenter.x * z
    zoomInfo.pos.y = rectH / 2.0f - pendingCenter.y * z

  hasPendingCenter = false

proc switchGameMode*(newMode: GameMode) =
  ## Used for runtime mode switching (F11 key) between editor and game modes.

  var
    centerX: float32
    centerY: float32
    hasCenter = false

  let
    oldRectW = worldMapZoomInfo.rect.w.float32
    oldRectH = worldMapZoomInfo.rect.h.float32
    oldZ = worldMapZoomInfo.zoom * worldMapZoomInfo.zoom

  if oldRectW > 0 and oldRectH > 0 and oldZ > 0:
    centerX = (oldRectW / 2.0f - worldMapZoomInfo.pos.x) / oldZ
    centerY = (oldRectH / 2.0f - worldMapZoomInfo.pos.y) / oldZ
    hasCenter = true

  if hasCenter:
    pendingCenter = vec2(centerX, centerY)
    hasPendingCenter = true

  gameMode = newMode

  # Updates viewport properties based on mode.
  if gameMode == Game:
    worldMapZoomInfo.rect = irect(
      0,
      0,
      window.size.x.int32,
      window.size.y.int32
    )
    worldMapZoomInfo.scrollArea = rect(irect(
      0,
      0,
      window.size.x.int32,
      window.size.y.int32
    ))
    worldMapZoomInfo.hasMouse = true
    applyModeSwitchCenter(worldMapZoomInfo)
  else: # Editor mode
    # Panel drawing will update rect/scrollArea, but resets hasMouse.
    worldMapZoomInfo.hasMouse = false
  saveUIState()

proc computeScore(): float =
  ## Computes the average score for the active collective.
  if replay.isNil:
    return 0.0
  let cid = activeCollective
  var
    totalScore = 0.0
    agentCount = 0
  for obj in replay.objects:
    if obj.isAgent and obj.collectiveId.at(step) == cid:
      totalScore += obj.totalReward.at
      agentCount += 1
  if agentCount > 0:
    return totalScore / agentCount.float
  return 0.0

proc computeJunctionCount(): int =
  ## Computes the number of junctions for the active collective.
  if replay.isNil:
    return 0
  let cid = activeCollective
  var junctionCount = 0
  for obj in replay.objects:
    if normalizeTypeName(obj.typeName) == "junction" and
        obj.collectiveId.at(step) == cid:
      junctionCount += 1
  return junctionCount

proc drawIconScaled(
  name: string,
  pos: Vec2,
  size: float32,
  color = rgbx(255, 255, 255, 255)
) =
  ## Draw an atlas image scaled to size x size at pos.
  if name notin sk.atlas.entries:
    return
  let uv = sk.atlas.entries[name]
  sk.drawQuad(
    pos, vec2(size, size),
    vec2(uv.x.float32, uv.y.float32),
    vec2(uv.width.float32, uv.height.float32),
    color
  )

const
  ResourceCellWidth = 88.0f
  ResourceCellHeight = 48.0f

proc resourceCell(pos: Vec2, icon: string, amount: int) =
  ## Draw one fixed-size resource cell (icon + 3-digit amount).
  const
    IconSize = 48.0f
    IconTextGap = 8.0f
  drawIconScaled(icon, pos, IconSize)
  discard sk.drawText(
    "pixelated",
    &"{amount:03d}",
    pos + vec2(IconSize + IconTextGap, 0),
    Yellow,
    clip = false
  )

proc drawVibeButton(
  pos: Vec2,
  vibeName: string,
  vibeIndex: int,
  iconSize: float32
) =
  ## Draw a vibe icon button at an absolute position with click handling.
  ## Show ui/button_main.down background when this vibe is active
  ## on the selected agent.
  let
    icon = "vibe/" & vibeName
    btnSize = vec2(iconSize, iconSize)
    btnRect = rect(pos, btnSize)
    mousePos = window.mousePos.vec2

  # Check if this vibe is currently active on the selected agent.
  let isActive = selection != nil and selection.isAgent and
    selection.vibeId.at == vibeIndex

  if isActive:
    sk.drawImage("ui/button_main.down", pos - vec2(16, 16))

  # Hit test and click handling.
  if mousePos.overlaps(btnRect):
    if not isActive:
      sk.drawImage("ui/button_main.hover", pos - vec2(16, 16))
    sk.hover = true
    if window.buttonReleased[MouseLeft]:
      worldMapZoomInfo.hasMouse = false
      if selection != nil and selection.isAgent:
        let vibeActionId = replay.actionNames.find("change_vibe_" & vibeName)
        if vibeActionId >= 0:
          let shiftDown = window.buttonDown[KeyLeftShift] or
            window.buttonDown[KeyRightShift]
          if shiftDown:
            let objective = Objective(
              kind: Vibe,
              vibeActionId: vibeActionId,
              repeat: false
            )
            if not agentObjectives.hasKey(selection.agentId) or
                agentObjectives[selection.agentId].len == 0:
              agentObjectives[selection.agentId] = @[objective]
              agentPaths[selection.agentId] = @[
                PathAction(kind: Vibe, vibeActionId: vibeActionId)
              ]
            else:
              agentObjectives[selection.agentId].add(objective)
              if agentPaths.hasKey(selection.agentId):
                agentPaths[selection.agentId].add(
                  PathAction(kind: Vibe, vibeActionId: vibeActionId)
                )
              else:
                agentPaths[selection.agentId] = @[
                  PathAction(kind: Vibe, vibeActionId: vibeActionId)
                ]
          else:
            sendAction(selection.agentId, replay.actionNames[vibeActionId])

  drawIconScaled(icon, pos, iconSize)

proc drawToggleIconButton(pos: Vec2, icon: string, isActive: bool): bool =
  ## Draw an icon-only toggle button and return true on click.
  let
    iconSize = 48.0f
    btnSize = vec2(iconSize, iconSize)
    btnRect = rect(pos, btnSize)
    hover = window.mousePos.vec2.overlaps(btnRect)
    pressed = hover and window.buttonReleased[MouseLeft]

  if isActive:
    sk.drawImage("ui/button_main.down", pos - vec2(16, 16))
  elif hover:
    sk.drawImage("ui/button_main.hover", pos - vec2(16, 16))

  if hover:
    sk.hover = true

  if pressed:
    worldMapZoomInfo.hasMouse = false

  drawIconScaled(icon, pos, iconSize)
  return pressed

proc drawTransportButton(startPos: Vec2, idx: int, icon: string, isDown: bool): bool =
  ## Draw one transport-style button and return true if clicked.
  const BtnStride = 48.0f
  let
    btnPos = startPos + vec2(idx.float32 * BtnStride, 0)
    bgSize = sk.getImageSize("ui/transportButton.up")
    btnRect = rect(btnPos, bgSize)
    hover = window.mousePos.vec2.overlaps(btnRect)
    pressed = hover and window.buttonReleased[MouseLeft]
    bg =
      if isDown or pressed:
        "ui/transportButton.down"
      elif hover:
        "ui/transportButton.hover"
      else:
        "ui/transportButton.up"
    alpha =
      if isDown or pressed:
        0.5f
      else:
        1f
  sk.drawImage(bg, btnPos)
  let iconSize = sk.getImageSize(icon)
  sk.drawImage(
    icon,
    btnPos + vec2((bgSize.x - iconSize.x) / 2, (bgSize.y - iconSize.y) / 2),
    color = color(1, 1, 1, alpha).rgbx
  )
  if pressed:
    worldMapZoomInfo.hasMouse = false
  return pressed

proc topLeftPanel() =
  ## Draw top-left panel with score and junction count.
  sk.drawImage("ui/panel_topleft", vec2(0, 0))

  let
    avgScore = computeScore()
    junctionCount = computeJunctionCount()
    scoreLabel = &"Score {avgScore:.2f}\nJunctions {junctionCount}"
  discard sk.drawText(
    "pixelated",
    scoreLabel,
    vec2(44, 32),
    Yellow,
    clip = false
  )

proc topRightPanel(winW: float32) =
  ## Draw top-right panel with resource counts.
  let
    trSize = sk.getImageSize("ui/panel_topright")
    trPos = vec2(winW - trSize.x, 0)
  sk.drawImage("ui/panel_topright", trPos)

  if not replay.isNil:
    const
      CellSpacing = 32.0f
      YPad = 42.0f
      XPad = 52.0f
    let globalResources = [
      ("resources/carbon", "carbon"),
      ("resources/oxygen", "oxygen"),
      ("resources/germanium", "germanium"),
      ("resources/silicon", "silicon"),
    ]
    var x = trPos.x + XPad
    let y = trPos.y + YPad
    for i, (icon, name) in globalResources:
      resourceCell(vec2(x, y), icon, getCollectiveResourceCount(activeCollective, name))
      x += ResourceCellWidth + CellSpacing

proc bottomBarStretch(winW: float32, winH: float32) =
  ## Draw the stretch bar between the two bottom panels.
  let
    blSize = sk.getImageSize("ui/panel_bottomleft")
    brSize = sk.getImageSize("ui/panel_bottomright")
    barSize = sk.getImageSize("ui/barstretch")
    barX = blSize.x - 1
    barW = (winW - brSize.x) - blSize.x + 2
    uv = sk.atlas.entries["ui/barstretch"]
  sk.drawQuad(
    vec2(barX, winH - barSize.y),
    vec2(barW, barSize.y),
    vec2(uv.x.float32, uv.y.float32),
    vec2(uv.width.float32, uv.height.float32),
    rgbx(255, 255, 255, 255)
  )

proc bottomLeftPanel(winH: float32) =
  ## Draw bottom-left panel and transport controls.
  let
    blSize = sk.getImageSize("ui/panel_bottomleft")
    bottomLeftPanelPos = vec2(0, winH - blSize.y)
  sk.drawImage("ui/panel_bottomleft", bottomLeftPanelPos)

  block:
    let startPos = vec2(59, winH - 60)

    if drawTransportButton(startPos, 0, "ui/rewindToStart", false):
      echo "rewind to start"
      step = 0
      stepFloat = step.float32
      saveUIState()

    if drawTransportButton(startPos, 1, "ui/stepBack", false):
      echo "step back"
      step -= 1
      step = clamp(step, 0, replay.maxSteps - 1)
      stepFloat = step.float32
      saveUIState()

    let playIcon =
      if play:
        "ui/pause"
      else:
        "ui/play"
    if drawTransportButton(startPos, 2, playIcon, play):
      echo "play/pause"
      play = not play
      saveUIState()

    if drawTransportButton(startPos, 3, "ui/stepForward", false):
      echo "step forward"
      step += 1
      if step > replay.maxSteps - 1:
        requestPython = true
      step = clamp(step, 0, replay.maxSteps - 1)
      stepFloat = step.float32
      saveUIState()

    if drawTransportButton(startPos, 4, "ui/rewindToEnd", false):
      echo "rewind to end"
      step = replay.maxSteps - 1
      stepFloat = step.float32
      saveUIState()

  # Minimap panel visibility toggles.
  block:
    const
      ToggleStart = vec2(392, 94)
      ToggleSpacing = 40.0f
      ToggleIconSize = 48.0f
      ToggleStride = ToggleIconSize + ToggleSpacing

    let toggleBasePos = bottomLeftPanelPos + ToggleStart

    if drawToggleIconButton(toggleBasePos + vec2(0, ToggleStride * 0), "ui/grid", settings.showGrid):
      settings.showGrid = not settings.showGrid
      saveUIState()
    if drawToggleIconButton(toggleBasePos + vec2(0, ToggleStride * 1), "ui/eye", settings.showVisualRange):
      settings.showVisualRange = not settings.showVisualRange
      saveUIState()
    if drawToggleIconButton(toggleBasePos + vec2(0, ToggleStride * 2), "ui/cloud", settings.showFogOfWar):
      settings.showFogOfWar = not settings.showFogOfWar
      saveUIState()

proc bottomRightPanel(winW: float32, winH: float32) =
  ## Draw bottom-right panel and vibe controls.
  let
    brSize = sk.getImageSize("ui/panel_bottomright")
    brPos = vec2(winW - brSize.x, winH - brSize.y)
  sk.drawImage("ui/panel_bottomright", brPos)

  # Speed controls rendered in transport-button style.
  block:
    const Speeds = [1.0, 5.0, 10.0, 50.0, 100.0, 1000.0]
    let speedStartPos = brPos + vec2(230, 316)
    for i, speed in Speeds:
      let icon =
        if i == 0:
          "ui/turtle"
        elif i == len(Speeds) - 1:
          "ui/rabbit"
        else:
          "ui/speed"
      if drawTransportButton(speedStartPos, i, icon, playSpeed < speed):
        playSpeed = speed
        saveUIState()

  # Action mode toggles.
  block:
    const
      ToggleStart = vec2(174, 44)
      ToggleSpacing = 40.0f
      ToggleIconSize = 48.0f
      ToggleStride = ToggleIconSize + ToggleSpacing
    let toggleBasePos = brPos + ToggleStart

    if drawToggleIconButton(toggleBasePos + vec2(0, ToggleStride * 0), "ui/move", moveToggleActive):
      moveToggleActive = not moveToggleActive
      echo "move toggle: ", moveToggleActive
    if drawToggleIconButton(toggleBasePos + vec2(0, ToggleStride * 1), "ui/queue", queueToggleActive):
      queueToggleActive = not queueToggleActive
      echo "queue toggle: ", queueToggleActive
    if drawToggleIconButton(toggleBasePos + vec2(0, ToggleStride * 2), "ui/repeat", repeatToggleActive):
      repeatToggleActive = not repeatToggleActive
      echo "repeat toggle: ", repeatToggleActive

  if not replay.isNil:
    const
      GridCols = 3
      GridRows = 3
      VibeIconSize = 48.0f
      XStride = 48.0f + 34.0f  # cell width + horizontal spacing
      YStride = 48.0f + 39.0f  # cell height + vertical spacing
      GridXOff = 50.0f   # offset from right edge of window
      GridYOff = 106.0f  # offset from bottom edge of window
    let
      vibes = replay.config.game.vibeNames
      gridW = GridCols.float32 * XStride - 34.0f  # no trailing spacing
      gridH = GridRows.float32 * YStride - 39.0f
      gridOrigin = vec2(
        winW - GridXOff - gridW,
        winH - GridYOff - gridH
      )
    var idx = 0
    for row in 0 ..< GridRows:
      for col in 0 ..< GridCols:
        if idx >= vibes.len:
          break
        let cellPos = gridOrigin + vec2(
          col.float32 * XStride,
          row.float32 * YStride
        )
        drawVibeButton(cellPos, vibes[idx], idx, VibeIconSize)
        idx += 1
      if idx >= vibes.len:
        break

proc drawStatBar(panelPos: Vec2, label: string, value: int, maxValue: int, divisions: int, delta: int) =
  ## Draw a labeled stat bar in the center panel.
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
    totalFilled = clamp(value.float32 / safeMax.float32 * safeDivisions.float32, 0.0f, safeDivisions.float32)
    previousValue = value - delta
    previousFilled = clamp(previousValue.float32 / safeMax.float32 * safeDivisions.float32, 0.0f, safeDivisions.float32)
    deltaStart = min(totalFilled, previousFilled)
    deltaEnd = max(totalFilled, previousFilled)

  let
    outerX = outerPos.x.int
    outerY = outerPos.y.int
    outerW = OuterSize.x.int
    outerH = OuterSize.y.int
    innerX = outerX + BorderPx + InnerGapPx
    innerY = outerY + BorderPx + InnerGapPx
    innerW = max(0, outerW - 2 * (BorderPx + InnerGapPx))
    innerH = max(0, outerH - 2 * (BorderPx + InnerGapPx))

  discard sk.drawText("pixelated", label, panelPos + LabelOffset, Yellow, clip = false)

  # Stroke-only rectangle made from 4 filled rects.
  sk.drawRect(vec2(outerX.float32, outerY.float32), vec2(outerW.float32, BorderPx.float32), Yellow)  # top
  sk.drawRect(vec2(outerX.float32, (outerY + outerH - BorderPx).float32), vec2(outerW.float32, BorderPx.float32), Yellow)  # bottom
  sk.drawRect(vec2(outerX.float32, outerY.float32), vec2(BorderPx.float32, outerH.float32), Yellow)  # left
  sk.drawRect(vec2((outerX + outerW - BorderPx).float32, outerY.float32), vec2(BorderPx.float32, outerH.float32), Yellow)  # right

  # Draw segmented fill with 1px gaps and integer pixel widths.
  let
    totalGap = SegmentGapPx * (safeDivisions - 1)
    usableW = max(0, innerW - totalGap)
    baseSegW = if safeDivisions > 0: usableW div safeDivisions else: 0
    remainder = if safeDivisions > 0: usableW mod safeDivisions else: 0

  var segmentX = innerX
  for i in 0 ..< safeDivisions:
    let segmentW = baseSegW + (if i < remainder: 1 else: 0)
    if segmentW > 0:
      let segmentFillRatio = clamp(totalFilled - i.float32, 0.0f, 1.0f)
      let segmentFillW = clamp((segmentW.float32 * segmentFillRatio + 0.5f).int, 0, segmentW)
      if segmentFillW > 0:
        sk.drawRect(
          vec2(segmentX.float32, innerY.float32),
          vec2(segmentFillW.float32, innerH.float32),
          Yellow
        )

      # Draw white delta segment at the changing edge (gain or loss).
      let
        segmentDeltaStart = clamp(deltaStart - i.float32, 0.0f, 1.0f)
        segmentDeltaEnd = clamp(deltaEnd - i.float32, 0.0f, 1.0f)
        segmentDeltaW = clamp((segmentW.float32 * (segmentDeltaEnd - segmentDeltaStart) + 0.5f).int, 0, segmentW)
      if segmentDeltaW > 0:
        let segmentDeltaX = segmentX + clamp((segmentW.float32 * segmentDeltaStart + 0.5f).int, 0, segmentW)
        sk.drawRect(
          vec2(segmentDeltaX.float32, innerY.float32),
          vec2(segmentDeltaW.float32, innerH.float32),
          rgbx(255, 255, 255, 255)
        )
    segmentX += segmentW + SegmentGapPx

proc centerPanel(winW: float32, winH: float32) =
  ## Draw bottom-center selected agent info panel.
  if selection.isNil:
    return

  let bcSize = sk.getImageSize("ui/panel_center")
  let bcPos = vec2((winW - bcSize.x) / 2.0, winH - bcSize.y - 20)
  sk.drawImage("ui/panel_center", bcPos)

  if selection.isAgent:
    let profilePos = bcPos + vec2(424, 32)
    let rig = getAgentRigName(selection)
    let profileName =
      if rig == "agent":
        "profiles/cog"
      else:
        "profiles/" & rig
    sk.drawImage(profileName, profilePos)

    let
      textPos = bcPos + vec2(69, 32)
      collectiveName = getCollectiveName(selection.collectiveId.at(step))
      cogName = getCogName(selection.agentId)
      displayName =
        if collectiveName.len > 0 and cogName.len > 0:
          collectiveName & " " & cogName
        elif collectiveName.len > 0:
          collectiveName
        elif cogName.len > 0:
          cogName
        else:
          rig

    var
      health = 0
      energy = 0
    let prevStep = max(0, step - 1)
    let inv = selection.inventory.at
    for item in inv:
      if item.itemId >= 0 and item.itemId < replay.itemNames.len:
        if replay.itemNames[item.itemId] == "hp":
          health = item.count
        elif replay.itemNames[item.itemId] == "energy":
          energy = item.count
    let
      prevHealth = getInventoryItem(selection, "hp", prevStep)
      prevEnergy = getInventoryItem(selection, "energy", prevStep)
      deltaHealth = health - prevHealth
      deltaEnergy = energy - prevEnergy

    discard sk.drawText("pixelated", displayName, textPos, Yellow, clip = false)
    drawStatBar(bcPos + vec2(69, 84), "HP", health, 100, 10, deltaHealth)
    drawStatBar(bcPos + vec2(69, 118), "E", energy, 20, 20, deltaEnergy)

    let agentResources = [
      ("resources/heart", "heart"),
      ("resources/carbon", "carbon"),
      ("resources/oxygen", "oxygen"),
      ("resources/germanium", "germanium"),
      ("resources/silicon", "silicon"),
    ]
    const
      ResourceGridOrigin = vec2(59, 156)
      ResourceColSpacing = 20.0f
      ResourceRowSpacing = 12.0f
      ResourceCols = 3
    var visibleResourceCells = 0
    for (icon, name) in agentResources:
      let amount = getInventoryItem(selection, name)
      if amount <= 0:
        continue
      let
        row = visibleResourceCells div ResourceCols
        col = visibleResourceCells mod ResourceCols
        rowXOffset = if row == 0: 0.0f else: (ResourceCellWidth + ResourceColSpacing) / 2.0f
        cellPos = bcPos + ResourceGridOrigin + vec2(
          rowXOffset + col.float32 * (ResourceCellWidth + ResourceColSpacing),
          row.float32 * (ResourceCellHeight + ResourceRowSpacing)
        )
      resourceCell(cellPos, icon, amount)
      inc visibleResourceCells

  else:
    # Building info panel.
    let
      normalized = normalizeTypeName(selection.typeName)
      iconName = "icons/objects/" & normalized
      profilePos = bcPos + vec2(424, 32)
      profileSize = sk.getImageSize("profiles/cog")
    if iconName in sk.atlas.entries:
      let
        iconW = profileSize.x
        offsetY = (profileSize.y - iconW) / 2.0
      drawIconScaled(iconName, profilePos + vec2(0, offsetY), iconW)

    let
      textPos = bcPos + vec2(69, 32)
      collectiveName = getCollectiveName(selection.collectiveId.at(step))
      displayName =
        if collectiveName.len > 0:
          collectiveName & " " & normalized
        else:
          normalized

    discard sk.drawText("pixelated", displayName, textPos, Yellow, clip = false)

    # Building inventory.
    let inv = selection.inventory.at
    const
      ResourceGridOrigin = vec2(59, 156)
      ResourceColSpacing = 20.0f
      ResourceRowSpacing = 12.0f
      ResourceCols = 3
    var visibleResourceCells = 0
    for item in inv:
      if item.count <= 0 or item.itemId < 0 or item.itemId >= replay.itemNames.len:
        continue
      let
        itemName = replay.itemNames[item.itemId]
        itemIcon =
          if "resources/" & itemName in sk.atlas.entries:
            "resources/" & itemName
          else:
            "resources/heart"  # fallback icon
        row = visibleResourceCells div ResourceCols
        col = visibleResourceCells mod ResourceCols
        rowXOffset = if row == 0: 0.0f else: (ResourceCellWidth + ResourceColSpacing) / 2.0f
        cellPos = bcPos + ResourceGridOrigin + vec2(
          rowXOffset + col.float32 * (ResourceCellWidth + ResourceColSpacing),
          row.float32 * (ResourceCellHeight + ResourceRowSpacing)
        )
      resourceCell(cellPos, itemIcon, item.count)
      inc visibleResourceCells

proc bottomLeftMinimap(winH: float32) =
  ## Draw minimap inside the bottom-left panel.
  const
    MinimapSize = 300.0f
    MinimapXOff = 30.0f
    MinimapYOff = 90.0f  # offset from the bottom of the window
  let minimapPos = vec2(MinimapXOff, winH - MinimapYOff - MinimapSize)

  # TODO: Profile this?
  glEnable(GL_SCISSOR_TEST)
  glScissor(
    minimapPos.x.GLint,
    MinimapYOff.GLint,
    MinimapSize.GLsizei,
    MinimapSize.GLsizei
  )
  glClearColor(0.0f, 0.0f, 0.0f, 1.0f)
  glClear(GL_COLOR_BUFFER_BIT)
  glDisable(GL_SCISSOR_TEST)

  let mmZoom = ZoomInfo()
  mmZoom.rect = irect(minimapPos.x, minimapPos.y, MinimapSize, MinimapSize)
  mmZoom.hasMouse = false

  saveTransform()
  translateTransform(minimapPos)
  drawMinimap(mmZoom)
  restoreTransform()


proc drawTimelineSlider*(value: var float32, minVal: float32, maxVal: float32, label: string = "") =
  ## Draw a mettascope timeline slider.
  ## Similar to the slider in silky but customized for mettascope.
  let
    minF = minVal
    maxF = maxVal
    range = maxF - minF

  let
    clampedValue = clamp(value, minF, maxF)

  let
    baseHandleSize = sk.getImageSize("scrubber.handle")
    buttonHandleSize = sk.getImageSize("button.9patch")
    labelSize = if label.len > 0: sk.getTextSize(sk.textStyle, label) else: vec2(0, 0)
    minLabelSize = if label.len > 0: sk.getTextSize(sk.textStyle, "0000") else: vec2(0, 0)
    knobTextPadding = sk.theme.padding.float32 * 2 + 8f
    handleWidth =
      if label.len > 0:
        max(buttonHandleSize.x, max(labelSize.x, minLabelSize.x) + knobTextPadding)
      else:
        baseHandleSize.x
    handleHeight = if label.len > 0: max(buttonHandleSize.y, baseHandleSize.y) else: baseHandleSize.y
    handleSize = vec2(handleWidth, handleHeight)
    height = handleSize.y
    width = sk.size.x
    controlRect = bumpy.rect(sk.at, vec2(width, height))
    trackStart = controlRect.x + handleSize.x / 2
    trackEnd = controlRect.x + width - handleSize.x / 2
    travel = max(0f, trackEnd - trackStart)
    travelSafe = if travel <= 0: 1f else: travel

  let norm = if range == 0: 0f else: clamp((clampedValue - minF) / range, 0f, 1f)
  let
    handlePos = vec2(trackStart + norm * travel - handleSize.x * 0.5, controlRect.y + (height - handleSize.y) * 0.5)
    handleRect = bumpy.rect(handlePos, handleSize)

  if timeLineDragging and (window.buttonReleased[MouseLeft] or not window.buttonDown[MouseLeft]):
    timeLineDragging = false

  if timeLineDragging:
    let t = clamp((window.mousePos.vec2.x - trackStart) / travelSafe, 0f, 1f)
    value = minF + t * range
  elif sk.mouseInsideClip(window, handleRect) or sk.mouseInsideClip(window, controlRect):
    if window.buttonPressed[MouseLeft]:
      worldMapZoomInfo.hasMouse = false
      timeLineDragging = true
      let t = clamp((window.mousePos.vec2.x - trackStart) / travelSafe, 0f, 1f)
      value = minF + t * range

  let displayValue = clamp(value, minF, maxF)
  let norm2 = if range == 0: 0f else: clamp((displayValue - minF) / range, 0f, 1f)
  let handlePos2 = vec2(trackStart + norm2 * travel - handleSize.x * 0.5, controlRect.y + (height - handleSize.y) * 0.5)

  sk.drawImage("ui/timeslider", handlePos2 - vec2(32, 24))
  discard sk.drawText("pixelated", label, handlePos2 + vec2(12, -8), Yellow)

proc bottomTimelineSlider(winW: float32, winH: float32) =
  ## Draw a bottom timeline slider inset from both edges.
  if replay.isNil:
    return

  const
    LeftInset = 350.0f
    RightInset = 380.0f
    BottomInset = 6.0f

  let sliderW = winW - LeftInset - RightInset
  if sliderW <= 0:
    return

  let
    prevStepFloat = stepFloat
    maxStepFloat =
      if playMode == Realtime and stepFloatSmoothing:
        stepFloat
      else:
        replay.maxSteps.float32 - 1
    displayStep = $int(stepFloat + 0.5f)
    sliderH = 40.0f

  ribbon(
    vec2(LeftInset, winH - BottomInset - sliderH),
    vec2(sliderW, sliderH),
    rgbx(0, 0, 0, 0)
  ):
    drawTimelineSlider(stepFloat, 0, maxStepFloat, displayStep)

  if prevStepFloat != stepFloat:
    step = clamp((stepFloat + 0.5f).int, 0, replay.maxSteps - 1)

proc drawGameWorld*() =
  ## Renders the game world to fill the entire window (no panels).
  let
    winW = window.size.x.float32
    winH = window.size.y.float32

  topLeftPanel()
  topRightPanel(winW)
  bottomBarStretch(winW, winH)
  bottomLeftPanel(winH)
  bottomRightPanel(winW, winH)
  centerPanel(winW, winH)

  bottomTimelineSlider(winW, winH)

  drawWorldMap(worldMapZoomInfo)
  bottomLeftMinimap(winH)
  worldMapZoomInfo.hasMouse = true
