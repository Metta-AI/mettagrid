import
  std/[strformat, tables],
  opengl,
  bumpy, vmath, windy, silky, silky/atlas, chroma, pixie,
  ../[common, configs, replays, colors, actions, cognames],
  team, sound, worldmap, minimap, custom_hud, camera, talk

var
  pendingCenter: Vec2
  hasPendingCenter = false
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
    previousPanelSize = vec2(
      window.size.x.float32,
      window.size.y.float32
    )
    worldMapZoomInfo.hasMouse = true
    applyModeSwitchCenter(worldMapZoomInfo)
  else: # Editor mode
    # Panel drawing will update rect/scrollArea, but resets hasMouse.
    worldMapZoomInfo.hasMouse = false
  saveUIState()
  playSound("UIswitch.wav")

proc computeScore(teamIdx: int = lastSelectedTeam): float =
  ## Computes the average score for a team's agents.
  if replay.isNil:
    return 0.0
  var
    totalScore = 0.0
    agentCount = 0
  for obj in replay.objects:
    if obj.isAgent and getEntityTeamIndex(obj) == teamIdx:
      totalScore += obj.totalReward.at
      agentCount += 1
  if agentCount > 0:
    return totalScore / agentCount.float
  return 0.0

proc computeJunctionCount(teamIdx: int = lastSelectedTeam): int =
  ## Computes the junction count for a team.
  if replay.isNil:
    return 0
  var junctionCount = 0
  for obj in replay.objects:
    if normalizeTypeName(obj.typeName) == "junction" and
        getEntityTeamIndex(obj) == teamIdx:
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
  ResourceCellWidth = 140.0f

