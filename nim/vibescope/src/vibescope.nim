import
  std/[strutils, strformat, os, parseopt, tables],
  opengl, windy, bumpy, vmath, chroma, silky, boxy, webby,
  vibescope/[replays, common, worldmap, panels, objectinfo, envconfig, vibes,
  footer, timeline, minimap, header, replayloader, aoepanel, commonspanel,
  eventstimeline, configs]

proc buildSilkyAtlas*(imagePath, jsonPath: string) =
  ## Build the silky UI atlas.
  var builder = newAtlasBuilder(1024, 4)
  builder.addDir(dataDir / "theme/", dataDir / "theme/")
  builder.addDir(dataDir / "ui/", dataDir & "/")
  builder.addDir(dataDir / "vibe/", dataDir & "/")
  builder.addDir(dataDir / "resources/", dataDir & "/")
  # builder.addDir(dataDir / "agents/", dataDir / "agents/")
  builder.addFont(dataDir / "fonts/Inter-Regular.ttf", "H1", 32.0)
  builder.addFont(dataDir / "fonts/Inter-Regular.ttf", "Default", 18.0)
  builder.write(imagePath, jsonPath)

when isMainModule:
  buildSilkyAtlas(dataDir / "silky.atlas.png", dataDir / "silky.atlas.json")
  let config = loadConfig()

  window = newWindow(
    "VibeScope",
    ivec2(config.windowWidth, config.windowHeight),
    vsync = true
  )
  makeContextCurrent(window)
  loadExtensions()

const
  BackgroundColor = parseHtmlColor("#000000").rgbx
  RibbonColor = parseHtmlColor("#273646").rgbx
  m = 12f # Default margin

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
      else:
        quit("Unknown option: " & p.key)
    of cmdArgument:
      quit("Unknown option: " & p.key)

proc parseUrlParams() =
  ## Parse URL parameters.
  let url = parseUrl(window.url)
  commandLineReplay = url.query["replay"]

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
          popupWarning = "Failed to load replay from URL.\nNetwork error: " & msg
        req.onResponse = proc(response: HttpResponse) =
          if response.code != 200:
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
          common.replay = loadReplay(response.body, commandLineReplay)
          onReplayLoaded()
      else:
        echo "Loading replay from file: ", commandLineReplay
        common.replay = loadReplay(commandLineReplay)
        onReplayLoaded()
    elif common.replay == nil:
      let defaultReplay = dataDir / "replays" / "dinky7.json.z"
      echo "Loading replay from default file: ", defaultReplay
      common.replay = loadReplay(defaultReplay)
      onReplayLoaded()
  of Realtime:
    echo "Realtime mode"
    onReplayLoaded()

proc genericPanelDraw(panel: panels.Panel, frameId: string, contentPos: Vec2, contentSize: Vec2) =
  frame(frameId, contentPos, contentSize):
    # Start content a bit inset.
    sk.at += vec2(8, 8)
    h1text(panel.name)
    text("This is the content of " & panel.name)
    for i in 0 ..< 20:
      text(&"Scrollable line {i} for " & panel.name)

proc drawWorldMap(panel: panels.Panel, frameId: string, contentPos: Vec2, contentSize: Vec2) =
  ## Draw the world map.
  sk.draw9Patch("panel.body.empty.9patch", 3, contentPos, contentSize)

  worldMapZoomInfo.rect = irect(contentPos.x, contentPos.y, contentSize.x, contentSize.y)
  worldMapZoomInfo.hasMouse = mouseInsideClip(rect(contentPos, contentSize))

  glEnable(GL_SCISSOR_TEST)
  glScissor(contentPos.x.int32, window.size.y.int32 - contentPos.y.int32 - contentSize.y.int32, contentSize.x.int32, contentSize.y.int32)
  glClearColor(1.0f, 0.0f, 0.0f, 1.0f)

  bxy.saveTransform()
  bxy.translate(contentPos)
  drawWorldMap(worldMapZoomInfo)
  bxy.restoreTransform()

  glDisable(GL_SCISSOR_TEST)

