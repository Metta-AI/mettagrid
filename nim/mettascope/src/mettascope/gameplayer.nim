import
  vmath, windy, silky, chroma,
  common, worldmap, panels, configs, actions

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
    worldMapZoomInfo.rect = irect(0, 0, window.size.x.int32, window.size.y.int32)
    worldMapZoomInfo.scrollArea = rect(irect(0, 0, window.size.x.int32, window.size.y.int32))
    worldMapZoomInfo.hasMouse = true
    applyModeSwitchCenter(worldMapZoomInfo)
  else: # Editor mode
    # Panel drawing will update rect/scrollArea, but resets hasMouse.
    worldMapZoomInfo.hasMouse = false
  saveUIState()

proc drawGameWorld*() =
  ## Renders the game world to fill the entire window (no panels).

  drawWorldMap(worldMapZoomInfo)
