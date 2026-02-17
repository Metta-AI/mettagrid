import
  os, genny, openGL, jsony, vmath, windy, silky,
  std/[times, math],
  ../src/mettascope,
  ../src/mettascope/[replays, common, worldmap, timeline, replayloader, heatmap, configs],
  ../src/mettascope/panels/[envpanel, vibespanel]

type
  ActionRequest* = object
    agentId*: int
    actionName*: cstring

  RenderResponse* = ref object
    shouldClose*: bool
    actions*: seq[ActionRequest]

const
  RealtimeSmoothMaxStepDelta = 1.5f

var
  realtimeTransitionActive = false
  realtimeTransitionStart = 0.0f
  realtimeTransitionTarget = 0.0f
  realtimeTransitionStartTime = 0.0
  realtimeTransitionDurationSeconds = 0.1

proc updateStepFloat() =
  ## Smoothly advance display step in realtime mode between Python updates.
  if not realtimeTransitionActive:
    return
  let
    elapsed = epochTime() - realtimeTransitionStartTime
    t = clamp((elapsed / realtimeTransitionDurationSeconds).float32, 0.0f, 1.0f)
  stepFloat = realtimeTransitionStart + (realtimeTransitionTarget - realtimeTransitionStart) * t
  if t >= 1.0f:
    stepFloat = realtimeTransitionTarget
    realtimeTransitionActive = false
    stepFloatSmoothing = false

proc ctrlCHandler() {.noconv.} =
  ## Handle ctrl-c signal to exit cleanly.
  echo "\nNim DLL caught ctrl-c, exiting..."
  if not window.isNil:
    window.close()
  quit(0)

proc init(dataDir: string, replay: string, autostart: bool = false): RenderResponse =
  try:
    echo "Initializing Mettascope..."
    if os.getEnv("METTASCOPE_DISABLE_CTRL_C", "") == "":
      setControlCHook(ctrlCHandler)
    result = RenderResponse(shouldClose: false, actions: @[])
    playMode = Realtime
    setDataDir(dataDir)
    play = autostart
    common.replay = loadReplayString(replay, "MettaScope")
    let config = loadConfig()

    window = newWindow(
      "MettaScope",
      ivec2(config.windowWidth, config.windowHeight),
      vsync = true
    )
    makeContextCurrent(window)
    loadExtensions()
    initMettascope()
    onReplayLoaded()
    return
  except Exception:
    echo "############ Error initializing Mettascope #################"
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
    let currentStepFloat = currentStep.float32
    if playMode == Realtime:
      let delta = abs(currentStepFloat - stepFloat)
      if delta > 0.0'f32 and delta <= RealtimeSmoothMaxStepDelta:
        realtimeTransitionStart = stepFloat
        realtimeTransitionTarget = currentStepFloat
        realtimeTransitionStartTime = epochTime()
        realtimeTransitionDurationSeconds = 1.0 / max(playSpeed.float64, 0.001)
        realtimeTransitionActive = true
        stepFloatSmoothing = true
      else:
        realtimeTransitionActive = false
        stepFloatSmoothing = false
        stepFloat = currentStepFloat
    else:
      realtimeTransitionActive = false
      stepFloatSmoothing = false
      stepFloat = currentStepFloat
    step = currentStep
    previousStep = currentStep
    requestPython = false

    if not hadAgentsBefore and common.replay.agents.len > 0:
      # fit the game world to the screen and update the UI state for any agents that should be selected
      needsInitialFit = true
      let config = loadConfig()
      applyUIState(config)
    result = RenderResponse(shouldClose: false, actions: @[])
    while true:
      if window.closeRequested:
        window.close()
        result.shouldClose = true
        return
      updateStepFloat()
      tickMettascope()
      if requestPython:
        onRequestPython()
        for action in requestActions:
          result.actions.add(ActionRequest(
            agentId: action.agentId,
            actionName: action.actionName.cstring
          ))
        requestActions.setLen(0)
        return
  except Exception:
    echo "############## Error rendering Mettascope ##################"
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

writeFiles("bindings/generated", "Mettascope")

include generated/internal
