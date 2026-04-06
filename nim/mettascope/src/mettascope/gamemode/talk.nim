import
  std/[math, strutils, tables],
  bumpy, chroma, vmath, silky,
  ../[common, replays, colors],
  ./[camera, movement]

var
  talkComposeActive*: bool
  talkComposeAgentId*: int = -1
  talkComposeInputId*: int
  talkComposeNeedsFocus: bool
  talkComposeText*: string = ""

proc clearTalkCompose*() =
  ## Clear the active manual talk draft and disable text input capture.
  talkComposeActive = false
  talkComposeAgentId = -1
  talkComposeNeedsFocus = false
  talkComposeText.setLen(0)
  window.runeInputEnabled = false

proc ensureTalkComposeSelection*() =
  ## Cancel composition when selection moves off the composing agent.
  if talkComposeActive and
      (selected.isNil or
      not selected.isAgent or
      selected.agentId != talkComposeAgentId):
    clearTalkCompose()

proc sanitizeTalkText*(text: string, limit: int): string =
  ## Keep only printable ASCII characters and clamp to the talk limit.
  let safeLimit = max(1, limit)
  for c in text:
    let code = c.int
    if code < 32 or code > 126:
      continue
    if result.len >= safeLimit:
      break
    result.add(c)

proc syncTalkComposeInput*(inputId: string, limit: int) =
  ## Keep focus, cursor, and text state aligned with the active talk draft.
  let inputState = textBoxStates[inputId]

  talkComposeText = sanitizeTalkText(talkComposeText, limit)
  let needsSync = inputState.getText() != talkComposeText
  if needsSync:
    inputState.setText(talkComposeText)
  if talkComposeNeedsFocus or needsSync:
    inputState.focused = true
    inputState.cursor = inputState.runes.len
    inputState.selector = inputState.cursor
    inputState.resetBlink()
    talkComposeNeedsFocus = false

proc beginTalkComposeForSelected*() =
  ## Begin talk composition for the selected agent.
  if replay.isNil or not replay.config.game.talk.enabled:
    return

  ensureTalkComposeSelection()

  if selected.isNil or not selected.isAgent:
    return
  let agent = selected
  if talkComposeActive or max(0, agent.talkRemainingSteps.at(step)) > 0:
    return

  talkComposeActive = true
  talkComposeAgentId = agent.agentId
  inc talkComposeInputId
  talkComposeNeedsFocus = true
  talkComposeText.setLen(0)
  window.runeInputEnabled = true

proc submitTalkCompose*() =
  ## Submit the current talk draft for the selected agent.
  ensureTalkComposeSelection()

  if not talkComposeActive:
    return

  let draft = talkComposeText.strip()
  if draft.len == 0:
    clearTalkCompose()
    return

  let agent = selected
  if max(0, agent.talkRemainingSteps.at(step)) > 0:
    return

  if requestActions.len == 0 or requestActions[^1].agentId != agent.agentId:
    requestActions.add(ActionRequest(
      agentId: agent.agentId,
      actionName: "",
      talkText: draft
    ))
  else:
    requestActions[^1].talkText = draft
  requestPython = true
  clearTalkCompose()

proc handleTalkComposerControls*() =
  ## Handle keyboard shortcuts for the talk composer.
  if replay.isNil or not replay.config.game.talk.enabled:
    if talkComposeActive:
      clearTalkCompose()
    return

  ensureTalkComposeSelection()

  if window.buttonPressed[KeyEscape]:
    clearTalkCompose()
  elif window.buttonPressed[KeyEnter]:
    if talkComposeActive:
      submitTalkCompose()
    else:
      beginTalkComposeForSelected()

