import
  std/strformat,
  vmath, silky,
  ../common, ../replays

proc drawScorePanel*(panel: Panel, frameId: string, contentPos: Vec2, contentSize: Vec2) =
  ## Draws the score panel showing score and junction count.
  frame(frameId, contentPos, contentSize):
    if replay.isNil:
      text("No replay loaded")
      return

    var totalScore = 0.0
    var agentCount = 0
    for obj in replay.objects:
      if obj.isAgent:
        totalScore += obj.totalReward.at
        agentCount += 1

    var junctionCount = 0
    for obj in replay.objects:
      if normalizeTypeName(obj.typeName) == "junction":
        junctionCount += 1

    let avgScore = if agentCount > 0: totalScore / agentCount.float else: 0.0
    let label = &"Score {avgScore:.2f}  Junctions {junctionCount}"

    sk.advance(vec2(0, 8))
    h1text(label)
