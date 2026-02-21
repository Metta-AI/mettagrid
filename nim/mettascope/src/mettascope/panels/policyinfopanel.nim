## Policy Info panel displays policy_infos metadata for the selected agent.

import
  std/[json, strformat, strutils, options],
  vmath, silky, windy,
  ../common, ../replays

proc parseRelativeTarget(value: JsonNode): Option[IVec2] =
  ## Parse a relative target offset from JSON.
  ##
  ## Expects either [row, col] or "row,col". Returns IVec2 with col=x, row=y.
  if value.kind == JArray and value.len == 2:
    try:
      let
        row = value[0].getInt
        col = value[1].getInt
      return some(ivec2(col.int32, row.int32))
    except:
      return none(IVec2)
  elif value.kind == JString:
    let parts = value.getStr.split(',')
    if parts.len == 2:
      try:
        let
          row = parseInt(parts[0].strip)
          col = parseInt(parts[1].strip)
        return some(ivec2(col.int32, row.int32))
      except:
        return none(IVec2)

  return none(IVec2)

proc formatPolicyValue(value: JsonNode): string =
  ## Format a policy info value into a readable string for UI display.
  case value.kind
  of JString:
    value.getStr
  of JInt:
    $value.getInt
  of JFloat:
    &"{value.getFloat:.4f}"
  of JBool:
    $value.getBool
  of JNull:
    "null"
  else:
    $value

proc drawPolicyInfo*(panel: Panel, frameId: string, contentPos: Vec2, contentSize: Vec2) =
  ## Draw the policy info panel for the currently selected agent.
  frame(frameId, contentPos, contentSize):
    policyTarget = none(IVec2)

    if selected.isNil:
      text("No selected")
      return

    if replay.isNil:
      text("Replay not loaded")
      return

    if not selected.isAgent:
      text("Select an agent")
      return

    let policyInfo = selected.policyInfos.at()
    if policyInfo.isNil or policyInfo.kind != JObject or policyInfo.len == 0:
      text("No policy info")
      return

    let agentPos = selected.location.at(step)

    for key, value in policyInfo.pairs:
      if key == "target":
        let relOpt = parseRelativeTarget(value)
        if relOpt.isSome:
          let
            rel = relOpt.get
            abs = ivec2(agentPos.x + rel.x, agentPos.y + rel.y)
          policyTarget = some(abs)
          text(&"{key}: [{rel.y}, {rel.x}] -> [{abs.y}, {abs.x}]")
        else:
          policyTarget = none(IVec2)
          text(&"{key}: {value}")
        continue

      text(&"{key}: {formatPolicyValue(value)}")
