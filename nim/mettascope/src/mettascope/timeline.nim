import
  std/[times, math],
  chroma, vmath, windy, silky,
  common, actions, gameplayer, timelineslider

const
  ScrubberColor = parseHtmlColor("#1D1D1D").rgbx

var
  lastFrameTime: float64 = epochTime()

proc onRequestPython*() =
  ## Called before requesting Python to process the next step.
  processActions()

proc playControls*() =
  let now = epochTime()
  let deltaTime = now - lastFrameTime

  let superDown =
    window.buttonDown[KeyLeftSuper] or window.buttonDown[KeyRightSuper]
  if superDown and window.buttonPressed[KeyQ]:
    when not defined(emscripten):
      window.closeRequested = true

  if window.buttonPressed[KeySpace]:
    play = not play
    stepFloat = step.float32
  if window.buttonPressed[KeyMinus]:
    playSpeed *= 0.5
    playSpeed = clamp(playSpeed, 0.00001, 1000.0)
    play = true
  if window.buttonPressed[KeyEqual]:
    playSpeed *= 2
    playSpeed = clamp(playSpeed, 0.00001, 1000.0)
    play = true
  if window.buttonPressed[KeyF10] or window.buttonPressed[KeyG]:
    let newMode = if gameMode == Editor: Game else: Editor
    switchGameMode(newMode)

  if play:
    stepFloat += playSpeed * deltaTime
    case playMode:
    of Historical:
      if stepFloat >= replay.maxSteps.float32:
        # Loop back to the start.
        stepFloat -= replay.maxSteps.float32
    of Realtime:
      if stepFloat >= replay.maxSteps.float32:
        # Requesting more steps from Python.
        requestPython = true
        stepFloat = replay.maxSteps.float32 - 1
    step = stepFloat.int
    step = step.clamp(0, replay.maxSteps - 1)

  if window.buttonPressed[KeyLeftBracket]:
    step -= 1
    step = clamp(step, 0, replay.maxSteps - 1)
    stepFloat = step.float32
  if window.buttonPressed[KeyRightBracket]:
    step += 1
    if playMode == Realtime and step >= replay.maxSteps:
      requestPython = true
      step = replay.maxSteps - 1
    step = clamp(step, 0, replay.maxSteps - 1)
    stepFloat = step.float32
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