proc drawMinimap(panel: panels.Panel, frameId: string, contentPos: Vec2, contentSize: Vec2) =
  ## Draw the minimap.
  sk.draw9Patch("panel.body.empty.9patch", 3, contentPos, contentSize)

  glEnable(GL_SCISSOR_TEST)
  glScissor(contentPos.x.int32, window.size.y.int32 - contentPos.y.int32 - contentSize.y.int32, contentSize.x.int32, contentSize.y.int32)

  let minimapZoomInfo = ZoomInfo()
  minimapZoomInfo.rect = irect(contentPos.x, contentPos.y, contentSize.x, contentSize.y)
  # Adjust zoom info and draw the minimap.
  minimapZoomInfo.hasMouse = false

  bxy.saveTransform()
  bxy.translate(contentPos)
  drawMinimap(minimapZoomInfo)
  bxy.restoreTransform()

  glDisable(GL_SCISSOR_TEST)

proc registerPanels() =
  ## Register all panels so they can be restored from saved state.
  registerPanel("Object", drawObjectInfo)
  registerPanel("Environment", drawEnvironmentInfo)
  registerPanel("Collectives", drawCollectivesPanel)
  registerPanel("Map", drawWorldMap)
  registerPanel("Minimap", drawMinimap)
  registerPanel("Vibes", drawVibes)
  registerPanel("AOE", drawAoePanel)

proc initPanels() =
  ## Initialize default panel layout.
  panels.rootArea = panels.Area()
  panels.rootArea.split(Vertical)
  panels.rootArea.split = 0.22

  panels.rootArea.areas[0].split(Horizontal)
  panels.rootArea.areas[0].split = 0.7

  panels.rootArea.areas[1].split(Vertical)
  panels.rootArea.areas[1].split = 0.85

  panels.rootArea.areas[0].areas[0].addPanel("Object", drawObjectInfo)
  panels.rootArea.areas[0].areas[0].addPanel("Environment", drawEnvironmentInfo)
  panels.rootArea.areas[0].areas[0].addPanel("Collectives", drawCollectivesPanel)

  panels.rootArea.areas[1].areas[0].addPanel("Map", drawWorldMap)
  panels.rootArea.areas[0].areas[1].addPanel("Minimap", drawMinimap)

  panels.rootArea.areas[1].areas[1].addPanel("Vibes", drawVibes)
  panels.rootArea.areas[1].areas[1].addPanel("AOE", drawAoePanel)


proc onFrame() =

  playControls()

  sk.beginUI(window, window.size)

  glClearColor(0.0f, 0.0f, 0.0f, 1.0f)
  glClear(GL_COLOR_BUFFER_BIT)

  # Header
  try:
    drawHeader()
  except:
    echo "Error in drawHeader: ", getCurrentExceptionMsg()

  # Events timeline (above scrubber)
  try:
    if settings.showEventsTimeline and hasEvents():
      drawEventsTimeline(
        vec2(0, sk.size.y - 64 - 22 - EventsTimelineHeight),
        vec2(sk.size.x, EventsTimelineHeight))
  except:
    echo "Error in drawEventsTimeline: ", getCurrentExceptionMsg()

  # Scrubber
  try:
    drawTimeline(vec2(0, sk.size.y - 64 - 22), vec2(sk.size.x, 32))
  except:
    echo "Error in drawTimeline: ", getCurrentExceptionMsg()

  # Footer
  try:
    drawFooter(vec2(0, sk.size.y - 64), vec2(sk.size.x, 64))
  except:
    echo "Error in drawFooter: ", getCurrentExceptionMsg()

  try:
    drawPanels()
  except:
    echo "Error in drawPanels: ", getCurrentExceptionMsg()

  drawWarningPopup()

  when defined(profile):
    let ms = sk.avgFrameTime * 1000
    sk.at = sk.pos + vec2(sk.size.x - 250, 20)
    text(&"frame time: {ms:>7.3f}ms\nquads: {sk.instanceCount}")

  sk.endUi()
  window.swapBuffers()

  if window.cursor.kind != sk.cursor.kind:
    window.cursor = sk.cursor

proc initVibescope*(useDefaultPanels: bool = true) =
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

  # Always register panels so they can be restored from saved state
  registerPanels()

  if useDefaultPanels:
    initPanels()

  sk = newSilky(dataDir / "silky.atlas.png", dataDir / "silky.atlas.json")
  bxy = newBoxy()

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

proc tickVibescope*() =
  pollEvents()

proc main() =
  ## Main entry point.
  initVibescope()

  while not window.closeRequested:
    tickVibescope()

when isMainModule:
  main()
