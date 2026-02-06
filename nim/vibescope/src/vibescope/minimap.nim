import
  boxy, chroma, vmath, windy,
  common, worldmap, panels

proc drawMinimap*(zoomInfo: ZoomInfo) =
  ## Draw the minimap with automatic fitting to panel size.
  let box = irect(0, 0, zoomInfo.rect.w, zoomInfo.rect.h)

  bxy.drawRect(
    rect = box.rect,
    color = color(0, 0, 0, 1.0)
  )

  if replay.isNil or replay.mapSize == (0, 0):
    return

  bxy.saveTransform()

  # Calculate transform to fit entire world in minimap panel.
  let rectW = zoomInfo.rect.w.float32
  let rectH = zoomInfo.rect.h.float32
  if rectW <= 0 or rectH <= 0:
    bxy.restoreTransform()
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

  bxy.translate(vec2(posX, posY))
  bxy.scale(vec2(zoomScale, zoomScale))

  # Handle click-to-navigate before drawing
  if zoomInfo.hasMouse and window.buttonPressed[MouseLeft]:
    let mouseLocal = window.mousePos.vec2 - vec2(zoomInfo.rect.x.float32, zoomInfo.rect.y.float32)
    let worldX = (mouseLocal.x - posX) / zoomScale
    let worldY = (mouseLocal.y - posY) / zoomScale

    # Center main map on clicked world coordinates
    let z = worldMapZoomInfo.zoom * worldMapZoomInfo.zoom
    let rectW = worldMapZoomInfo.rect.w.float32
    let rectH = worldMapZoomInfo.rect.h.float32
    worldMapZoomInfo.pos.x = rectW / 2.0f - worldX * z
    worldMapZoomInfo.pos.y = rectH / 2.0f - worldY * z
    viewStateChanged = true

  drawWorldMini()

  # Draw viewport indicator
  # Calculate visible world rectangle from main map camera
  let z = worldMapZoomInfo.zoom * worldMapZoomInfo.zoom
  let viewCX = (worldMapZoomInfo.rect.w.float32 / 2.0f - worldMapZoomInfo.pos.x) / z
  let viewCY = (worldMapZoomInfo.rect.h.float32 / 2.0f - worldMapZoomInfo.pos.y) / z
  let viewHW = worldMapZoomInfo.rect.w.float32 / (2.0f * z)
  let viewHH = worldMapZoomInfo.rect.h.float32 / (2.0f * z)

  # Draw outline as 4 thin rectangles (border thickness ~2 pixels)
  let borderThickness = 2.0f / zoomScale
  let outlineColor = color(1.0, 1.0, 1.0, 0.6)

  # Top edge
  bxy.drawRect(
    rect = rect(viewCX - viewHW, viewCY - viewHH, viewHW * 2.0f, borderThickness),
    color = outlineColor
  )
  # Bottom edge
  bxy.drawRect(
    rect = rect(viewCX - viewHW, viewCY + viewHH - borderThickness, viewHW * 2.0f, borderThickness),
    color = outlineColor
  )
  # Left edge
  bxy.drawRect(
    rect = rect(viewCX - viewHW, viewCY - viewHH, borderThickness, viewHH * 2.0f),
    color = outlineColor
  )
  # Right edge
  bxy.drawRect(
    rect = rect(viewCX + viewHW - borderThickness, viewCY - viewHH, borderThickness, viewHH * 2.0f),
    color = outlineColor
  )

  bxy.restoreTransform()
