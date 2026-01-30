import
  silky, chroma, vmath,
  ./[common, configs]

const
  FooterColor = parseHtmlColor("#273646").rgbx
  Speeds = [1.0, 5.0, 10.0, 50.0, 100.0, 1000.0]

proc drawFooter*(pos, size: Vec2) =
  ribbon(pos, size, FooterColor):

    let pos = sk.pos
    let size = sk.size

    sk.at = pos + vec2(16, 16)
    group(vec2(0, 0), LeftToRight):
      clickableIcon("ui/rewindToStart", step != 0):
        step = 0
        stepFloat = step.float32
        saveUIState()
      if sk.shouldShowTooltip:
        tooltip("Rewind to Start")
      clickableIcon("ui/stepBack", step > 0):
        step -= 1
        step = clamp(step, 0, replay.maxSteps - 1)
        stepFloat = step.float32
        saveUIState()
      if sk.shouldShowTooltip:
        tooltip("Step Back")
      if play:
        clickableIcon("ui/pause", true):
          play = false
          saveUIState()
      else:
        clickableIcon("ui/play", true):
          play = true
          saveUIState()
      if sk.shouldShowTooltip:
        if play:
          tooltip("Pause")
        else:
          tooltip("Play")
      clickableIcon("ui/stepForward", step < replay.maxSteps - 1):
        step += 1
        if step > replay.maxSteps - 1:
          requestPython = true
        step = clamp(step, 0, replay.maxSteps - 1)
        stepFloat = step.float32
        saveUIState()
      if sk.shouldShowTooltip:
        tooltip("Step Forward")
      clickableIcon("ui/rewindToEnd", step != replay.maxSteps - 1):
        step = replay.maxSteps - 1
        stepFloat = step.float32
        saveUIState()
      if sk.shouldShowTooltip:
        tooltip("Rewind to End")

    sk.at = pos + vec2(size.x/2 - 120, 16)
    group(vec2(0, 0), LeftToRight):
      for i, speed in Speeds:
        if i == 0:
          clickableIcon("ui/turtle", playSpeed >= speed):
            playSpeed = speed
            saveUIState()
          if sk.shouldShowTooltip:
            tooltip("Speed: " & $speed & "x (Slowest)")
        elif i == len(Speeds) - 1:
          clickableIcon("ui/rabbit", playSpeed >= speed):
            playSpeed = speed
            saveUIState()
          if sk.shouldShowTooltip:
            tooltip("Speed: " & $speed & "x (Fastest)")
        else:
          clickableIcon("ui/speed", playSpeed >= speed):
            playSpeed = speed
            saveUIState()
          if sk.shouldShowTooltip:
            tooltip("Speed: " & $speed & "x")

    sk.at = pos + vec2(size.x - 240, 16)
    group(vec2(0, 0), LeftToRight):
      clickableIcon("ui/tack", settings.lockFocus):
        settings.lockFocus = not settings.lockFocus
        saveUIState()
      if sk.shouldShowTooltip:
        tooltip(if settings.lockFocus: "Unlock Focus" else: "Lock Focus")
      clickableIcon("ui/heart", settings.showResources):
        settings.showResources = not settings.showResources
        saveUIState()
      if sk.shouldShowTooltip:
        tooltip(if settings.showResources: "Hide Resources" else: "Show Resources")
      clickableIcon("ui/grid", settings.showGrid):
        settings.showGrid = not settings.showGrid
        saveUIState()
      if sk.shouldShowTooltip:
        tooltip(if settings.showGrid: "Hide Grid" else: "Show Grid")
      clickableIcon("ui/eye", settings.showVisualRange):
        settings.showVisualRange = not settings.showVisualRange
        saveUIState()
      if sk.shouldShowTooltip:
        tooltip(if settings.showVisualRange: "Hide Visual Range" else: "Show Visual Range")
      clickableIcon("ui/cloud", settings.showFogOfWar):
        settings.showFogOfWar = not settings.showFogOfWar
        saveUIState()
      if sk.shouldShowTooltip:
        tooltip(if settings.showFogOfWar: "Hide Fog of War" else: "Show Fog of War")
      clickableIcon("ui/heatmap", settings.showHeatmap):
        settings.showHeatmap = not settings.showHeatmap
        saveUIState()
      if sk.shouldShowTooltip:
        tooltip(if settings.showHeatmap: "Hide Heatmap" else: "Show Heatmap")