proc resourceCell(
  pos: Vec2,
  icon: string,
  amount: SomeNumber,
  showIcon = true,
  bgWidth = 80.0f
) =
  ## Draw one fixed-size resource cell (icon + number).
  const
    IconSize = 48.0f
    IconTextGap = 8.0f
    NumberBgName = "ui/resource_bg"
    BgHeight = 40.0f
    NumberTextPaddingX = 8.0f
  if showIcon:
    drawIconScaled(icon, pos, IconSize)
  let
    bgSize = vec2(bgWidth, BgHeight)
    numberBgPos =
      if showIcon:
        pos + vec2(IconSize + IconTextGap, (IconSize - BgHeight) * 0.5f + 4)
      else:
        pos
  if NumberBgName in sk.atlas.entries:
    sk.draw9Patch(NumberBgName, 16, numberBgPos, bgSize)

  let amountLabel =
    when amount is SomeFloat:
      &"{amount:.2f}"
    else:
      $amount
  discard sk.drawText(
    "pixelated",
    amountLabel,
    numberBgPos + vec2(NumberTextPaddingX, -4),
    Yellow,
    maxWidth = max(0.0f, bgSize.x - NumberTextPaddingX * 2.0f),
    maxHeight = bgSize.y,
    clip = false,
    hAlign = RightAlign,
    vAlign = MiddleAlign
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
    mousePos = sk.mousePos

  # Check if this vibe is currently active on the selected agent.
  let isActive = selected != nil and selected.isAgent and
    selected.vibeId.at == vibeIndex

  if isActive:
    sk.drawImage("ui/button_main.down", pos - vec2(16, 16))

  # Hit test and click handling.
  let vibeHover = mousePos.overlaps(btnRect)
  if vibeHover:
    if not isActive:
      sk.drawImage("ui/button_main.hover", pos - vec2(16, 16))
    if window.buttonReleased[MouseLeft]:
      playSound("UIbutton.wav")

      worldMapZoomInfo.hasMouse = false
      if selected != nil and selected.isAgent:
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
            if not agentObjectives.hasKey(selected.agentId) or
                agentObjectives[selected.agentId].len == 0:
              agentObjectives[selected.agentId] = @[objective]
              agentPaths[selected.agentId] = @[
                PathAction(kind: Vibe, vibeActionId: vibeActionId)
              ]
            else:
              agentObjectives[selected.agentId].add(objective)
              if agentPaths.hasKey(selected.agentId):
                agentPaths[selected.agentId].add(
                  PathAction(kind: Vibe, vibeActionId: vibeActionId)
                )
              else:
                agentPaths[selected.agentId] = @[
                  PathAction(kind: Vibe, vibeActionId: vibeActionId)
                ]
          else:
            sendAction(selected.agentId, replay.actionNames[vibeActionId])

  if vibeHover:
    tooltip(vibeName)
  drawIconScaled(icon, pos, iconSize)

proc drawToggleIconButton(pos: Vec2, icon: string, isActive: bool): bool =
  ## Draw an icon-only toggle button and return true on click.
  let
    iconSize = 48.0f
    btnSize = vec2(iconSize, iconSize)
    btnRect = rect(pos, btnSize)
    hover = sk.mousePos.overlaps(btnRect)
    pressed = hover and window.buttonReleased[MouseLeft]

  if isActive:
    sk.drawImage("ui/button_main.down", pos - vec2(16, 16))
  elif hover:
    sk.drawImage("ui/button_main.hover", pos - vec2(16, 16))

  if hover:
    let tip = iconTooltip(icon)
    if tip != "":
      tooltip(tip)
  if pressed:
    worldMapZoomInfo.hasMouse = false
    playSound("UIswitch.wav")

  drawIconScaled(icon, pos, iconSize)
  return pressed

proc drawTransportButton(startPos: Vec2, idx: int, icon: string, isDown: bool): bool =
  ## Draw one transport-style button and return true if clicked.
  const BtnStride = 48.0f
  let
    btnPos = startPos + vec2(idx.float32 * BtnStride, 0)
    bgSize = sk.getImageSize("ui/transportButton.up")
    btnRect = rect(btnPos, bgSize)
    hover = sk.mousePos.overlaps(btnRect)
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
  if hover:
    let tip = iconTooltip(icon)
    if tip != "":
      tooltip(tip)
  if pressed:
    worldMapZoomInfo.hasMouse = false
    playSound("UIswitch.wav")
  return pressed

proc topLeftPanel() =
  ## Draw top-left panel with team colors, scores, and junctions.
  const
    ScoreBgWidth = 120.0f
    JunctionBgWidth = 80.0f
    ScoreColWidth = ScoreBgWidth + 8.0f
    JunctionColWidth = JunctionBgWidth + 8.0f
    SwatchSize = 16.0f
    HeaderRowHeight = 56.0f
    DataRowHeight = 44.0f
    SwatchColWidth = SwatchSize + 4.0f
    SwatchColSpacing = 16
    ContentWidth = SwatchColWidth + SwatchColSpacing + ScoreColWidth + JunctionColWidth
    BorderLeft = 30
    BorderRight = 50
    BorderTop = 55
    BorderBottom = 100
    PadLeft = 16.0f
    PadRight = 16.0f
    PadTop = -6.0f
    PadBottom = 8.0f

  let
    numTeams = max(getNumTeams(), 1)
    contentHeight =
      HeaderRowHeight + numTeams.float32 * DataRowHeight
    panelWidth =
      BorderLeft.float32 + PadLeft +
      ContentWidth + PadRight + BorderRight.float32
    panelHeight =
      BorderTop.float32 + PadTop +
      contentHeight + PadBottom + BorderBottom.float32

  sk.draw9Patch(
    "ui/panel_topleft",
    BorderTop, BorderRight, BorderBottom, BorderLeft,
    vec2(0, 0),
    vec2(panelWidth, panelHeight)
  )

  if replay.isNil:
    return

  let
    contentX = BorderLeft.float32 + PadLeft
    scoreColX = contentX + SwatchColWidth + SwatchColSpacing
    junctionColX = scoreColX + ScoreColWidth
    headerY = BorderTop.float32 + PadTop

  # Header row aligned to match data cell digits (right-aligned with 8px padding).
  const NumberTextPaddingX = 8.0f
  discard sk.drawText(
    "pixelated", "Score",
    vec2(scoreColX + NumberTextPaddingX, headerY),
    Yellow, clip = false,
    maxWidth = ScoreBgWidth - NumberTextPaddingX * 2.0f,
    hAlign = CenterAlign
  )
  const JunctionIconSize = 32.0f
  drawIconScaled(
    "icons/objects/junction",
    vec2(
      junctionColX + (JunctionColWidth - JunctionIconSize) * 0.5f,
      headerY + (HeaderRowHeight - JunctionIconSize) * 0.5f
    ),
    JunctionIconSize
  )

  # Data rows with bg centered within each column.
  const BgHeight = 40.0f
  for i in 0 ..< getNumTeams():
    let y = headerY + HeaderRowHeight + i.float32 * DataRowHeight
    sk.drawRect(
      vec2(contentX, y + (BgHeight - SwatchSize) * 0.5f),
      vec2(SwatchSize, SwatchSize),
      getTeamColor(i)
    )
    resourceCell(
      vec2(scoreColX, y),
      "", computeScore(i),
      showIcon = false, bgWidth = ScoreBgWidth
    )
    resourceCell(
      vec2(junctionColX + (JunctionColWidth - JunctionBgWidth) * 0.5f, y),
      "", computeJunctionCount(i),
      showIcon = false, bgWidth = JunctionBgWidth
    )

proc topRightPanel(winW: float32) =
  ## Draw top-right panel with resource counts for all teams.
  const
    ColSpacing = 98.0f
    IconSize = 48.0f
    NumberBgWidth = 80.0f
    IconRowHeight = 56.0f
    DataRowHeight = 44.0f
    NumResources = 4
    ContentWidth = NumResources.float32 * ColSpacing
    BorderLeft = 30
    BorderRight = 30
    BorderTop = 55
    BorderBottom = 100
    PadLeft = 20.0f
    PadRight = 16.0f
    PadTop = 0.0f
    PadBottom = 8.0f

  let
    numTeams = getNumTeams()
    contentHeight =
      IconRowHeight + max(numTeams, 1).float32 * DataRowHeight
    panelWidth =
      BorderLeft.float32 + PadLeft +
      ContentWidth + PadRight + BorderRight.float32
    panelHeight =
      BorderTop.float32 + PadTop +
      contentHeight + PadBottom + BorderBottom.float32
    trPos = vec2(winW - panelWidth, 0)
  sk.draw9Patch(
    "ui/panel_topright",
    BorderTop, BorderRight, BorderBottom, BorderLeft,
    trPos,
    vec2(panelWidth, panelHeight)
  )

  if not replay.isNil:
    let
      globalResources = [
        ("resources/carbon", "carbon"),
        ("resources/oxygen", "oxygen"),
        ("resources/germanium", "germanium"),
        ("resources/silicon", "silicon"),
      ]
      contentX = trPos.x + BorderLeft.float32 + PadLeft

    # Header row: icons centered over each column.
    let iconY = trPos.y + BorderTop.float32 + PadTop
    for i, (icon, name) in globalResources:
      let x = contentX + i.float32 * ColSpacing +
        (ColSpacing - IconSize) * 0.5f
      drawIconScaled(icon, vec2(x, iconY), IconSize)

    # Data rows: numbers only.
    for teamIdx in 0 ..< numTeams:
      for i, (icon, name) in globalResources:
        let
          x = contentX + i.float32 * ColSpacing +
            (ColSpacing - NumberBgWidth) * 0.5f
          y = iconY + IconRowHeight + teamIdx.float32 * DataRowHeight
        resourceCell(
          vec2(x, y), icon,
          getGlobalResourceCount(teamIdx, name),
          showIcon = false
        )

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
      step = 0
      stepFloat = step.float32
      saveUIState()

    if drawTransportButton(startPos, 1, "ui/stepBack", false):
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
      play = not play
      saveUIState()

    if drawTransportButton(startPos, 3, "ui/stepForward", false):
      step += 1
      if step > replay.maxSteps - 1:
        requestPython = true
      step = clamp(step, 0, replay.maxSteps - 1)
      stepFloat = step.float32
      saveUIState()

    if drawTransportButton(startPos, 4, "ui/rewindToEnd", false):
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
  const StopRightEdgeOffset =  8.0f  # The image does not align to the right edge by default.
  let
    brSize = sk.getImageSize("ui/panel_bottomright")
    brPos = vec2(winW - brSize.x, winH - brSize.y)
    srSize = sk.getImageSize("ui/bar_stopRight")
    srPos = vec2(winW - srSize.x + StopRightEdgeOffset, winH - srSize.y)
    spSize = sk.getImageSize("ui/bar_spacer")
    spOffset = 315.0f
    spPos = vec2(winW - spOffset - spSize.x, winH - spSize.y)
    slSize = sk.getImageSize("ui/bar_stopLeft")
    slOffset = spOffset + slSize.x - 25.0f
    slPos = vec2(winW - slOffset - slSize.x, winH - slSize.y)
  sk.drawImage("ui/panel_bottomright", brPos)
  sk.drawImage("ui/bar_stopRight", srPos)
  sk.drawImage("ui/bar_spacer", spPos)
  sk.drawImage("ui/bar_stopLeft", slPos)

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
    if drawToggleIconButton(toggleBasePos + vec2(0, ToggleStride * 1), "ui/queue", queueToggleActive):
      queueToggleActive = not queueToggleActive
      if queueToggleActive:
        moveToggleActive = true
    if drawToggleIconButton(toggleBasePos + vec2(0, ToggleStride * 2), "ui/repeat", repeatToggleActive):
      repeatToggleActive = not repeatToggleActive
      if repeatToggleActive:
        queueToggleActive = true
        moveToggleActive = true

  # Mute Button.
  block:
    const MuteButtonStride = 48.0f
    let
      isDown = soundMuted
      icon = "ui/soundMute"
      btnPos = brPos + vec2(200 - MuteButtonStride, 316)
      bgSize = sk.getImageSize("ui/transportButton.up")
      btnRect = rect(btnPos, bgSize)
      hover = sk.mousePos.overlaps(btnRect)
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
    if hover:
      tooltip("Mute/Unmute")
    if pressed:
      worldMapZoomInfo.hasMouse = false
      playSound("UIswitch.wav")
      soundMuted = not soundMuted
      saveUIState()

  if not replay.isNil:
    const
      GridCols = 3
      GridRows = 3
      VibeIconSize = 48.0f
      XStride = 48.0f + 34.0f  # cell width + horizontal spacing
      YStride = 48.0f + 39.0f  # cell height + vertical spacing
      GridXOff = 50.0f   # offset from right edge of window
      GridYOff = 106.0f  # offset from bottom edge of window
    var availableVibes: seq[tuple[name: string, vibeId: int]]
    for vibeId, vibeName in replay.config.game.vibeNames:
      if replay.actionNames.find("change_vibe_" & vibeName) != -1:
        availableVibes.add((vibeName, vibeId))

    let
      gridW = GridCols.float32 * XStride - 34.0f  # no trailing spacing
      gridH = GridRows.float32 * YStride - 39.0f
      gridOrigin = vec2(
        winW - GridXOff - gridW,
        winH - GridYOff - gridH
      )
    var idx = 0
    for row in 0 ..< GridRows:
      for col in 0 ..< GridCols:
        if idx >= availableVibes.len:
          break
        let cellPos = gridOrigin + vec2(
          col.float32 * XStride,
          row.float32 * YStride
        )
        let (vibeName, vibeId) = availableVibes[idx]
        drawVibeButton(
          cellPos,
          vibeName,
          vibeId,
          VibeIconSize
        )
        idx += 1
      if idx >= availableVibes.len:
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
        # Just first 2 letters of the label.
        label[0..1]
      else:
        label
  discard sk.drawText("pixelated", text, panelPos + LabelOffset, Yellow, clip = false)

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
  if selected.isNil:
    return

  let
    bcSize = sk.getImageSize("ui/panel_center")
    bcPos = vec2((winW - bcSize.x) / 2.0, winH - bcSize.y - 20)
  sk.drawImage("ui/panel_center", bcPos)
  var at = vec2(bcPos.x + 69, bcPos.y + 32)

  let
    isAgent = selected.isAgent
    profilePos = bcPos + vec2(424, 32)
    teamName = getTeamName(getEntityTeamIndex(selected))
    policyName = if isAgent: selected.policyName else: ""

  var
    displayName = ""
    profileName = ""
    resourcesToDraw: seq[tuple[icon: string, amount: int]] = @[]

  if isAgent:
    let rig = getAgentRigName(selected)
    let resolvedAsset = replay.resolveRenderAsset(selected, step)
    let cogName = getCogName(selected.agentId)
    displayName =
      if teamName.len > 0 and cogName.len > 0:
        teamName & " " & cogName
      elif teamName.len > 0:
        teamName
      elif cogName.len > 0:
        cogName
      else:
        rig
    profileName =
      if resolvedAsset.len > 0 and ("profiles/" & resolvedAsset) in sk.atlas.entries:
        "profiles/" & resolvedAsset
      else:
        "profiles/" & rig
  else:
    let resolvedAsset = replay.resolveRenderAsset(selected, step)
    let normalized =
      if resolvedAsset.len > 0:
        normalizeTypeName(resolvedAsset)
      else:
        normalizeTypeName(selected.renderName)
    displayName =
      if teamName.len > 0:
        teamName & " " & normalized
      else:
        normalized
    profileName =
      if resolvedAsset.len > 0 and ("profiles/" & resolvedAsset) in sk.atlas.entries:
        "profiles/" & resolvedAsset
      else:
        "profiles/" & normalized

  # Draw entity display name and policy label.
  discard sk.drawText("pixelated", displayName, at, Yellow, clip = false)
  if isAgent:
    let policyLabel =
      if policyName.len > 20:
        policyName[0 ..< 20]
      else:
        policyName
    discard sk.drawText(
      "pixelated",
      policyLabel,
      at + vec2(0, 32),
      rgbx(255, 255, 255, 255),
      clip = false,
    )

  # Draw agent stat bars or custom status display.
  let useCustomStatus = replay.hasCustomStatus(selected)
  if useCustomStatus:
    discard drawCustomStatusBars(selected, bcPos + vec2(0, 32.0f))
  elif isAgent:
    let
      prevStep = max(0, step - 1)
      hud1Cfg = replay.hudItem1
      hud2Cfg = replay.hudItem2
      hud1 = getInventoryItem(selected, hud1Cfg.resource)
      hud2 = getInventoryItem(selected, hud2Cfg.resource)
      prevHud1 = getInventoryItem(selected, hud1Cfg.resource, prevStep)
      prevHud2 = getInventoryItem(selected, hud2Cfg.resource, prevStep)
      deltaHud1 = hud1 - prevHud1
      deltaHud2 = hud2 - prevHud2
    drawStatBar(bcPos + vec2(69, 113), hud1Cfg.short_name, hud1, hud1Cfg.max, 10, deltaHud1)
    drawStatBar(bcPos + vec2(69, 145), hud2Cfg.short_name, hud2, hud2Cfg.max, 20, deltaHud2)

  # Draw inventory resources as inline wrapped icons for agents and buildings.
  if useCustomStatus:
    let cr = collectCustomResources(selected, bcPos + vec2(0, 32.0f))
    resourcesToDraw = cr.resources
    at = cr.anchor
  else:
    for item in selected.inventory.at:
      if item.count <= 0 or item.itemId < 0 or item.itemId >= replay.itemNames.len:
        continue
      let
        itemName = replay.itemNames[item.itemId]
        itemIcon = "resources/" & itemName
      if itemName in @["hp", "energy", "solar", "scrambler"]:
        continue
      if itemIcon notin sk.atlas.entries:
        continue
      resourcesToDraw.add((icon: itemIcon, amount: item.count))
    # Use `at` for resource anchor; buildings start higher since they have no bars.
    at = vec2(
      bcPos.x + 59,
      if isAgent:
        bcPos.y + 183
      else:
        bcPos.y + 112
    )
  const
    ResourceMaxWidth = 300.0f
    IconSize = 48.0f
    IconTextGap = 8.0f
    ItemGap = 16.0f
    RowGap = 12.0f
  var
    cursorX = 0.0f
    cursorY = 0.0f
  for resource in resourcesToDraw:
    let
      amountLabel = $resource.amount
      textSize = sk.getTextSize(sk.textStyle, amountLabel)
      itemWidth = IconSize + IconTextGap + textSize.x
    if cursorX > 0 and cursorX + itemWidth > ResourceMaxWidth:
      cursorX = 0.0f
      cursorY += IconSize + RowGap
    let iconPos = at + vec2(cursorX, cursorY)
    drawIconScaled(resource.icon, iconPos, IconSize)
    discard sk.drawText(
      "pixelated",
      amountLabel,
      iconPos + vec2(IconSize + IconTextGap, 0),
      Yellow,
      maxWidth = textSize.x,
      maxHeight = IconSize,
      clip = false,
      hAlign = LeftAlign,
      vAlign = MiddleAlign
    )
    cursorX += itemWidth + ItemGap

  # Draw profile portrait with optional team color mask.
  if profileName in sk.atlas.entries:
    let
      profileMask = profileName & ".mask"
      profileTeamIdx = getEntityTeamIndex(selected)
    if profileTeamIdx >= 0 and profileMask in sk.atlas.entries:
      sk.drawImage(profileName, profilePos, getTeamColor(profileTeamIdx), profileMask)
    else:
      sk.drawImage(profileName, profilePos)

proc bottomLeftMinimap(winH: float32) =
  ## Draw minimap inside the bottom-left panel.
  const
    MinimapSize = 300.0f
    MinimapXOff = 30.0f
    MinimapYOff = 90.0f  # offset from the bottom of the window
  let
    minimapPos = vec2(MinimapXOff, winH - MinimapYOff - MinimapSize)
    scissorPos = minimapPos * sk.uiScale
    scissorSize = vec2(MinimapSize, MinimapSize) * sk.uiScale

  # TODO: Profile this?
  glEnable(GL_SCISSOR_TEST)
  glScissor(
    scissorPos.x.GLint,
    (MinimapYOff * sk.uiScale).GLint,
    scissorSize.x.GLsizei,
    scissorSize.y.GLsizei
  )
  glClearColor(0.0f, 0.0f, 0.0f, 1.0f)
  glClear(GL_COLOR_BUFFER_BIT)
  glDisable(GL_SCISSOR_TEST)

  let mmZoom = ZoomInfo()
  mmZoom.rect = irect(minimapPos.x, minimapPos.y, MinimapSize, MinimapSize)
  mmZoom.hasMouse = window.mousePos.vec2.overlaps(rect(scissorPos, scissorSize))

  saveTransform()
  translateTransform(scissorPos)
  drawMinimap(mmZoom)
  restoreTransform()

proc drawTimelineSlider*(value: var float32, minVal: float32, maxVal: float32, label: string = "") =
  ## Draw a mettascope timeline slider.
  ## Similar to the slider in silky but customized for mettascope.
  let
    minF = minVal
    maxF = maxVal
    range = maxF - minF
    clampedValue = clamp(value, minF, maxF)
    baseHandleSize = sk.getImageSize("scrubber.handle")
    buttonHandleSize = sk.getImageSize("button.9patch")
    labelSize = if label.len > 0: sk.getTextSize(sk.textStyle, label) else: vec2(0, 0)
    maxLabel =
      if label.len > 0:
        $int(max(abs(minVal), abs(maxVal)) + 0.5f)
      else:
        ""
    minLabelSize = if maxLabel.len > 0: sk.getTextSize(sk.textStyle, maxLabel) else: vec2(0, 0)
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

  let
    norm = if range == 0: 0f else: clamp((clampedValue - minF) / range, 0f, 1f)
    handlePos = vec2(trackStart + norm * travel - handleSize.x * 0.5, controlRect.y + (height - handleSize.y) * 0.5)
    handleRect = bumpy.rect(handlePos, handleSize)

  if timeLineDragging and (window.buttonReleased[MouseLeft] or not window.buttonDown[MouseLeft]):
    timeLineDragging = false
    playSound("UIscrub2.wav")

  if timeLineDragging:
    let t = clamp((sk.mousePos.x - trackStart) / travelSafe, 0f, 1f)
    value = minF + t * range
    playScrubberStepSound(t)
  elif sk.mouseHover(window, handleRect) or sk.mouseHover(window, controlRect):
    if window.buttonPressed[MouseLeft]:
      worldMapZoomInfo.hasMouse = false
      timeLineDragging = true
      let t = clamp((sk.mousePos.x - trackStart) / travelSafe, 0f, 1f)
      value = minF + t * range
      playSound("UIscrub3.wav")

  let
    displayValue = clamp(value, minF, maxF)
    norm2 = if range == 0: 0f else: clamp((displayValue - minF) / range, 0f, 1f)
    handlePos2 = vec2(trackStart + norm2 * travel - handleSize.x * 0.5, controlRect.y + (height - handleSize.y) * 0.5)
    sliderPos = handlePos2 - vec2(32, 24)
    sliderSize = sk.getImageSize("ui/timeslider")
    labelPaddingX = 10.0f

  sk.drawImage("ui/timeslider", sliderPos)
  discard sk.drawText(
    "pixelated",
    label,
    sliderPos + vec2(labelPaddingX, 14),
    Yellow,
    maxWidth = sliderSize.x - labelPaddingX * 2,
    maxHeight = sliderSize.y,
    clip = false,
    hAlign = CenterAlign,
    vAlign = TopAlign
  )

proc bottomTimelineSlider(winW: float32, winH: float32) =
  ## Draw a bottom timeline slider inset from both edges.
  if replay.isNil:
    return

  const
    MuteButtonInset = 48.0f + 70.0f
    LeftInset = 355.0f
    RightInset = 380.0f + MuteButtonInset
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
    winW = sk.size.x
    winH = sk.size.y
    winWi = window.size.x.int32
    winHi = window.size.y.int32

  if worldMapZoomInfo.rect.x != 0 or
      worldMapZoomInfo.rect.y != 0 or
      worldMapZoomInfo.rect.w != winWi or
      worldMapZoomInfo.rect.h != winHi:
    worldMapZoomInfo.rect = irect(0, 0, winWi, winHi)
    worldMapZoomInfo.scrollArea = rect(irect(0, 0, winWi, winHi))
    updateMinZoom(worldMapZoomInfo)
    adjustPanelForResize(worldMapZoomInfo)

  topLeftPanel()
  topRightPanel(winW)
  bottomBarStretch(winW, winH)
  bottomLeftPanel(winH)
  bottomRightPanel(winW, winH)
  centerPanel(winW, winH)
  centeredTalkComposer(winW, winH)

  bottomTimelineSlider(winW, winH)

  drawWorldMap(worldMapZoomInfo)
  drawTalkBubbles(worldMapZoomInfo)
  bottomLeftMinimap(winH)
  worldMapZoomInfo.hasMouse = true
