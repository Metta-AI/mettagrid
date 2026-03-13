## Dialogue panel displays the transcript between low-level runtime logs and the LLM reviewer.

import
  std/[hashes, strutils, tables],
  silky, windy,
  ../common, ../replays

var
  dialogueRenderedAgentByFrame = initTable[string, int]()
  dialogueRenderedSignatureByFrame = initTable[string, Hash]()
  dialogueCachedAgentId = -1
  dialogueCachedStep = -1
  dialogueCachedTranscript = ""
  dialogueCachedTranscriptSignature = Hash(0)
  dialogueCachedLines: seq[string] = @[]

const DialogueLineHeight = 18'f32

proc resetDialogueCaches*() =
  dialogueRenderedAgentByFrame.clear()
  dialogueRenderedSignatureByFrame.clear()
  dialogueCachedAgentId = -1
  dialogueCachedStep = -1
  dialogueCachedTranscript = ""
  dialogueCachedTranscriptSignature = Hash(0)
  dialogueCachedLines = @[]

proc dialogueSignature(transcript: string): Hash =
  hash(transcript)

proc currentDialogueTail(agent: Entity): string =
  if agent.isNil or agent.dialogueAppend.len == 0:
    return ""

  let targetStep = min(step, agent.dialogueAppend.high)
  if agent.agentId == dialogueCachedAgentId and targetStep == dialogueCachedStep:
    return dialogueCachedTranscript

  var
    transcript = ""
    startStep = 0
  if agent.agentId == dialogueCachedAgentId and targetStep > dialogueCachedStep:
    transcript = dialogueCachedTranscript
    startStep = dialogueCachedStep + 1

  if startStep <= targetStep:
    for i in startStep .. targetStep:
      if agent.dialogueReset.at(i):
        transcript.setLen(0)
      let appended = agent.dialogueAppend.at(i)
      if appended.len > 0:
        transcript.add(appended)

  dialogueCachedAgentId = agent.agentId
  dialogueCachedStep = targetStep
  dialogueCachedTranscript = transcript
  result = transcript

proc dialogueLines(transcript: string): seq[string] =
  let signature = dialogueSignature(transcript)
  if signature != dialogueCachedTranscriptSignature:
    dialogueCachedTranscriptSignature = signature
    dialogueCachedLines =
      if transcript.len > 0:
        transcript.splitLines()
      else:
        @[]
  dialogueCachedLines

proc drawDialoguePanel*(panel: Panel, frameId: string, contentPos: Vec2, contentSize: Vec2) =
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

    let transcript = currentDialogueTail(selected)
    if transcript.len == 0:
      text("No dialogue yet")
      return
    let lines = dialogueLines(transcript)
    let
      startY = sk.at.y
      scrollY = max(0'f32, frameStates[frameId].scrollPos.y)
      firstLine = clamp(int(floor(scrollY / DialogueLineHeight)), 0, max(lines.len - 1, 0))
      visibleLineCount = max(1, int(ceil(contentSize.y / DialogueLineHeight)) + 1)
      lastLineExclusive = min(lines.len, firstLine + visibleLineCount)

    sk.at.y = startY + firstLine.float32 * DialogueLineHeight
    for line in lines[firstLine ..< lastLineExclusive]:
      if line.len == 0:
        text(" ")
      else:
        text(line)
    let totalContentHeight = lines.len.float32 * DialogueLineHeight
    if sk.at.y < startY + totalContentHeight:
      sk.at.y = startY + totalContentHeight

    let
      agentId = selected.agentId
      signature = dialogueSignature(transcript)
      previousAgentId = dialogueRenderedAgentByFrame.getOrDefault(frameId, -1)
      previousSignature = dialogueRenderedSignatureByFrame.getOrDefault(frameId, Hash(0))
    if previousAgentId != agentId or previousSignature != signature:
      let estimatedContentHeight = max(0'f32, totalContentHeight)
      frameStates[frameId].scrollPos.y = max(0'f32, estimatedContentHeight - contentSize.y)
    dialogueRenderedAgentByFrame[frameId] = agentId
    dialogueRenderedSignatureByFrame[frameId] = signature
