## Dialogue panel displays the transcript between low-level runtime logs and the LLM reviewer.

import
  std/[hashes, json, strutils, tables],
  silky, windy,
  ../common, ../replays

var
  dialogueRenderedAgentByFrame = initTable[string, int]()
  dialogueRenderedSignatureByFrame = initTable[string, Hash]()

proc jsonStringOrEmpty(node: JsonNode, key: string): string =
  if node.isNil or node.kind != JObject or key notin node or node[key].kind != JString:
    return ""
  node[key].getStr

proc currentDialogueTail(agent: Entity): string =
  jsonStringOrEmpty(agent.policyInfos.at(), "__dialogue_transcript_tail")

proc displayedDialogueLineCount(transcript: string): int =
  var lineCount = 0
  if transcript.len > 0:
    lineCount += transcript.splitLines().len
  lineCount

proc dialogueSignature(transcript: string): Hash =
  hash(transcript)

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

    if transcript.len > 0:
      for line in transcript.splitLines():
        if line.len == 0:
          text(" ")
        else:
          text(line)

    let
      agentId = selected.agentId
      signature = dialogueSignature(transcript)
      previousAgentId = dialogueRenderedAgentByFrame.getOrDefault(frameId, -1)
      previousSignature = dialogueRenderedSignatureByFrame.getOrDefault(frameId, Hash(0))
    if previousAgentId != agentId or previousSignature != signature:
      let
        lineCount = displayedDialogueLineCount(transcript)
        estimatedContentHeight = max(0'f32, lineCount.float32 * 18'f32)
      frameStates[frameId].scrollPos.y = max(0'f32, estimatedContentHeight - contentSize.y)
    dialogueRenderedAgentByFrame[frameId] = agentId
    dialogueRenderedSignatureByFrame[frameId] = signature
