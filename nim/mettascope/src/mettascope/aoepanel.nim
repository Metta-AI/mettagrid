import
  std/[sets],
  bumpy, silky, chroma, vmath, windy,
  common, panels

const NumCollectives* = 2

proc getAoeColor*(collectiveId: int): ColorRGBX =
  case collectiveId
  of 0: rgbx(230, 51, 51, 255)              # Clips = red
  of 1: rgbx(51, 204, 51, 255)              # Cogs = green
  else: rgbx(128, 128, 128, 255)            # Others = grey

template coloredCheckBox*(label: string, theSet: var HashSet[int], value: int, tint: ColorRGBX) =
  ## Checkbox with tint color that operates directly on a HashSet.
  ## Toggles the value in/out of the set when clicked.
  let
    iconSize = sk.getImageSize("check.on")
    textSize = sk.getTextSize(sk.textStyle, label)
    height = max(iconSize.y.float32, textSize.y)
    width = iconSize.x.float32 + sk.theme.spacing.float32 + textSize.x
    hitRect = rect(sk.at, vec2(width, height))
    isOn = value in theSet

  if sk.mouseInsideClip(window, hitRect) and window.buttonReleased[MouseLeft]:
    if isOn:
      theSet.excl(value)
    else:
      theSet.incl(value)

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
  ## Draw the AoE panel with checkboxes for Clips and Cogs.
  frame(frameId, contentPos, contentSize):
    sk.at += vec2(8, 8)

    # Only show Clips (0) and Cogs (1) - the two main collectives
    coloredCheckBox("Clips", settings.aoeEnabledCollectives, 0, getAoeColor(0))
    coloredCheckBox("Cogs", settings.aoeEnabledCollectives, 1, getAoeColor(1))