proc centeredTalkComposer*(winW: float32, winH: float32) =
  ## Draw a centered lower-screen talk composer, separate from the right panel.
  if replay.isNil or not replay.config.game.talk.enabled:
    return
  ensureTalkComposeSelection()
  if not talkComposeActive:
    return

  const
    TalkFrameMaxWidth = 980.0'f
    TalkFrameHeight = 56.0'f
    TalkFrameGap = 18.0'f

  let
    maxTalkWidth = max(320.0'f, min(TalkFrameMaxWidth, winW - 40.0'f))
    talkWidth = min(maxTalkWidth, max(440.0'f, winW - 180.0'f))
    centerPanelSize = sk.getImageSize("ui/panel_center")
    centerPanelY = winH - centerPanelSize.y - 20.0'f
    talkY = centerPanelY - TalkFrameHeight - TalkFrameGap

  let talkPos = vec2(
    (winW - talkWidth) * 0.5'f,
    max(28.0'f, talkY)
  )
  let talkSize = vec2(talkWidth, TalkFrameHeight)
  if window.mousePos.vec2.overlaps(rect(talkPos, talkSize)):
    worldMapZoomInfo.hasMouse = false

  let
    limit = max(1, replay.config.game.talk.maxLength)
    inputId = "gameTalkCompose." & $talkComposeInputId

  sk.pushLayout(talkPos, talkSize)
  textBox(
    inputId,
    talkComposeText,
    talkSize.x,
    talkSize.y,
    wrapWords = false,
    singleLine = true
  )
  syncTalkComposeInput(inputId, limit)
  sk.popLayout()

proc drawTalkBubble(agent: Entity, zoomInfo: ZoomInfo) =
  ## Draw the talk bubble for one agent when talk is active.
  const
    TalkBubbleMinWidth = 180.0'f
    TalkBubblePreferredMaxWidth = 520.0'f
    TalkBubbleWidthStep = 32.0'f
    TalkBubbleMargin = 8.0'f
    TalkBubbleLiftTiles = 1.15'f
    TalkBubblePadding = vec2(14.0'f, 14.0'f)
    TalkBubbleOffset = vec2(20.0'f, -20.0'f)

  let talkText = agent.talkText.at(step)
  if talkText.len == 0:
    return

  let remainingSteps = max(0, agent.talkRemainingSteps.at(step))
  if remainingSteps <= 0:
    return

  proc wrapTalkBubbleLines(text: string, maxTextWidth: float32): seq[string] =
    ## Wrap the talk text into width-limited lines for the bubble.
    let normalized = strutils.splitWhitespace(text).join(" ")
    if normalized.len == 0:
      return @[""]

    var currentLine = ""
    for word in normalized.split(' '):
      if word.len == 0:
        continue
      if sk.getTextSize("pixelated", word).x > maxTextWidth:
        if currentLine.len > 0:
          result.add(currentLine)
          currentLine = ""
        var currentSegment = ""
        for ch in word:
          let candidate = currentSegment & ch
          if currentSegment.len > 0 and
              sk.getTextSize("pixelated", candidate).x > maxTextWidth:
            result.add(currentSegment)
            currentSegment = $ch
          else:
            currentSegment = candidate
        currentLine = currentSegment
        continue

      let candidate =
        if currentLine.len == 0:
          word
        else:
          currentLine & " " & word
      if currentLine.len > 0 and
          sk.getTextSize("pixelated", candidate).x > maxTextWidth:
        result.add(currentLine)
        currentLine = word
      else:
        currentLine = candidate

    if currentLine.len > 0:
      result.add(currentLine)
    if result.len == 0:
      result.add("")
    return result

  let
    zoomScale = zoomInfo.zoom * zoomInfo.zoom
    lineHeight = sk.getTextSize("pixelated", "Ag").y + 6.0'f
    maxBubbleWidth = max(
      TalkBubbleMinWidth,
      min(
        TalkBubblePreferredMaxWidth,
        zoomInfo.rect.w.float32 - TalkBubbleMargin * 2.0'f
      )
    )
    minTextWidth = max(
      120.0'f,
      TalkBubbleMinWidth - TalkBubblePadding.x * 2.0'f
    )
    maxTextWidth = max(
      minTextWidth,
      maxBubbleWidth - TalkBubblePadding.x * 2.0'f
    )
    maxBubbleHeight = max(
      TalkBubblePadding.y * 2.0'f + lineHeight,
      zoomInfo.rect.h.float32 - TalkBubbleMargin * 2.0'f
    )
    cooldownSteps = max(1, replay.config.game.talk.cooldownSteps)
    fadeSteps = max(1, cooldownSteps div 4)
    fadeAlpha =
      if remainingSteps >= fadeSteps:
        1.0'f
      else:
        0.25'f +
          0.75'f * remainingSteps.float32 / fadeSteps.float32
    fadeByte = uint8(round(255.0 * fadeAlpha.float64))
    fillByte = uint8(round(236.0 * fadeAlpha.float64))

  var
    wrapWidth = minTextWidth
    wrappedLines: seq[string] = @[]
    bubbleWidth = TalkBubbleMinWidth
    bubbleHeight = maxBubbleHeight
    bestPenalty = high(float32)
    foundFittingLayout = false

  while true:
    let candidateLines = wrapTalkBubbleLines(talkText, wrapWidth)
    var candidateTextWidth = 0.0'f
    for line in candidateLines:
      candidateTextWidth =
        max(candidateTextWidth, sk.getTextSize("pixelated", line).x)

    let
      candidateBubbleWidth = clamp(
        candidateTextWidth + TalkBubblePadding.x * 2.0'f,
        TalkBubbleMinWidth,
        maxBubbleWidth
      )
      candidateBubbleHeight =
        TalkBubblePadding.y * 2.0'f +
        lineHeight * candidateLines.len.float32
      candidateFits = candidateBubbleHeight <= maxBubbleHeight
      candidatePenalty =
        max(candidateBubbleWidth, max(1.0'f, candidateBubbleHeight)) /
        max(1.0'f, candidateBubbleHeight) - 1.0'f
      shouldUseCandidate =
        if not candidateFits:
          not foundFittingLayout and wrapWidth >= maxTextWidth
        elif not foundFittingLayout:
          true
        elif candidatePenalty < bestPenalty - 0.001'f:
          true
        elif abs(candidatePenalty - bestPenalty) <= 0.001'f:
          candidateBubbleWidth * candidateBubbleHeight <
            bubbleWidth * bubbleHeight
        else:
          false

    if shouldUseCandidate:
      wrappedLines = candidateLines
      bubbleWidth = candidateBubbleWidth
      bubbleHeight = min(candidateBubbleHeight, maxBubbleHeight)
      bestPenalty = candidatePenalty
      if candidateFits:
        foundFittingLayout = true

    if wrapWidth >= maxTextWidth:
      break
    wrapWidth = min(maxTextWidth, wrapWidth + TalkBubbleWidthStep)

  var bubblePos =
    zoomInfo.rect.xy.vec2 +
    zoomInfo.pos +
    (smoothPos(agent) + vec2(0, -TalkBubbleLiftTiles)) * zoomScale +
    TalkBubbleOffset -
    vec2(bubbleWidth * 0.5'f, bubbleHeight)

  bubblePos.x = clamp(
    bubblePos.x,
    zoomInfo.rect.x.float32 + TalkBubbleMargin,
    zoomInfo.rect.x.float32 +
      zoomInfo.rect.w.float32 -
      bubbleWidth -
      TalkBubbleMargin
  )
  bubblePos.y = max(
    zoomInfo.rect.y.float32 + TalkBubbleMargin,
    bubblePos.y
  )

  sk.draw9Patch(
    "tooltip.9patch",
    4,
    bubblePos,
    vec2(bubbleWidth, bubbleHeight),
    rgbx(248'u8, 250'u8, 255'u8, fillByte)
  )
  for i in 0 ..< wrappedLines.len:
    discard sk.drawText(
      "pixelated",
      wrappedLines[i],
      bubblePos + vec2(TalkBubblePadding.x, TalkBubblePadding.y +
        lineHeight * i.float32),
      rgbx(Cloud.r, Cloud.g, Cloud.b, fadeByte)
    )

proc drawTalkBubbles*(zoomInfo: ZoomInfo) {.measure.} =
  ## Draw speech bubbles above agents with active talk.
  if replay.isNil or
      not replay.config.game.talk.enabled or
      zoomInfo.zoom < 4.25f: # Show at a less zoomed-out level.
    return

  for agent in replay.agents:
    if not agent.alive.at:
      continue
    drawTalkBubble(agent, zoomInfo)
