## AOE panel displays checkboxes to toggle AOE overlays for each team.

import
  std/[algorithm, json, strformat, sets],
  bumpy, silky, chroma, vmath, windy,
  common, panels, replays

const
  UnalignedId* = -1

proc getCollectivesNode(): JsonNode =
  ## Get the collectives JSON node (dict) from the replay config.
  if replay.isNil or replay.mgConfig.isNil:
    return nil
  if "game" notin replay.mgConfig or "collectives" notin replay.mgConfig["game"]:
    return nil
  let collectives = replay.mgConfig["game"]["collectives"]
  if collectives.kind != JObject:
    return nil
  return collectives

proc getNumCollectives*(): int =
  ## Get the number of collectives from the replay config.
  let collectives = getCollectivesNode()
  if collectives.isNil:
    return 0
  return collectives.len

proc getCollectiveName*(collectiveId: int): string =
  ## Get the collective name by ID from the mg_config.
  ## IDs are assigned alphabetically (matching C++/Python), so we sort keys first.
  let collectives = getCollectivesNode()
  if collectives.isNil or collectiveId < 0:
    return ""
  var names: seq[string] = @[]
  for name, _ in collectives.pairs:
    names.add(name)
  names.sort()
  if collectiveId < names.len:
    return names[collectiveId]
  return ""

proc getCollectiveConfig*(collectiveId: int): JsonNode =
  ## Get the collective config by ID from the mg_config.
  ## IDs are assigned alphabetically (matching C++/Python), so we sort keys first.
  let collectives = getCollectivesNode()
  if collectives.isNil or collectiveId < 0:
    return nil
  var names: seq[string] = @[]
  for name, _ in collectives.pairs:
    names.add(name)
  names.sort()
  if collectiveId < names.len:
    return collectives[names[collectiveId]]
  return nil

proc getAoeColor*(collectiveId: int): Color =
  ## Get color for collective by looking up its name. Clips = red, Cogs = green.
  ## IDs are assigned alphabetically, so we look up the name to determine color.
  if collectiveId == UnalignedId:
    return color(0.5, 0.5, 0.5, 0.4)  # Neutral = grey
  let name = getCollectiveName(collectiveId)
  case name
  of "cogs": color(0.2, 0.8, 0.2, 0.4)   # Cogs = green
  of "clips": color(0.9, 0.2, 0.2, 0.4)  # Clips = red
  else: color(0.5, 0.5, 0.5, 0.4)        # Others = grey

proc drawAoeToggle(label: string, enabled: bool, tintColor: Color): bool =
  ## Draw a toggle button with a color indicator. Returns true if clicked.
  let boxSize = 20.0f
  let spacing = 8.0f
  let textSize = sk.getTextSize("Default", label)
  let totalWidth = boxSize + spacing + textSize.x
  let totalHeight = max(boxSize, textSize.y)
  let startPos = sk.at
  # Draw color box.
  let tintRgbx = rgbx(
    (tintColor.r * 255).uint8,
    (tintColor.g * 255).uint8,
    (tintColor.b * 255).uint8,
    255
  )
  sk.drawRect(startPos, vec2(boxSize, boxSize), tintRgbx)
  # Draw check mark if enabled.
  if enabled:
    sk.drawRect(startPos + vec2(4, 4), vec2(boxSize - 8, boxSize - 8), rgbx(255, 255, 255, 255))
  # Draw label.
  discard sk.drawText("Default", label, startPos + vec2(boxSize + spacing, 2), rgbx(255, 255, 255, 255))
  # Advance the layout.
  sk.advance(vec2(0, totalHeight + 4))
  # Handle click.
  let clickRect = bumpy.rect(startPos, vec2(totalWidth, totalHeight))
  if mouseInsideClip(clickRect) and window.buttonPressed[MouseLeft]:
    return true
  return false

proc drawAoePanel*(panel: panels.Panel, frameId: string, contentPos: Vec2, contentSize: Vec2) =
  ## Draw the AOE panel with checkboxes for each team.
  frame(frameId, contentPos, contentSize):
    sk.at += vec2(8, 8)
    h1text("AOE Overlays")
    sk.advance(vec2(0, 8))
    let numCollectives = getNumCollectives()
    # Draw toggle for unaligned objects.
    let unalignedEnabled = UnalignedId in settings.aoeEnabledCollectives
    let unalignedColor = getAoeColor(UnalignedId)
    if drawAoeToggle("Unaligned", unalignedEnabled, unalignedColor):
      if UnalignedId in settings.aoeEnabledCollectives:
        settings.aoeEnabledCollectives.excl(UnalignedId)
      else:
        settings.aoeEnabledCollectives.incl(UnalignedId)
      viewStateChanged = true
    # Draw toggle for each team.
    for i in 0 ..< numCollectives:
      let collectiveName = getCollectiveName(i)
      let displayName = if collectiveName.len > 0: collectiveName else: &"Team {i}"
      let enabled = i in settings.aoeEnabledCollectives
      let teamColor = getAoeColor(i)
      if drawAoeToggle(displayName, enabled, teamColor):
        if i in settings.aoeEnabledCollectives:
          settings.aoeEnabledCollectives.excl(i)
        else:
          settings.aoeEnabledCollectives.incl(i)
        viewStateChanged = true
    # Add toggle all/none buttons.
    sk.advance(vec2(0, 12))
    group(vec2(0, 0), LeftToRight):
      button("All"):
        settings.aoeEnabledCollectives.incl(UnalignedId)
        for i in 0 ..< numCollectives:
          settings.aoeEnabledCollectives.incl(i)
        viewStateChanged = true
      button("None"):
        settings.aoeEnabledCollectives.clear()
        viewStateChanged = true

