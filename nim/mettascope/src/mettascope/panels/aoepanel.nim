## AoE (Area of Effect) panel - allows toggling AoE visibility for collectives.

import
  std/sets,
  bumpy, silky, chroma, vmath, windy,
  ../common, ../collectives, ../configs

template coloredCheckBoxInverse*(label: string, hiddenSet: var HashSet[int], value: int, tint: ColorRGBX) =
  ## Checkbox with tint color that toggles visibility via a "hidden" set.
  ## Checked = visible (not in set), unchecked = hidden (in set).
  let
    iconSize = sk.getImageSize("check.on")
    textSize = sk.getTextSize(sk.textStyle, label)
    height = max(iconSize.y.float32, textSize.y)
    width = iconSize.x.float32 + sk.theme.spacing.float32 + textSize.x
    hitRect = rect(sk.at, vec2(width, height))
    isOn = value notin hiddenSet

  if sk.mouseInsideClip(window, hitRect) and window.buttonReleased[MouseLeft]:
    if value in hiddenSet:
      hiddenSet.excl(value)
    else:
      hiddenSet.incl(value)
    saveUIState()

  let
    iconPos = vec2(sk.at.x, sk.at.y + (height - iconSize.y.float32) * 0.5)
    textPos = vec2(
      iconPos.x + iconSize.x.float32 + sk.theme.spacing.float32,
      sk.at.y + (height - textSize.y) * 0.5
    )
  sk.drawImage(if isOn: "check.on" else: "check.off", iconPos, tint)
  discard sk.drawText(sk.textStyle, label, textPos, sk.theme.defaultTextColor)
  sk.advance(vec2(width, height))

proc drawAoePanel*(panel: Panel, frameId: string, contentPos: Vec2, contentSize: Vec2) =
  ## Draw the AoE panel with checkboxes for all collectives in the game config.
  frame(frameId, contentPos, contentSize):
    sk.at += vec2(8, 8)

    let numCollectives = getNumCollectives()
    for i in 0 ..< numCollectives:
      let name = getCollectiveName(i)
      if name.len > 0:
        coloredCheckBoxInverse(name, settings.hiddenCollectiveAoe, i, getCollectiveColor(i))
