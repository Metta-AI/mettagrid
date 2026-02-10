import
  std/[os, strformat],
  benchy,
  ../src/mettascope/[heatmap, replays]

const DefaultReplayPath = currentSourcePath().parentDir / "data/replays/42c5386e-1ec2-4255-b81f-736f7fff5f3f.json.z"

proc getReplayPath(): string =
  ## Use first CLI arg if provided, otherwise use the default benchmark replay.
  if paramCount() >= 1:
    return paramStr(1)
  return DefaultReplayPath

let replayPath = getReplayPath()
if not fileExists(replayPath):
  quit &"Replay file not found: {replayPath}"

let benchReplay = loadReplay(replayPath)
if benchReplay.maxSteps <= 0:
  quit &"Replay failed to load or has no steps: {replayPath}"

echo &"Replay: {replayPath}"
echo &"Map size: {benchReplay.mapSize[0]}x{benchReplay.mapSize[1]}, steps: {benchReplay.maxSteps}, agents: {benchReplay.numAgents}"

timeIt "heatmap generate (newHeatmap + initialize)":
  let hm = newHeatmap(benchReplay)
  hm.initialize(benchReplay)
  doAssert hm.width == benchReplay.mapSize[0]
  doAssert hm.height == benchReplay.mapSize[1]
  doAssert hm.maxSteps == benchReplay.maxSteps
