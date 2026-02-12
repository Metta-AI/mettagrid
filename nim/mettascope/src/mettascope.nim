import
  std/[strutils, strformat, os, parseopt, times],
  opengl, windy, bumpy, vmath, silky, webby,
  mettascope/[replays, common, worldmap, panels,
  footer, timeline, minimap, header, replayloader, configs, gameplayer],
  mettascope/panels/[objectpanel, policyinfopanel, envpanel, vibespanel, aoepanel, collectivepanel, scorepanel]

when isMainModule:
  let config = loadConfig()

  window = newWindow(
    "MettaScope",
    ivec2(config.windowWidth, config.windowHeight),
    vsync = true
  )
  makeContextCurrent(window)
  loadExtensions()

proc parseUrlParams() =
  ## Parse URL parameters.
  let url = parseUrl(window.url)
  commandLineReplay = url.query["replay"]

proc parseArgs() =
  ## Parse command line arguments.
  var p = initOptParser(commandLineParams())
  while true:
    p.next()
    case p.kind
    of cmdEnd:
      break
    of cmdLongOption, cmdShortOption:
      case p.key
      of "replay", "r":
        commandLineReplay = p.val
      of "game-mode", "g":
        forcedGameMode = Game
      of "editor-mode", "e":
        forcedGameMode = Editor
      of "autostart", "a":
        play = p.val == "true" or p.val == ""
      else:
        quit("Unknown option: " & p.key)
    of cmdArgument:
      quit("Unknown option: " & p.key)

proc replaySwitch(replay: string) =
  ## Load the replay.
  case common.playMode
  of Historical:
    if commandLineReplay != "":
      if commandLineReplay.startsWith("http"):
        common.replay = EmptyReplay
        echo "fetching replay from URL: ", commandLineReplay
        let req = startHttpRequest(commandLineReplay)
        req.onError = proc(msg: string) =
          echo "Failed to load replay from URL (network error): ", msg
          popupWarning = "Failed to load replay from URL.\nNetwork error: " & msg
        req.onResponse = proc(response: HttpResponse) =
          if response.code != 200:
            echo "Failed to load replay from URL (HTTP ", response.code, "): ", response.body
            case response.code:
            of 403:
              popupWarning = "Access denied (403 Forbidden).\nThe replay requires authentication or you don't have permission to access it."
            of 404:
              popupWarning = "Replay not found (404).\nThe replay URL is invalid or the file has been moved."
            of 500, 502, 503, 504:
              popupWarning = "Server error (" & $response.code & ").\nThe replay server is experiencing issues. Please try again later."
            else:
              popupWarning = "Failed to load replay (HTTP " & $response.code & ").\n" & response.body
            return
          echo "replay fetched, loading..."
          try:
            common.replay = loadReplay(response.body, commandLineReplay)
            onReplayLoaded()
          except:
            let err = getCurrentExceptionMsg()
            echo "Failed to load replay from URL (parse/load error): ", err
            popupWarning = "Failed to load replay from URL.\n" & err
            common.replay = EmptyReplay
      else:
        echo "Loading replay from file: ", commandLineReplay
        try:
          common.replay = loadReplay(commandLineReplay)
          onReplayLoaded()
        except:
          popupWarning = "Failed to load replay file.\n" & getCurrentExceptionMsg()
          common.replay = EmptyReplay
    elif common.replay == nil:
      let defaultReplay = dataDir / "replays" / "default.json.z"
      echo "Loading replay from default file: ", defaultReplay
      try:
        common.replay = loadReplay(defaultReplay)
        onReplayLoaded()
      except:
        popupWarning = "Failed to load default replay file.\n" & getCurrentExceptionMsg()
        common.replay = EmptyReplay
  of Realtime:
    echo "Realtime mode"
    onReplayLoaded()

