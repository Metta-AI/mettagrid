## Monologue panel displays the transcript between low-level runtime logs and the LLM reviewer.

import
  std/[hashes, strutils, tables],
  silky, windy,
  ../common, ../replays

var
  monologueRenderedAgentByFrame = initTable[string, int]()
  monologueRenderedSignatureByFrame = initTable[string, Hash]()
  monologueCachedAgentId = -1
  monologueCachedStep = -1
  monologueCachedTranscript = ""
  monologueCachedTranscriptSignature = Hash(0)
  monologueCachedLines: seq[string] = @[]

const MonologueLineHeight = 18'f32

proc resetMonologueCaches*() =
  monologueRenderedAgentByFrame.clear()
  monologueRenderedSignatureByFrame.clear()
  monologueCachedAgentId = -1
  monologueCachedStep = -1
  monologueCachedTranscript = ""
  monologueCachedTranscriptSignature = Hash(0)
  monologueCachedLines = @[]

proc monologueSignature(transcript: string): Hash =
  hash(transcript)

proc currentMonologueTail(agent: Entity): string =
  if agent.isNil or agent.dialogueAppend.len == 0:
    return ""

  let targetStep = min(step, agent.dialogueAppend.high)
  if agent.agentId == monologueCachedAgentId and targetStep == monologueCachedStep:
    return monologueCachedTranscript

  var
    transcript = ""
    startStep = 0
  if agent.agentId == monologueCachedAgentId and targetStep > monologueCachedStep:
    transcript = monologueCachedTranscript
    startStep = monologueCachedStep + 1

  if startStep <= targetStep:
    for i in startStep .. targetStep:
      if agent.dialogueReset.at(i):
        transcript.setLen(0)
      let appended = agent.dialogueAppend.at(i)
      if appended.len > 0:
        transcript.add(appended)

  monologueCachedAgentId = agent.agentId
  monologueCachedStep = targetStep
  monologueCachedTranscript = transcript
  result = transcript

proc monologueLines(transcript: string): seq[string] =
  let signature = monologueSignature(transcript)
  if signature != monologueCachedTranscriptSignature:
    monologueCachedTranscriptSignature = signature
    monologueCachedLines =
      if transcript.len > 0:
        transcript.splitLines()
      else:
        @[]
  monologueCachedLines

proc drawMonologuePanel*(panel: Panel, frameId: string, contentPos: Vec2, contentSize: Vec2) =
  frame(frameId, contentPos, contentSize):
    if selected.isNil:
      text("No selected")
      return

    if replay.isNil:
      text("Replay not loaded")
      return

    if not selected.isAgent:
      text("Select an agent")
      return

    let transcript = currentMonologueTail(selected)
    if transcript.len == 0:
      text("No monologue yet")
      return
    let lines = monologueLines(transcript)
    let
      startY = sk.at.y
      scrollY = max(0'f32, frameStates[frameId].scrollPos.y)
      firstLine = clamp(int(floor(scrollY / MonologueLineHeight)), 0, max(lines.len - 1, 0))
      visibleLineCount = max(1, int(ceil(contentSize.y / MonologueLineHeight)) + 1)
      lastLineExclusive = min(lines.len, firstLine + visibleLineCount)

    sk.at.y = startY + firstLine.float32 * MonologueLineHeight
    for line in lines[firstLine ..< lastLineExclusive]:
      if line.len == 0:
        text(" ")
      else:
        text(line)
    let totalContentHeight = lines.len.float32 * MonologueLineHeight
    if sk.at.y < startY + totalContentHeight:
      sk.at.y = startY + totalContentHeight

    let
      agentId = selected.agentId
      signature = monologueSignature(transcript)
      previousAgentId = monologueRenderedAgentByFrame.getOrDefault(frameId, -1)
      previousSignature = monologueRenderedSignatureByFrame.getOrDefault(frameId, Hash(0))
    if previousAgentId != agentId or previousSignature != signature:
      let estimatedContentHeight = max(0'f32, totalContentHeight)
      frameStates[frameId].scrollPos.y = max(0'f32, estimatedContentHeight - contentSize.y)
    monologueRenderedAgentByFrame[frameId] = agentId
    monologueRenderedSignatureByFrame[frameId] = signature
