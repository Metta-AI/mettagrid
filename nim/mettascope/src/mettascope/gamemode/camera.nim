import
  std/math,
  bumpy, windy,
  ../common

type
  ZoomInfo* = ref object
    ## Used to track the zoom state of a world map and others.
    rect*: IRect
    pos*: Vec2
    vel*: Vec2
    zoom*: float32 = 10
    zoomVel*: float32
    minZoom*: float32 = 0.5
    maxZoom*: float32 = 50
    scrollArea*: Rect
    hasMouse*: bool = false
    dragging*: bool = false

var
  worldMapZoomInfo*: ZoomInfo

proc clampMapPan*(zoomInfo: ZoomInfo) =
  ## Clamp pan so the world map remains at least partially visible.
  if replay.isNil:
    return

  let zoomScale = zoomInfo.zoom * zoomInfo.zoom
  if zoomScale <= 0:
    return

  let
    mapMinX = -0.5f
    mapMinY = -0.5f
    mapMaxX = replay.mapSize[0].float32 - 0.5f
    mapMaxY = replay.mapSize[1].float32 - 0.5f
    mapWidth = mapMaxX - mapMinX
    mapHeight = mapMaxY - mapMinY
    rectW = zoomInfo.rect.w.float32
    rectH = zoomInfo.rect.h.float32
    viewHalfW = rectW / (2.0f * zoomScale)
    viewHalfH = rectH / (2.0f * zoomScale)
  var
    cx = (rectW / 2.0f - zoomInfo.pos.x) / zoomScale
    cy = (rectH / 2.0f - zoomInfo.pos.y) / zoomScale

  let
    minVisiblePixels = min(500.0f, min(rectW, rectH) * 0.5f)
    minVisibleWorld = minVisiblePixels / zoomScale
    maxVisibleUnitsX = min(minVisibleWorld, mapWidth / 2.0f)
    maxVisibleUnitsY = min(minVisibleWorld, mapHeight / 2.0f)
    minCenterX = mapMinX + maxVisibleUnitsX - viewHalfW
    maxCenterX = mapMaxX - maxVisibleUnitsX + viewHalfW
    minCenterY = mapMinY + maxVisibleUnitsY - viewHalfH
    maxCenterY = mapMaxY - maxVisibleUnitsY + viewHalfH

  cx = cx.clamp(minCenterX, maxCenterX)
  cy = cy.clamp(minCenterY, maxCenterY)
  zoomInfo.pos.x = rectW / 2.0f - cx * zoomScale
  zoomInfo.pos.y = rectH / 2.0f - cy * zoomScale

proc beginPanAndZoom*(zoomInfo: ZoomInfo) =
  ## Pan and zoom the map.
  saveTransform()

  if zoomInfo.hasMouse:
    if window.buttonPressed[MouseLeft] or window.buttonPressed[MouseMiddle]:
      zoomInfo.dragging = true
    if not window.buttonDown[MouseLeft] and
        not window.buttonDown[MouseMiddle] and zoomInfo.dragging:
      zoomInfo.dragging = false

  if zoomInfo.dragging:
    if window.buttonDown[MouseLeft] or window.buttonDown[MouseMiddle]:
      zoomInfo.vel = window.mouseDelta.vec2
      settings.lockFocus = false
    else:
      zoomInfo.vel *= 0.9
    zoomInfo.pos += zoomInfo.vel

  if zoomInfo.hasMouse and window.scrollDelta.y != 0:
    let
      localMousePos = window.mousePos.vec2 - zoomInfo.rect.xy.vec2
      zoomSensitivity = 0.005
      oldMat = translate(vec2(zoomInfo.pos.x, zoomInfo.pos.y)) *
        scale(vec2(zoomInfo.zoom * zoomInfo.zoom, zoomInfo.zoom * zoomInfo.zoom))
      focalPoint = if settings.lockFocus and selected != nil:
        let agentWorldPos = vec2(
          selected.location.at(step).x.float32,
          selected.location.at(step).y.float32
        )
        oldMat * agentWorldPos
      else:
        localMousePos
      oldWorldPoint = oldMat.inverse() * focalPoint
      zoomFactor = pow(1.0 - zoomSensitivity, window.scrollDelta.y)

    zoomInfo.zoom *= zoomFactor
    zoomInfo.zoom = clamp(zoomInfo.zoom, zoomInfo.minZoom, zoomInfo.maxZoom)

    let
      newMat = translate(vec2(zoomInfo.pos.x, zoomInfo.pos.y)) *
        scale(vec2(zoomInfo.zoom * zoomInfo.zoom, zoomInfo.zoom * zoomInfo.zoom))
      newWorldPoint = newMat.inverse() * focalPoint
    zoomInfo.pos +=
      (newWorldPoint - oldWorldPoint) *
      (zoomInfo.zoom * zoomInfo.zoom)

  clampMapPan(zoomInfo)
  translateTransform(zoomInfo.pos)
  let zoomScale = zoomInfo.zoom * zoomInfo.zoom
  scaleTransform(vec2(zoomScale, zoomScale))

proc endPanAndZoom*(zoomInfo: ZoomInfo) =
  ## Restore the transform after map panning and zooming.
  restoreTransform()
