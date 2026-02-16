import
  std/[strformat, tables],
  opengl,
  bumpy, vmath, windy, silky, silky/atlas, chroma,
  common, worldmap, panels, configs,
  replays, collectives, colors, minimap, actions

var
  pendingCenter: Vec2
  hasPendingCenter = false

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
      echo "vibe button clicked: ", vibeName
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

proc drawGameWorld*() =
  ## Renders the game world to fill the entire window (no panels).

  # Draw UI panels on top of the world map.
  let
    winW = window.size.x.float32
    winH = window.size.y.float32

  # Top-left panel
  sk.drawImage("ui/panel_topleft", vec2(0, 0))

  # Draw score and junction count on the top-left panel in pixel font.
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

  # Top-right panel
  let
    trSize = sk.getImageSize("ui/panel_topright")
    trPos = vec2(winW - trSize.x, 0)
  sk.drawImage("ui/panel_topright", trPos)

  # Draw resource icons and counts on the top-right panel.
  if not replay.isNil:
    const
      IconSize = 48.0f
      IconSpacing = 8.0f
      TextSize = 32.0f
      Spacing = 32.0f
      YPad = 42.0f
      XPad = 52.0f
    let resources = [
      ("resources/carbon", "carbon"),
      ("resources/oxygen", "oxygen"),
      ("resources/germanium", "germanium"),
      ("resources/silicon", "silicon"),
    ]
    var x = trPos.x + XPad
    let y = trPos.y + YPad
    for i, (icon, name) in resources:
      drawIconScaled(icon, vec2(x, y), IconSize)
      x += IconSize + IconSpacing
      let
        count = getCollectiveResourceCount(activeCollective, name)
        countText = &"{count:03d}"
      discard sk.drawText(
        "pixelated",
        countText,
        vec2(x, y),
        Yellow,
        clip = false
      )
      x += TextSize + Spacing

  # Get bottom panel sizes for bar stretch and panel positioning.
  let
    blSize = sk.getImageSize("ui/panel_bottomleft")
    brSize = sk.getImageSize("ui/panel_bottomright")

  # Bar stretch fills the gap between bottom-left and bottom-right
  # panels along the bottom edge.
  # Draw before bottom panels with 1px overlap so panels cover fuzzy edges.
  let
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

  # Bottom-left panel (drawn on top of bar stretch)
  sk.drawImage("ui/panel_bottomleft", vec2(0, winH - blSize.y))

  # Transport buttons on the bottom bar.
  block:
    const BtnStride = 48.0f
    let
      btnH = sk.getImageSize("ui/transportButton.up").y
      startPos = vec2(59, winH - 60)

    proc transportButton(idx: int, icon: string, isDown: bool): bool =
      ## Draw a transport button, return true if clicked.
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
      sk.drawImage(bg, btnPos)
      let iconSize = sk.getImageSize(icon)
      sk.drawImage(
        icon,
        btnPos + vec2((bgSize.x - iconSize.x) / 2, (bgSize.y - iconSize.y) / 2)
      )
      return pressed

    if transportButton(0, "ui/rewindToStart", false):
      echo "rewind to start"
      step = 0
      stepFloat = step.float32
      saveUIState()

    if transportButton(1, "ui/stepBack", false):
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
    if transportButton(2, playIcon, play):
      echo "play/pause"
      play = not play
      saveUIState()

    if transportButton(3, "ui/stepForward", false):
      echo "step forward"
      step += 1
      if step > replay.maxSteps - 1:
        requestPython = true
      step = clamp(step, 0, replay.maxSteps - 1)
      stepFloat = step.float32
      saveUIState()

    if transportButton(4, "ui/rewindToEnd", false):
      echo "rewind to end"
      step = replay.maxSteps - 1
      stepFloat = step.float32
      saveUIState()

  # Bottom-right panel (drawn on top of bar stretch)
  let brPos = vec2(winW - brSize.x, winH - brSize.y)
  sk.drawImage("ui/panel_bottomright", brPos)

  # Vibe buttons in a 3x3 grid on the bottom-right panel.
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

  # Bottom-center panel (only shown when something is selected)
  if not selection.isNil:
    let bcSize = sk.getImageSize("ui/panel_center")
    let bcPos = vec2((winW - bcSize.x) / 2.0, winH - bcSize.y - 20)
    sk.drawImage("ui/panel_center", bcPos)

    # Draw agent info on the bottom-center panel.
    if selection.isAgent:
      # Profile image at 424,32 offset from bcPos.
      let profilePos = bcPos + vec2(424, 32)
      let rig = getAgentRigName(selection)
      let profileName =
        if rig == "agent":
          "profiles/cog"
        else:
          "profiles/" & rig
      sk.drawImage(profileName, profilePos)

      # Name, health, energy at 64,60 offset from bcPos.
      let
        textPos = bcPos + vec2(74, 60)
        collectiveName = getCollectiveName(selection.collectiveId.at(step))
        agentName =
          if collectiveName.len > 0:
            collectiveName & " " & rig
          else:
            rig

      var
        health = 0
        energy = 0
      let inv = selection.inventory.at
      for item in inv:
        if item.itemId >= 0 and item.itemId < replay.itemNames.len:
          if replay.itemNames[item.itemId] == "hp":
            health = item.count
          elif replay.itemNames[item.itemId] == "energy":
            energy = item.count

      let infoLabel =
        &"{agentName}\n" &
        &"Team: {collectiveName}\n" &
        &"Health: {health}\n" &
        &"Energy: {energy}"
      discard sk.drawText("pixelated", infoLabel, textPos, Yellow, clip = false)

  # Draw the world map.
  drawWorldMap(worldMapZoomInfo)

  # Minimap inside the bottom-left panel.
  block:
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
