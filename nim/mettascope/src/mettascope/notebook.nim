import
  std/[strutils],
  replays, common, replayloader

when defined(emscripten):
  {.emit: """
  #include <emscripten.h>
  """.}

  {.emit: """
  EM_JS(void, setup_postmessage_replay_handler_internal, (void* userData), {
    function isValidOrigin(origin) {
      if (origin.includes('colab') && origin.includes('googleusercontent.com')) {
        return true;
      }
      if (origin.startsWith('http://localhost:') || origin.startsWith('https://localhost:')
        || origin.startsWith('http://127.0.0.1:') || origin.startsWith('https://127.0.0.1:')) {
        return true;
      }
      return false;
    }

    window.parent.postMessage({ type: 'mettascopeReady' }, '*');

    window.addEventListener('message', function(event) {
      if (!isValidOrigin(event.origin) || !event.data) {
        return;
      }

      // Step-control API: allow the parent to seek to a specific replay step.
      if (event.data.type === 'mettascopeSetStep' && typeof event.data.step === 'number') {
        Module._mettascope_set_step(event.data.step | 0);
        if (typeof event.data.agent === 'number') {
          Module._mettascope_select_agent(event.data.agent | 0);
        }
        return;
      }
      if (event.data.type === 'mettascopeSelectAgent' && typeof event.data.agent === 'number') {
        Module._mettascope_select_agent(event.data.agent | 0);
        return;
      }

      if (event.data.type !== 'replayData') {
        return;
      }

      const base64Data = event.data.base64;
      if (!base64Data || typeof base64Data !== 'string') {
        return;
      }

      try {
        const binaryString = atob(base64Data);
        const binaryLength = binaryString.length;
        const binaryPtr = _malloc(binaryLength);
        if (!binaryPtr) return;

        for (let i = 0; i < binaryLength; i++) {
          HEAPU8[binaryPtr + i] = binaryString.charCodeAt(i);
        }

        const fileName = event.data.fileName || 'replay_from_notebook.json.z';
        const fileNameLen = lengthBytesUTF8(fileName) + 1;
        const fileNamePtr = _malloc(fileNameLen);
        stringToUTF8(fileName, fileNamePtr, fileNameLen);

        Module._mettascope_postmessage_replay_callback(userData, fileNamePtr, binaryPtr, binaryLength);

        _free(fileNamePtr);
        _free(binaryPtr);
      } catch (error) {
        console.error('Error processing postMessage replay data:', error);
      }
    });
  });
  """.}

  proc setup_postmessage_replay_handler_internal*(userData: pointer) {.importc.}

  {.emit: """
  EM_JS(void, mettascope_emit_step_to_parent_internal, (int step), {
    if (typeof window !== 'undefined' && window.parent) {
      window.parent.postMessage({ type: 'mettascopeStep', step: step }, '*');
    }
  });
  """.}

  proc mettascope_emit_step_to_parent_internal(step: cint) {.importc.}

  {.emit: """
  EM_JS(void, mettascope_emit_agent_to_parent_internal, (int agent), {
    if (typeof window !== 'undefined' && window.parent) {
      window.parent.postMessage(
        { type: 'mettascopeSelectAgent', agent: agent }, '*');
    }
  });
  """.}

  proc mettascope_emit_agent_to_parent_internal(agent: cint) {.importc.}

  proc mettascope_postmessage_replay_callback(userData: pointer, fileNamePtr: cstring, binaryPtr: pointer, binaryLen: cint) {.exportc, cdecl, codegenDecl: "EMSCRIPTEN_KEEPALIVE $# $#$#".} =
    ## Callback to handle postMessage replay data from JavaScript.
    let fileName = $fileNamePtr
    var fileData = newString(binaryLen)
    if binaryLen > 0:
      copyMem(fileData[0].addr, binaryPtr, binaryLen)

    if fileName.endsWith(".json.gz") or fileName.endsWith(".json.z"):
      try:
        common.replay = loadReplay(fileData, fileName)
        onReplayLoaded()
        echo "Loaded replay from postMessage: ", fileName
      except:
        echo "Error loading replay: ", getCurrentExceptionMsg()
        popupWarning = "Failed to load replay from notebook.\n" & getCurrentExceptionMsg()

  proc setupPostMessageReplayHandler*(userData: pointer) =
    ## Set up postMessage handler for receiving replay data.
    when defined(emscripten):
      setup_postmessage_replay_handler_internal(userData)

  proc mettascope_set_step(newStep: cint) {.exportc, cdecl,
      codegenDecl: "EMSCRIPTEN_KEEPALIVE $# $#$#".} =
    ## Jump the replay to a specific step (inbound postMessage API).
    if common.replay.isNil or common.replay.maxSteps <= 0:
      return
    let clamped = max(0, min(newStep.int, common.replay.maxSteps - 1))
    common.step = clamped
    common.stepFloat = clamped.float32
    common.forceWarp = true

  proc mettascope_select_agent(agentId: cint) {.exportc, cdecl,
      codegenDecl: "EMSCRIPTEN_KEEPALIVE $# $#$#".} =
    ## Select an agent by index.
    if common.replay.isNil:
      return
    let id = agentId.int
    if id < 0 or id >= common.replay.agents.len:
      return
    common.selected = common.replay.agents[id]

  var lastEmittedStep {.global.} = -1

  proc emitStepToParent*() =
    ## Emit outbound postMessage when the replay step changes.
    if common.step == lastEmittedStep:
      return
    lastEmittedStep = common.step
    mettascope_emit_step_to_parent_internal(common.step.cint)

  var lastEmittedAgent {.global.} = -2

  proc emitSelectedAgentToParent*() =
    ## Emit outbound postMessage when the selected agent changes.
    let current =
      if common.selected.isNil or not common.selected.isAgent: -1
      else: common.selected.agentId
    if current == lastEmittedAgent:
      return
    lastEmittedAgent = current
    mettascope_emit_agent_to_parent_internal(current.cint)

else:
  proc emitStepToParent*() =
    discard

  proc emitSelectedAgentToParent*() =
    discard
