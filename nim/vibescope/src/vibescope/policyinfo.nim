## Policy Info panel displays policy_infos metadata for the selected agent.

import
  std/[json, strformat, strutils, options],
  vmath, silky,
  common, panels, replays

proc parseRelativeTarget(value: JsonNode): Option[IVec2] =
  ## Parse a relative target offset from JSON. Expects [row, col] array or "row,col" string.
  ## Returns the offset as IVec2 (col=x, row=y).
  if value.kind == JArray and value.len == 2:
    try:
      let row = value[0].getInt
      let col = value[1].getInt
      return some(ivec2(col.int32, row.int32))  # col=x, row=y
    except:
      return none(IVec2)
  elif value.kind == JString:
    # Parse string format "row,col"
    let parts = value.getStr.split(',')
    if parts.len == 2:
      try:
        let row = parseInt(parts[0].strip)
        let col = parseInt(parts[1].strip)
        return some(ivec2(col.int32, row.int32))  # col=x, row=y
      except:
        return none(IVec2)
  return none(IVec2)

proc drawPolicyInfo*(panel: panels.Panel, frameId: string, contentPos: Vec2, contentSize: Vec2) =
  frame(frameId, contentPos, contentSize):
    # Clear policy target at start of each draw
    policyTarget = none(IVec2)

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

    # Get agent's current position for absolute coordinate calculation
    let agentPos = selection.location.at(step)

    for key, value in policyInfo.pairs:
      # Parse target and store in shared state
      if key == "target":
        let relOpt = parseRelativeTarget(value)
        # Display target with both relative and absolute coordinates
        if relOpt.isSome:
          let rel = relOpt.get  # Parsed value is relative offset
          let abs = ivec2(agentPos.x + rel.x, agentPos.y + rel.y)  # Calculate absolute
          policyTarget = some(abs)  # Store absolute position for map drawing
          text(&"{key}: [{rel.y}, {rel.x}] -> [{abs.y}, {abs.x}]")  # Display as [row, col]
        else:
          policyTarget = none(IVec2)
          text(&"{key}: {value}")
        continue

      let valueStr = case value.kind
        of JString: value.getStr
        of JInt: $value.getInt
        of JFloat: formatFloat(value.getFloat, ffDecimal, 4)
        of JBool: $value.getBool
        of JNull: "null"
        else: $value
      text(&"{key}: {valueStr}")
