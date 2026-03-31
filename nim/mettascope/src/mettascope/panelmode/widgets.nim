## Shared UI widgets for panels.

import
  vmath, silky, silky/atlas, chroma

const IconSize* = 32.0f

proc drawImageScaled*(sk: Silky, name: string, pos: Vec2, size: Vec2, color = rgbx(255, 255, 255, 255)) =
  ## Draw an image scaled to a specific size using silky.
  if name notin sk.atlas.entries:
    return
  let uv = sk.atlas.entries[name]
  sk.drawQuad(
    pos,
    size,
    vec2(uv.x.float32, uv.y.float32),
    vec2(uv.width.float32, uv.height.float32),
    color
  )

template smallIconLabel*(imageName: string, labelText: string) =
  ## Draw a small icon with a text label, properly aligned.
  ## Icon is drawn at IconSize x IconSize, text is vertically centered.
  ## Falls back to undefined icon if the requested icon isn't found.
  let startX = sk.at.x
  let startY = sk.at.y
  sk.at.x += 8  # Indent
  # Draw icon (use undefined if not found)
  let actualIcon =
    if imageName in sk.atlas.entries:
      imageName
    else:
      "icons/undefined"
  drawImageScaled(sk, actualIcon, sk.at, vec2(IconSize, IconSize))
  sk.at.x += IconSize + 6  # Advance past icon + gap
  sk.at.y += 6  # Center text vertically with icon
  text(labelText)
  sk.at.x = startX  # Reset x for next line
  sk.at.y = startY + IconSize + 2  # Move to next line based on icon height
