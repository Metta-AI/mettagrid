import
  chroma, vmath, windy, silky,
  common, worldmap, panels

proc drawCameraViewportOverlay(zoomInfo: ZoomInfo, zoomScale, posX, posY: float32) =
  ## Draw the current main world-map camera viewport as a white minimap outline.
  if worldMapZoomInfo.isNil:
    return

  let
    mainRectW = worldMapZoomInfo.rect.w.float32
    mainRectH = worldMapZoomInfo.rect.h.float32
    mainZoomScale = worldMapZoomInfo.zoom * worldMapZoomInfo.zoom
    mapMinX = -0.5f
    mapMinY = -0.5f
    mapMaxX = replay.mapSize[0].float32 - 0.5f
    mapMaxY = replay.mapSize[1].float32 - 0.5f

  if mainRectW <= 0 or mainRectH <= 0 or mainZoomScale <= 0:
    return

  let
    rawLeft = (0.0f - worldMapZoomInfo.pos.x) / mainZoomScale
    rawRight = (mainRectW - worldMapZoomInfo.pos.x) / mainZoomScale
    rawTop = (0.0f - worldMapZoomInfo.pos.y) / mainZoomScale
    rawBottom = (mainRectH - worldMapZoomInfo.pos.y) / mainZoomScale
    worldLeft = max(mapMinX, min(mapMaxX, min(rawLeft, rawRight)))
    worldRight = max(mapMinX, min(mapMaxX, max(rawLeft, rawRight)))
    worldTop = max(mapMinY, min(mapMaxY, min(rawTop, rawBottom)))
    worldBottom = max(mapMinY, min(mapMaxY, max(rawTop, rawBottom)))
    miniLeft = worldLeft * zoomScale + posX
    miniRight = worldRight * zoomScale + posX
    miniTop = worldTop * zoomScale + posY
    miniBottom = worldBottom * zoomScale + posY
    outlineX = zoomInfo.rect.x.float32 + miniLeft
    outlineY = zoomInfo.rect.y.float32 + miniTop
    outlineW = max(1.0f, miniRight - miniLeft)
    outlineH = max(1.0f, miniBottom - miniTop)
    outlineThickness = 1.0f
    outlineColor = rgbx(255, 255, 255, 255)

  sk.drawRect(vec2(outlineX, outlineY), vec2(outlineW, outlineThickness), outlineColor)
  sk.drawRect(
    vec2(outlineX, outlineY + max(0.0f, outlineH - outlineThickness)),
    vec2(outlineW, outlineThickness),
    outlineColor
  )
  sk.drawRect(vec2(outlineX, outlineY), vec2(outlineThickness, outlineH), outlineColor)
  sk.drawRect(
    vec2(outlineX + max(0.0f, outlineW - outlineThickness), outlineY),
    vec2(outlineThickness, outlineH),
    outlineColor
  )

proc drawMinimap*(zoomInfo: ZoomInfo) =
  ## Draw the minimap with automatic fitting to panel size.
  if replay.isNil or replay.mapSize == (0, 0):
    return

  saveTransform()

  # Calculate transform to fit entire world in minimap panel.
  let rectW = zoomInfo.rect.w.float32
  let rectH = zoomInfo.rect.h.float32
  if rectW <= 0 or rectH <= 0:
    restoreTransform()
    return

  let
    mapMinX = -0.5f
    mapMinY = -0.5f
    mapMaxX = replay.mapSize[0].float32 - 0.5f
    mapMaxY = replay.mapSize[1].float32 - 0.5f
    mapW = max(0.001f, mapMaxX - mapMinX)
    mapH = max(0.001f, mapMaxY - mapMinY)

  let zoomScale = min(rectW / mapW, rectH / mapH)
  let
    cx = (mapMinX + mapMaxX) / 2.0f
    cy = (mapMinY + mapMaxY) / 2.0f
    posX = rectW / 2.0f - cx * zoomScale
    posY = rectH / 2.0f - cy * zoomScale

  translateTransform(vec2(posX, posY))
  scaleTransform(vec2(zoomScale, zoomScale))

  drawWorldMini()

  restoreTransform()
  drawCameraViewportOverlay(zoomInfo, zoomScale, posX, posY)
