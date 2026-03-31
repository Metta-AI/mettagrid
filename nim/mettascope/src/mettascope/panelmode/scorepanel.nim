import
  std/[strformat, strutils, tables, algorithm],
  vmath, silky, chroma,
  ../common, ../replays, ../gamemode/team,
  widgets

proc drawScorePanel*(panel: Panel, frameId: string, contentPos: Vec2, contentSize: Vec2) =
  ## Draws the score panel showing per-team stats.
  frame(frameId, contentPos, contentSize):
    if replay.isNil:
      text("No replay loaded")
      return

    let numTeams = getNumTeams()
    if numTeams == 0:
      var totalScore = 0.0
      var agentCount = 0
      for obj in replay.objects:
        if obj.isAgent:
          totalScore += obj.totalReward.at
          agentCount += 1
      let avgScore = if agentCount > 0: totalScore / agentCount.float else: 0.0
      h1text(&"Score {avgScore:.2f}")
      return

    for teamIdx in 0 ..< numTeams:
      let teamName = getTeamName(teamIdx)
      let color = getTeamColor(teamIdx)
      let tint = rgbx(color.r, color.g, color.b, 255)
      discard sk.drawText(sk.textStyle, teamName.toUpperAscii, sk.at, tint)
      sk.advance(vec2(0, sk.theme.spacing.float32 + 16))

      var totalReward = 0.0
      var agentCount = 0
      var agentsByRig = initTable[string, int]()
      var buildingsByType = initTable[string, int]()

      for obj in replay.objects:
        if getEntityTeamIndex(obj) != teamIdx:
          continue
        if obj.isAgent:
          if not obj.alive.at:
            continue
          totalReward += obj.totalReward.at
          agentCount += 1
          let rig = getAgentRigName(obj)
          agentsByRig.mgetOrPut(rig, 0) += 1
        else:
          if not obj.alive.at:
            continue
          let typeName = normalizeTypeName(obj.typeName)
          if typeName == "wall":
            continue
          buildingsByType.mgetOrPut(typeName, 0) += 1

      let avgScore = if agentCount > 0: totalReward / agentCount.float else: 0.0
      text(&"  Score: {avgScore:.2f} ({agentCount} agents)")

      if buildingsByType.len > 0:
        var sorted: seq[(string, int)] = @[]
        for k, v in buildingsByType: sorted.add((k, v))
        sorted.sort(proc(a, b: (string, int)): int = cmp(b[1], a[1]))
        for (name, count) in sorted:
          smallIconLabel("icons/objects/" & name, &"{name}: {count}")

      if agentsByRig.len > 0:
        var sorted: seq[(string, int)] = @[]
        for k, v in agentsByRig: sorted.add((k, v))
        sorted.sort(proc(a, b: (string, int)): int = cmp(b[1], a[1]))
        for (name, count) in sorted:
          text(&"  {name}: {count}")

      sk.advance(vec2(0, sk.theme.spacing.float32 * 2))
