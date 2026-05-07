## WebSocket support for live Emscripten MettaScope builds.
import
  std/json,
  common, replayloader, replays,
  gamemode/worldmap

when defined(emscripten):
  {.emit: """
  #include <emscripten.h>
  """.}

  {.emit: """
  EM_JS(void, mp_connect_ws_internal, (const char* url), {
    var wsUrl = UTF8ToString(url);
    console.log('Connecting to ' + wsUrl);
    window._mpWs = new WebSocket(wsUrl);
    window._mpWs.onopen = function() {
      console.log('WebSocket connected');
    };
    window._mpWs.onmessage = function(e) {
      var data = e.data;
      var len = lengthBytesUTF8(data) + 1;
      var ptr = _malloc(len);
      stringToUTF8(data, ptr, len);
      Module._mp_on_message(ptr, len - 1);
      _free(ptr);
    };
    window._mpWs.onerror = function(e) {
      console.error('WebSocket error', e);
    };
    window._mpWs.onclose = function() {
      console.log('WebSocket closed');
    };
  });
  """}

  {.emit: """
  EM_JS(void, mp_send_ws_internal, (const char* msg), {
    if (window._mpWs && window._mpWs.readyState === 1) {
      window._mpWs.send(UTF8ToString(msg));
    }
  });
  """}

  proc mpConnectWrapper(url: cstring) =
    {.emit: "mp_connect_ws_internal(`url`);".}

  proc mpSendWrapper(msg: cstring) =
    {.emit: "mp_send_ws_internal(`msg`);".}

proc mpConnect*(wsUrl: string) =
  multiplayerActive = true
  playMode = Realtime
  play = false
  replay = EmptyReplay
  when defined(emscripten):
    mpConnectWrapper(wsUrl.cstring)
  else:
    echo "Live WebSocket is only supported in Emscripten builds."

proc mpSend*(msg: string) =
  when defined(emscripten):
    mpSendWrapper(msg.cstring)

proc mpSendControl*(command: string, speed: float32 = 0.0) =
  var msg = "{\"type\":\"control\",\"command\":\"" & command & "\""
  if command == "speed":
    msg.add(",\"speed\":" & $speed)
  msg.add("}")
  mpSend(msg)

var
  lastSentPlay = false
  lastSentSpeed = -1.0'f32

proc mpSyncControls*() =
  if not multiplayerActive:
    return
  if play != lastSentPlay:
    mpSendControl(if play: "play" else: "stop")
    lastSentPlay = play
  if playSpeed != lastSentSpeed:
    mpSendControl("speed", playSpeed)
    lastSentSpeed = playSpeed

proc mpSendActions*() =
  if not multiplayerActive:
    return
  if requestActions.len == 0:
    mpSendControl("step")
    requestPython = false
    return
  for action in requestActions:
    let msg =
      "{\"type\":\"action\",\"agent_id\":" &
      $action.agentId &
      ",\"action_name\":\"" &
      action.actionName & "\"}"
    mpSend(msg)
  if not play:
    mpSendControl("step")
  requestActions.setLen(0)
  requestPython = false

proc selectAssignedAgent() =
  if selected.isNil and multiplayerAgentId >= 0:
    selected = getAgentById(multiplayerAgentId)
    settings.lockFocus = true

proc mpOnAssign(parsed: JsonNode) =
  multiplayerAgentId = parsed["agent_id"].getInt()
  lastSentPlay = play
  lastSentSpeed = playSpeed
  gameMode = Game
  replay = loadReplayString($parsed["initial_replay"], "live")
  onReplayLoaded()
  echo "Assigned agent ", multiplayerAgentId

proc mpOnStep(data: string, parsed: JsonNode) =
  let stepNum = parsed["step"].getInt()
  replay.apply(data)
  step = stepNum
  stepFloat = stepNum.float32
  selectAssignedAgent()

proc mpOnWalls(data: string) =
  replay.apply(data)
  resetTerrainCaches()
  rebuildSplats()

proc mpOnDone() =
  echo "Game over"
  play = false

proc mpOnMessage(data: string) =
  let parsed = parseJson(data)
  case parsed["type"].getStr()
  of "assign":
    mpOnAssign(parsed)
  of "walls":
    mpOnWalls(data)
  of "step":
    mpOnStep(data, parsed)
  of "done":
    mpOnDone()
  else:
    discard

when defined(emscripten):
  proc mp_on_message(msgPtr: cstring, msgLen: cint)
      {.exportc, cdecl,
       codegenDecl:
         "EMSCRIPTEN_KEEPALIVE $# $#$#".} =
    let data = $msgPtr
    if data.len == 0:
      return
    mpOnMessage(data)
