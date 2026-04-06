import
  std/[algorithm, strformat],
  silky, windy,
  ../[common, replays, talk]

const
  TalkComposeGap = 28.0'f

type
  TalkEntry* = object
    step*: int
    speakerId*: int
    message*: string

proc collectVisibleTalkEntries*(observer: Entity): seq[TalkEntry] =
  ## Return the visible talk history for one observer.
  if observer.isNil or replay.isNil or not observer.isAgent:
    return @[]

  let finalStep = max(0, step)

  proc canSee(
    speaker: Entity,
    atStep: int
  ): bool =
    ## Return true when the observer could see the speaker at one step.
    if observer.visionSize <= 0 or
        not observer.alive.at(atStep) or
        not speaker.alive.at(atStep):
      return false

    let
      observerPos = observer.location.at(atStep).xy
      speakerPos = speaker.location.at(atStep).xy
      dx = int(speakerPos.x - observerPos.x)
      dy = int(speakerPos.y - observerPos.y)
      visionRadius = observer.visionSize div 2
      visionRadiusSq = visionRadius * visionRadius
      distSq = dx * dx + dy * dy
    return distSq <= visionRadiusSq or
      (visionRadius >= 2 and distSq == visionRadiusSq + 1 and
      (abs(dx) == visionRadius or abs(dy) == visionRadius))

  proc collectSpeakerTalk(speaker: Entity): seq[TalkEntry] =
    ## Return the visible talk history contributed by one speaker.
    var
      previousTalkText = ""
      previousRemainingSteps = 0
      utteranceId = 0
      loggedUtteranceId = 0

    for historyStep in 0 .. finalStep:
      let
        talkText = speaker.talkText.at(historyStep).strip()
        remainingSteps = max(0, speaker.talkRemainingSteps.at(historyStep))
        talkActive = talkText.len > 0 and remainingSteps > 0
      if talkActive and
          (previousRemainingSteps <= 0 or
          previousTalkText != talkText or
          remainingSteps > previousRemainingSteps):
        inc utteranceId

      if talkActive and utteranceId > loggedUtteranceId and
          canSee(speaker, historyStep):
        result.add(TalkEntry(
          step: historyStep,
          speakerId: speaker.agentId,
          message: talkText
        ))
        loggedUtteranceId = utteranceId

      previousTalkText = talkText
      previousRemainingSteps = remainingSteps

  for speaker in replay.agents:
    result.add(collectSpeakerTalk(speaker))

  result.sort(proc(a, b: TalkEntry): int =
    result = cmp(a.step, b.step)
    if result == 0:
      result = cmp(a.speakerId, b.speakerId)
  )

proc drawTalkPanel*(panel: Panel, frameId: string, contentPos: Vec2, contentSize: Vec2) =
  ## Draw talk history and composer controls in the panel area.
  frame(frameId, contentPos, contentSize):
    if replay.isNil or not replay.config.game.talk.enabled:
      text("Talk disabled for this replay.")
      return

    ensureTalkComposeSelection()

    if selected.isNil or not selected.isAgent:
      text("Select an agent to compose.")
      return

    let agent = selected
    let
      entries = collectVisibleTalkEntries(agent)
      limit = max(1, replay.config.game.talk.maxLength)
      remainingSteps = max(0, agent.talkRemainingSteps.at(step))
      isActive = talkComposeActive and talkComposeAgentId == agent.agentId
      composeLabel =
        if remainingSteps > 0:
          &"Compose (Cooldown: {remainingSteps})"
        else:
          "Compose"

    text("Chat History")

    if entries.len == 0:
      text("No visible talk yet.")
    else:
      for entry in entries:
        let
          line = &"[{entry.step}] COG {entry.speakerId}: {entry.message}"
          linePos = sk.at
          lineHeight = max(
            sk.atlas.fonts[sk.textStyle].lineHeight.float32,
            sk.drawText(
              sk.textStyle,
              line,
              linePos,
              sk.theme.defaultTextColor,
              maxWidth = max(0.0'f, sk.size.x),
              wordWrap = true
            ).y
          )
        sk.at.y = linePos.y + lineHeight + sk.theme.spacing.float32

    sk.advance(vec2(0.0'f, TalkComposeGap))
    text(composeLabel)

    if isActive:
      let inputId = "panelTalkCompose." & $talkComposeInputId
      textInput(inputId, talkComposeText)
      syncTalkComposeInput(inputId, limit)
      let canSend = remainingSteps == 0 and talkComposeText.strip.len > 0
      text("Enter sends.")
      text(&"{max(0, limit - talkComposeText.len)} chars left")
      button("Send Talk"):
        if canSend:
          submitTalkCompose()
      button("Cancel"):
        clearTalkCompose()
      return

    if remainingSteps == 0:
      text("Press Enter or click Compose.")
    button("Compose Talk"):
      beginTalkComposeForSelected()
