import
  vmath,
  mettascope/[actions, common, replays],
  mettascope/gamemode/worldmap

proc setupReplay(): Replay =
  ## Create a replay with the cardinal move action IDs wired for orientation tests.
  replay = Replay(
    version: 4,
    numAgents: 1,
    maxSteps: 3,
    mapSize: (5, 5),
    fileName: "test",
    actionNames: @["noop", "move_north", "move_south", "move_west", "move_east"],
    objects: @[],
    agents: @[],
    moveNorthActionId: 1,
    moveSouthActionId: 2,
    moveWestActionId: 3,
    moveEastActionId: 4,
  )
  result = replay

block action_fallback_tests:
  echo "Testing successful stationary interaction facing persistence."
  discard setupReplay()
  let agent = Entity(
    id: 1,
    typeName: "agent",
    agentId: 0,
    isAgent: true,
    location: @[ivec2(2, 2), ivec2(2, 2), ivec2(2, 2)],
    actionId: @[replay.moveNorthActionId, 0, 0],
    actionSuccess: @[true, true, true],
    animationId: newSeq[int](3),
  )
  doAssert inferOrientation(agent, 0) == N, "Step 0 should face north from the successful interaction."
  doAssert inferOrientation(agent, 2) == N, "Later idle steps should keep the north-facing interaction."
