import
  std/json,
  mettascope/[common, replays]

proc makeReplayJson(objectsJson: string, maxSteps: int = 10): string =
  """{"version":4,"num_agents":0,"max_steps":""" & $maxSteps &
  ""","map_size":[10,10],"action_names":["noop"],"item_names":["ore"],"type_names":["agent"],"objects":""" &
  objectsJson & """}"""

block policy_infos_static_replay:
  let json = makeReplayJson(
    """[{"id":1,"agent_id":0,"type_name":"agent","location":[1,1],"orientation":0,"inventory":[],"inventory_max":0,"color":0,"policy_infos":[[0,{"goal":"ExploreHub","policy_name":"policy_0"}],[3,{"goal":"MineResource","policy_name":"policy_0"}]]}]""",
    maxSteps = 5
  )
  let replay = loadReplayString(json, "test.json")
  doAssert replay.objects.len == 1
  doAssert replay.objects[0].policyInfos.at(0)["goal"].getStr == "ExploreHub"
  doAssert replay.objects[0].policyInfos.at(2)["goal"].getStr == "ExploreHub"
  doAssert replay.objects[0].policyInfos.at(3)["goal"].getStr == "MineResource"
  doAssert replay.objects[0].policyInfos.at(4)["policy_name"].getStr == "policy_0"
  echo "✓ policy_infos load from top-level static replay objects"
