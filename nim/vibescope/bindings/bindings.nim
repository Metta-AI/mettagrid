import
  std/times,
  os, genny, openGL, jsony, vmath, windy, silky,
  ../src/vibescope,
  ../src/vibescope/[replays, common, worldmap, timeline, envconfig, vibes, windowstate, panels, heatmap, replayloader]

from std/sets import incl, excl, clear, items

type
  ActionRequest* = object
    agentId*: int
    actionName*: cstring

  RenderResponse* = ref object
    shouldClose*: bool
    actions*: seq[ActionRequest]

var
  savedVibescopeState: VibescopeState
  lastStateSaveTime: float64 = 0.0
  stateDirty: bool = false

proc captureSettingsState(): SettingsState =
  ## Capture the current settings.
  result.showFogOfWar = settings.showFogOfWar
  result.showVisualRange = settings.showVisualRange
  result.showGrid = settings.showGrid
  result.showResources = settings.showResources
  result.showObservations = settings.showObservations
  result.lockFocus = settings.lockFocus
  for id in settings.aoeEnabledCollectives:
    result.aoeEnabledCollectives.add(id)

proc applySettingsState(state: SettingsState) =
  ## Apply saved settings.
  settings.showFogOfWar = state.showFogOfWar
  settings.showVisualRange = state.showVisualRange
  settings.showGrid = state.showGrid
  settings.showResources = state.showResources
  settings.showObservations = state.showObservations
  settings.lockFocus = state.lockFocus
  settings.aoeEnabledCollectives.clear()
  for id in state.aoeEnabledCollectives:
    settings.aoeEnabledCollectives.incl(id)

proc saveFullState() =
  ## Save the full vibescope state.
  try:
    var state = VibescopeState()
    state.window = WindowState(
      x: window.pos.x,
      y: window.pos.y,
      width: window.size.x,
      height: window.size.y
    )
    state.zoom = captureZoomState()
    state.panels = capturePanelState()
    state.settings = captureSettingsState()
    saveVibescopeState(state)
  except:
    echo "Error saving state: ", getCurrentExceptionMsg()

proc maybeSaveState() =
  ## Save state if dirty and enough time has passed (debounce).
  # Check if view (pan/zoom) changed
  if viewStateChanged:
    viewStateChanged = false
    stateDirty = true
  let now = epochTime()
  if stateDirty and now - lastStateSaveTime > 1.0:
    saveFullState()
    lastStateSaveTime = now
    stateDirty = false

proc markStateDirty() =
  ## Mark state as needing to be saved.
  stateDirty = true

proc ctrlCHandler() {.noconv.} =
  ## Handle ctrl-c signal to exit cleanly.
  echo "\nNim DLL caught ctrl-c, exiting..."
  saveFullState()
  if not window.isNil:
    window.close()
  quit(0)

proc init(dataDir: string, replay: string, autostart: bool = false): RenderResponse =
  try:
    echo "Initializing Vibescope..."
    if os.getEnv("VIBESCOPE_DISABLE_CTRL_C", "") == "":
      setControlCHook(ctrlCHandler)
    result = RenderResponse(shouldClose: false, actions: @[])
    playMode = Realtime
    setDataDir(dataDir)
    play = autostart
    common.replay = loadReplayString(replay, "VibeScope")
    savedVibescopeState = loadVibescopeState()
    window = newWindow(
      "VibeScope",
      ivec2(savedVibescopeState.window.width, savedVibescopeState.window.height),
      vsync = true
    )
    applyWindowState(window, savedVibescopeState.window)
    # Set up window tracking callbacks
    window.onMove = proc() =
      markStateDirty()
    window.onResize = proc() =
      markStateDirty()
    makeContextCurrent(window)
    loadExtensions()
    # Check if we have saved panel state to restore
    let hasSavedPanels = savedVibescopeState.panels.areas.len > 0 or savedVibescopeState.panels.panelNames.len > 0
    initVibescope(useDefaultPanels = not hasSavedPanels)
    onReplayLoaded()
    # Restore saved panel layout
    if hasSavedPanels:
      applyPanelState(savedVibescopeState.panels)
    # Restore saved settings (AOE checkboxes, etc.)
    applySettingsState(savedVibescopeState.settings)
    # Set saved zoom state to be applied on first draw (when panel rect is available)
    if savedVibescopeState.zoom.zoom > 0:
      setSavedViewState(
        savedVibescopeState.zoom.zoom,
        savedVibescopeState.zoom.centerX,
        savedVibescopeState.zoom.centerY
      )
    return
  except Exception:
    echo "############ Error initializing Vibescope #################"
    echo getCurrentException().getStackTrace()
    echo getCurrentExceptionMsg()
    echo "############################################################"

    result.shouldClose = true
    return

proc render(currentStep: int, replayStep: string): RenderResponse =
  try:
    let hadAgentsBefore = common.replay.agents.len > 0
    common.replay.apply(replayStep)
    if worldHeatmap != nil:
      update(worldHeatmap, currentStep, replay)
    step = currentStep
    stepFloat = currentStep.float32
    previousStep = currentStep
    requestPython = false

    # If agents were just loaded for the first time, refit the world panel.
    if not hadAgentsBefore and common.replay.agents.len > 0:
      needsInitialFit = true
    result = RenderResponse(shouldClose: false, actions: @[])
    while true:
      if window.closeRequested:
        saveFullState()
        window.close()
        result.shouldClose = true
        return
      tickVibescope()
      maybeSaveState()
      if requestPython:
        onRequestPython()
        for action in requestActions:
          result.actions.add(ActionRequest(
            agentId: action.agentId,
            actionName: action.actionName
          ))
        requestActions.setLen(0)
        markStateDirty()
        return
  except Exception:
    echo "############## Error rendering Vibescope ##################"
    echo getCurrentException().getStackTrace()
    echo getCurrentExceptionMsg()
    echo "############################################################"
    result.shouldClose = true
    return

exportObject ActionRequest:
  discard

exportRefObject RenderResponse:
  fields:
    shouldClose
    actions

exportProcs:
  init
  render

writeFiles("bindings/generated", "Vibescope")

include generated/internal
