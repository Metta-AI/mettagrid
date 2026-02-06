import
  std/strformat,
  vmath, silky, windy,
  ../common, ../replays

proc drawScorePanel*(panel: Panel, frameId: string, contentPos: Vec2, contentSize: Vec2) =
  ## Draws the score panel showing the average total reward across all agents.
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

    if agentCount == 0:
      text("No agents found")
      return

    let avgScore = totalScore / agentCount.float

    # Display the score prominently in H1 style.
    sk.advance(vec2(0, 8))
    h1text(&"Score: {avgScore:.2f}")
