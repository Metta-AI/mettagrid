import
  std/[os, strformat],
  benchy,
  ../src/mettascope/[replays, common],
  ../src/mettascope/gamemode/pipegrid

const DefaultReplayPath = currentSourcePath().parentDir.parentDir / "data/replays/default.json.z"

proc getReplayPath(): string =
  ## Use first CLI arg if provided, otherwise use the default benchmark replay.
  if paramCount() >= 1:
    return paramStr(1)
  return DefaultReplayPath

let replayPath = getReplayPath()
if not fileExists(replayPath):
  quit &"Replay file not found: {replayPath}"

replay = loadReplay(replayPath)
if replay.maxSteps <= 0:
  quit &"Replay failed to load or has no steps: {replayPath}"

echo &"Replay: {replayPath}"
echo &"Map size: {replay.mapSize[0]}x{replay.mapSize[1]}, steps: {replay.maxSteps}, agents: {replay.numAgents}, objects: {replay.objects.len}"

timeIt "pipegrid full forward pass":
  resetPipegridState()
  for i in 0 ..< replay.maxSteps:
    step = i
    updatePipegridState()
