import
  std/strformat,
  vmath, silky, windy,
  ../common, ../replays, ../collectives

proc drawScorePanel*(panel: Panel, frameId: string, contentPos: Vec2, contentSize: Vec2) =
  ## Draws the score panel showing score and junction count for the active faction.
  frame(frameId, contentPos, contentSize):
    if replay.isNil:
      text("No replay loaded")
      return

    let cid = activeCollective

    # Compute average total reward for agents in the active faction.
    var totalScore = 0.0
    var agentCount = 0
    for obj in replay.objects:
      if obj.isAgent and obj.collectiveId.at(step) == cid:
        totalScore += obj.totalReward.at
        agentCount += 1

    # Count junctions held by the active faction.
    var junctionCount = 0
    for obj in replay.objects:
      if normalizeTypeName(obj.typeName) == "junction" and obj.collectiveId.at(step) == cid:
        junctionCount += 1

    let avgScore = if agentCount > 0: totalScore / agentCount.float else: 0.0
    let name = getCollectiveName(cid)
    let label = &"{name}  Score {avgScore:.2f}  Junctions {junctionCount}"

    sk.advance(vec2(0, 8))
    h1text(label)