proc drawWorldMap(panel: Panel, frameId: string, contentPos: Vec2, contentSize: Vec2) {.measure.} =
  ## Draw the world map.
  sk.draw9Patch("panel.body.empty.9patch", 3, contentPos, contentSize)

  worldMapZoomInfo.rect = irect(contentPos.x, contentPos.y, contentSize.x, contentSize.y)
  worldMapZoomInfo.hasMouse = sk.mouseInsideClip(window, rect(contentPos, contentSize))

  applyModeSwitchCenter(worldMapZoomInfo)

  glEnable(GL_SCISSOR_TEST)
  glScissor(contentPos.x.int32, window.size.y.int32 - contentPos.y.int32 - contentSize.y.int32, contentSize.x.int32, contentSize.y.int32)
  glClearColor(1.0f, 0.0f, 0.0f, 1.0f)

  saveTransform()
  translateTransform(contentPos)
  drawWorldMap(worldMapZoomInfo)
  restoreTransform()

  glDisable(GL_SCISSOR_TEST)

proc drawMinimap(panel: Panel, frameId: string, contentPos: Vec2, contentSize: Vec2) {.measure.} =
  ## Draw the minimap.
  sk.draw9Patch("panel.body.empty.9patch", 3, contentPos, contentSize)

  glEnable(GL_SCISSOR_TEST)
  glScissor(contentPos.x.int32, window.size.y.int32 - contentPos.y.int32 - contentSize.y.int32, contentSize.x.int32, contentSize.y.int32)

  let minimapZoomInfo = ZoomInfo()
  minimapZoomInfo.rect = irect(contentPos.x, contentPos.y, contentSize.x, contentSize.y)
  # Adjust zoom info and draw the minimap.
  minimapZoomInfo.hasMouse = false

  saveTransform()
  translateTransform(contentPos)
  drawMinimap(minimapZoomInfo)
  restoreTransform()

  glDisable(GL_SCISSOR_TEST)

proc createDefaultPanelLayout() =
  ## Create the default panel layout.
  rootArea = Area()
  rootArea.split(Vertical)
  rootArea.split = 0.22

  rootArea.areas[0].split(Horizontal)
  rootArea.areas[0].split = 0.7

  rootArea.areas[1].split(Vertical)
  rootArea.areas[1].split = 0.85

  rootArea.areas[0].areas[0].addPanel("Object", drawObjectInfo)
  rootArea.areas[0].areas[0].addPanel("Policy Info", drawPolicyInfo)
  rootArea.areas[0].areas[0].addPanel("Environment", drawEnvironmentInfo)

  rootArea.areas[1].areas[0].addPanel("Map", drawWorldMap)
  rootArea.areas[0].areas[1].addPanel("Minimap", drawMinimap)

  rootArea.areas[1].areas[1].addPanel("Vibes", drawVibes)
  rootArea.areas[1].areas[1].addPanel("AoE", drawAoePanel)
  rootArea.areas[1].areas[1].addPanel("Collectives", drawCollectivesPanel)
  rootArea.areas[1].areas[1].addPanel("Score", drawScorePanel)

proc collectPanelNames(area: Area): seq[string] =
  ## Collect all panel names from an area tree.
  for panel in area.panels:
    result.add(panel.name)
  for subarea in area.areas:
    result.add(collectPanelNames(subarea))

proc findFirstLeafArea(area: Area): Area =
  ## Find the first leaf area (one that has panels) in the tree.
  if area.panels.len > 0:
    return area
  for subarea in area.areas:
    let leaf = findFirstLeafArea(subarea)
    if leaf != nil:
      return leaf
  return nil

