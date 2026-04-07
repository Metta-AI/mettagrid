import
  std/[times, math],
  chroma, vmath, windy, silky,
  ../[common, actions, configs],
  ../gamemode/[gameplayer, timelineslider, sound, talk]

const
  ScrubberColor = parseHtmlColor("#1D1D1D").rgbx

var
  lastFrameTime: float64 = epochTime()

proc onRequestPython*() =
  ## Called before requesting Python to process the next step.
  processActions()

proc takeRequestActions*(processPython: bool): seq[ActionRequest] =
  ## Return queued actions for Python or drop them during pending-only renders.
  if processPython:
    processActions()
    result = requestActions
  requestActions.setLen(0)
  requestPython = false

proc playControls*() =
  if not talkComposeActive and window.buttonPressed[KeyEscape]:
    moveToggleActive = false
    queueToggleActive = false
    repeatToggleActive = false

  handleTalkComposerControls()

  let now = epochTime()
  let deltaTime = now - lastFrameTime
  let
    superDown =
      window.buttonDown[KeyLeftSuper] or window.buttonDown[KeyRightSuper]
    shiftDown =
      window.buttonDown[KeyLeftShift] or window.buttonDown[KeyRightShift]

  if shiftDown and
      (window.buttonPressed[KeyEqual] or window.buttonPressed[NumpadAdd]):
    sk.uiScale = min(sk.uiScale + 0.25'f, 4.0'f)
    saveUIState()
    playSound("UIbutton.wav")
  if shiftDown and
      (window.buttonPressed[KeyMinus] or window.buttonPressed[NumpadSubtract]):
    sk.uiScale = max(sk.uiScale - 0.25'f, 0.25'f)
    saveUIState()
    playSound("UIbutton.wav")

  if not talkComposeActive and superDown and window.buttonPressed[KeyQ]:
    when not defined(emscripten):
      window.closeRequested = true

  if not talkComposeActive and window.buttonPressed[KeySpace]:
    play = not play
    playSound("UIswitch.wav")
  if not talkComposeActive and not shiftDown and window.buttonPressed[KeyMinus]:
    playSpeed *= 0.5
    playSpeed = clamp(playSpeed, 0.00001, 1000.0)
    play = true
    playSound("UIbutton.wav")
  if not talkComposeActive and not shiftDown and window.buttonPressed[KeyEqual]:
    playSpeed *= 2
    playSpeed = clamp(playSpeed, 0.00001, 1000.0)
    play = true
    playSound("UIbutton.wav")
  if window.buttonPressed[KeyF10] or
      (not talkComposeActive and window.buttonPressed[KeyG]):
    let newMode = if gameMode == Editor: Game else: Editor
    switchGameMode(newMode)
  if not talkComposeActive and window.buttonPressed[KeyF] and selected != nil:
    settings.lockFocus = true
    saveUIState()
    playSound("UIswitch.wav")

  if play:
    case playMode:
    of Historical:
      stepFloat += playSpeed * deltaTime
      if stepFloat >= replay.maxSteps.float32:
        # Loop back to the start.
        stepFloat -= replay.maxSteps.float32
    of Realtime:
      # In realtime mode, Python owns the next step. The local timeline only
      # catches up when the user has scrubbed behind the latest available step.
      let latestStepFloat = replay.maxSteps.float32 - 1.0f
      if stepFloatSmoothing:
        discard
      elif stepFloat < latestStepFloat:
        stepFloat += playSpeed * deltaTime
        stepFloat = min(stepFloat, latestStepFloat)
      else:
        requestPython = true
    step = stepFloat.int
    step = step.clamp(0, replay.maxSteps - 1)

  if not talkComposeActive and window.buttonPressed[KeyLeftBracket]:
    step -= 1
    step = clamp(step, 0, replay.maxSteps - 1)
    stepFloat = step.float32
    playSound("UIbutton.wav")
  if not talkComposeActive and window.buttonPressed[KeyRightBracket]:
    step += 1
    if playMode == Realtime and step >= replay.maxSteps:
      requestPython = true
      step = replay.maxSteps - 1
    step = clamp(step, 0, replay.maxSteps - 1)
    stepFloat = step.float32
    playSound("UIbutton.wav")
  # Fire onStepChanged once and only once when step changes.
  if step != previousStep:
    previousStep = step

  lastFrameTime = now

proc drawTimeline*(pos, size: Vec2) =
  ribbon(pos, size, ScrubberColor):
    let
      prevStepFloat = stepFloat
      maxStepFloat =
        if playMode == Realtime and stepFloatSmoothing:
          stepFloat
        else:
          replay.maxSteps.float32 - 1
      displayStep = $int(stepFloat + 0.5)
    sk.at.y -= 12
    drawTimelineSlider("timeline", stepFloat, 0, maxStepFloat, displayStep)
    if prevStepFloat != stepFloat:
      step = stepFloat.round.int
