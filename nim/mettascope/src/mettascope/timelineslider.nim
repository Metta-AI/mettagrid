import
  std/tables,
  bumpy, vmath, windy, silky,
  common

type
  TimelineSliderState = ref object
    dragging: bool

var
  timelineSliderStates = initTable[string, TimelineSliderState]()

proc getTimelineSliderState(id: string): TimelineSliderState =
  ## Get or create slider interaction state for the given ID.
  if id notin timelineSliderStates:
    timelineSliderStates[id] = TimelineSliderState()
  timelineSliderStates[id]

proc drawTimelineSlider*(id: string, value: var float32, minVal: float32, maxVal: float32, label: string = "") =
  ## Draw a mettascope timeline slider.
  ## Similar to the slider in silky but customized for mettascope.
  let
    minF = minVal
    maxF = maxVal
    range = maxF - minF

  let
    clampedValue = clamp(value, minF, maxF)
    sliderState = getTimelineSliderState(id)

  let
    baseHandleSize = sk.getImageSize("scrubber.handle")
    buttonHandleSize = sk.getImageSize("button.9patch")
    labelSize = if label.len > 0: sk.getTextSize(sk.textStyle, label) else: vec2(0, 0)
    minLabelSize = if label.len > 0: sk.getTextSize(sk.textStyle, "0000") else: vec2(0, 0)
    knobTextPadding = sk.theme.padding.float32 * 2 + 8f
    handleWidth =
      if label.len > 0:
        max(buttonHandleSize.x, max(labelSize.x, minLabelSize.x) + knobTextPadding)
      else:
        baseHandleSize.x
    handleHeight = if label.len > 0: max(buttonHandleSize.y, baseHandleSize.y) else: baseHandleSize.y
    handleSize = vec2(handleWidth, handleHeight)
    height = handleSize.y
    width = sk.size.x
    controlRect = bumpy.rect(sk.at, vec2(width, height))
    trackStart = controlRect.x + handleSize.x / 2
    trackEnd = controlRect.x + width - handleSize.x / 2
    travel = max(0f, trackEnd - trackStart)
    travelSafe = if travel <= 0: 1f else: travel

  sk.draw9Patch(
    "scrubber.body.9patch",
    4,
    controlRect.xy,
    controlRect.wh
  )

  let norm = if range == 0: 0f else: clamp((clampedValue - minF) / range, 0f, 1f)
  let
    handlePos = vec2(trackStart + norm * travel - handleSize.x * 0.5, controlRect.y + (height - handleSize.y) * 0.5)
    handleRect = bumpy.rect(handlePos, handleSize)

  if sliderState.dragging and (window.buttonReleased[MouseLeft] or not window.buttonDown[MouseLeft]):
    sliderState.dragging = false

  if sliderState.dragging:
    let t = clamp((window.mousePos.vec2.x - trackStart) / travelSafe, 0f, 1f)
    value = minF + t * range
  elif sk.mouseInsideClip(window, handleRect) or sk.mouseInsideClip(window, controlRect):
    if window.buttonPressed[MouseLeft]:
      sliderState.dragging = true
      let t = clamp((window.mousePos.vec2.x - trackStart) / travelSafe, 0f, 1f)
      value = minF + t * range

  let displayValue = clamp(value, minF, maxF)
  let norm2 = if range == 0: 0f else: clamp((displayValue - minF) / range, 0f, 1f)
  let handlePos2 = vec2(trackStart + norm2 * travel - handleSize.x * 0.5, controlRect.y + (height - handleSize.y) * 0.5)

  if label.len > 0:
    sk.draw9Patch("button.9patch", 8, handlePos2, handleSize)
    let textPos = vec2(
      handlePos2.x + (handleSize.x - labelSize.x) * 0.5,
      handlePos2.y + (handleSize.y - labelSize.y) * 0.5
    )
    discard sk.drawText(sk.textStyle, label, textPos, sk.theme.defaultTextColor)
  else:
    sk.drawImage("scrubber.handle", handlePos2)

  sk.advance(vec2(width, height))
