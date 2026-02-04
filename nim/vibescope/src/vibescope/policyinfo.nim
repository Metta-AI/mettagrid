## Policy Info panel displays policy_infos metadata for the selected agent.

import
  std/[json, strformat, strutils],
  vmath, silky,
  common, panels, replays

proc drawPolicyInfo*(panel: panels.Panel, frameId: string, contentPos: Vec2, contentSize: Vec2) =
  frame(frameId, contentPos, contentSize):
    if selection.isNil:
      text("No selection")
      return

    if replay.isNil:
      text("Replay not loaded")
      return

    if not selection.isAgent:
      text("Select an agent")
      return

    let policyInfo = selection.policyInfos.at()
    if policyInfo.isNil or policyInfo.kind != JObject or policyInfo.len == 0:
      text("No policy info")
      return

    for key, value in policyInfo.pairs:
      let valueStr = case value.kind
        of JString: value.getStr
        of JInt: $value.getInt
        of JFloat: formatFloat(value.getFloat, ffDecimal, 4)
        of JBool: $value.getBool
        of JNull: "null"
        else: $value
      text(&"{key}: {valueStr}")
