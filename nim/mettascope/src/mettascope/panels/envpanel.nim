import
  std/json,
  boxy, silky, windy,
  ../common, ../replays

proc drawEnvironmentInfo*(panel: Panel, frameId: string, contentPos: Vec2, contentSize: Vec2) =
  frame(frameId, contentPos, contentSize):
    text("Environment Info")
    button("Open Config"):
      let text =
        if replay.isNil or replay.mgConfig.isNil:
          "No replay config found."
        else:
          replay.mgConfig.pretty
      openTempTextFile("mg_config.json", text)