proc initPanels() =
  ## Initialize panels, loading layout from config if available.
  let config = loadConfig()
  applyUIState(config)
  createDefaultPanelLayout()

  # Remember the default panels before potentially overwriting with saved layout.
  let defaultArea = rootArea

  var layoutLoaded = false
  if config.panelLayout.areas.len > 0 or config.panelLayout.panelNames.len > 0:
    try:
      rootArea = deserializeArea(config.panelLayout, defaultArea)
      if validateAreaStructure(rootArea, true):
        layoutLoaded = true
      else:
        rootArea = defaultArea
    except:
      echo "Error loading panel layout from config, using default: ", getCurrentExceptionMsg()
      rootArea = defaultArea

  # Add any new panels from the default layout that are missing from the saved layout.
  if layoutLoaded:
    let savedNames = collectPanelNames(rootArea)
    let defaultNames = collectPanelNames(defaultArea)
    var missingPanels: seq[Panel] = @[]
    for name in defaultNames:
      if name notin savedNames:
        let refPanel = getPanelByName(defaultArea, name)
        if refPanel != nil:
          missingPanels.add(refPanel)
    if missingPanels.len > 0:
      let targetArea = findFirstLeafArea(rootArea)
      if targetArea != nil:
        for panel in missingPanels:
          let newPanel = Panel(name: panel.name, parentArea: targetArea, draw: panel.draw)
          targetArea.panels.add(newPanel)
          echo "Added missing panel: ", panel.name


proc onFrame() =

  playControls()

  sk.beginUI(window, window.size)

  glClearColor(0.0f, 0.0f, 0.0f, 1.0f)
  glClear(GL_COLOR_BUFFER_BIT)

  # Enable premultiplied alpha blending for all raw OpenGL shader draws.
  # Pixie textures (tilemaps, sprites, clouds, AoE overlays) are premultiplied.
  glEnable(GL_BLEND)
  glBlendFunc(GL_ONE, GL_ONE_MINUS_SRC_ALPHA)

  if gameMode == Editor:
    ## Editor mode UI.
    drawHeader()
    drawTimeline(vec2(0, sk.size.y - 64 - 33), vec2(sk.size.x, 32))
    drawFooter(vec2(0, sk.size.y - 64), vec2(sk.size.x, 64))
    drawPanels()
  else:
    ## Game mode UI.
    drawGameWorld()

  drawWarningPopup()
  sk.endUi()
  window.swapBuffers()

  if window.cursor.kind != sk.cursor.kind:
    window.cursor = sk.cursor

proc initMettascope*() {.measure.} =
  window.onFrame = onFrame

  window.onResize = proc() =
    var currentConfig = loadConfig()
    currentConfig.windowWidth = window.size.x.int32
    currentConfig.windowHeight = window.size.y.int32
    saveConfig(currentConfig)

  window.onFileDrop = proc(fileName: string, fileData: string) =
    echo "File dropped: ", fileName, " (", fileData.len, " bytes)"
    if fileName.endsWith(".json.z"):
      try:
        common.replay = loadReplay(fileData, fileName)
        onReplayLoaded()
        echo "Successfully loaded replay: ", fileName
      except:
        popupWarning = "Failed to load replay file.\n" & getCurrentExceptionMsg()
    else:
      popupWarning = "Unsupported file type.\nOnly .json.z replay files are supported."

  initPanels()

  sk = newSilky(dataDir / "silky.atlas.png", dataDir / "silky.atlas.json")

  ## Initialize the world map zoom info.
  worldMapZoomInfo = ZoomInfo()
  worldMapZoomInfo.rect = IRect(x: 0, y: 0, w: 500, h: 500)
  worldMapZoomInfo.pos = vec2(0, 0)
  worldMapZoomInfo.zoom = 10
  worldMapZoomInfo.minZoom = 0.5
  worldMapZoomInfo.maxZoom = 50
  worldMapZoomInfo.scrollArea = Rect(x: 0, y: 0, w: 500, h: 500)
  worldMapZoomInfo.hasMouse = false

  if playMode == Historical:
    when defined(emscripten):
      parseUrlParams()
    else:
      parseArgs()
    replaySwitch(commandLineReplay)

proc tickMettascope*() =
  pollEvents()

proc main() =
  ## Main entry point.
  ##
  when defined(profileOnStart):
    # Compile with -d:profileOnStart to start tracing on startup.
    # Don't forget to press F3 soon after startup dump the trace.
    traceActive = true
    startTrace()

  initMettascope()

  while not window.closeRequested:
    tickMettascope()

when isMainModule:
  main()
