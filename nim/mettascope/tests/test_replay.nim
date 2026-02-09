import
  std/[json, os, osproc, strformat, strutils, times],
  zippy,
  mettascope/[validation, replays, common]

proc loadReplay(path: string): JsonNode =
  ## Load and decompress a .json.z replay file.
  if not (path.endsWith(".json.gz") or path.endsWith(".json.z")):
    raise newException(ValueError, "Replay file name must end with '.json.gz' or '.json.z'")

  let compressedData = readFile(path)
  var decompressed: string
  try:
    decompressed = zippy.uncompress(compressedData)
  except:
    raise newException(ValueError, "Failed to decompress replay file")

  try:
    result = parseJson(decompressed)
  except:
    raise newException(ValueError, "Invalid JSON in replay file")

block generated_replay_test:
  # Generate a replay using the CI setup and validate it against the strict schema.

  # Create temporary directory.
  let tmpDir = getTempDir() / "metta_replay_test_" & $getTime().toUnix()
  createDir(tmpDir)
  defer: removeDir(tmpDir)

  # Generate a replay using the CI configuration.
  let projectRoot = parentDir(parentDir(parentDir(parentDir(parentDir(parentDir(currentSourcePath()))))))
  let cmd = &"cd {projectRoot} && uv run --no-sync tools/run.py ci.replay_null replay_dir={tmpDir}"
  echo &"Running replay generation: {cmd}"

  let exitCode = execCmd(cmd)
  if exitCode != 0:
    raise newException(AssertionError, &"Replay generation failed with exit code {exitCode}")

  # Find generated replay files.
  var replayFiles: seq[string]
  for file in walkDirRec(tmpDir):
    if file.endsWith(".json.gz") or file.endsWith(".json.z"):
      replayFiles.add(file)

  if replayFiles.len == 0:
    raise newException(AssertionError, &"No replay files were generated in {tmpDir}")

  # Should have exactly one replay file.
  if replayFiles.len != 1:
    raise newException(AssertionError, &"Expected exactly 1 replay file, found {replayFiles.len}: {replayFiles}")

  # Validate the replay file.
  let replayPath = replayFiles[0]
  let loadedReplay = loadReplay(replayPath)
  let issues = validateReplay(loadedReplay)
  if issues.len > 0:
    issues.prettyPrint()
    raise newException(AssertionError, &"Validation issues found in replay")

  echo &"✓ Successfully generated and validated replay: {extractFilename(replayPath)}"

  # Verify alive field is present on objects in the generated replay.
  let objects = loadedReplay["objects"]
  var aliveCount = 0
  for obj in objects.getElems():
    if "alive" in obj:
      aliveCount += 1
  echo &"  Objects with alive field: {aliveCount}/{objects.len}"
  doAssert aliveCount > 0, "Expected at least one object with alive field"

block alive_field_unit_tests:
  ## Unit tests for alive field handling in the replay loader.

  # Helper to build a minimal valid replay JSON string.
  proc makeReplayJson(objectsJson: string, maxSteps: int = 10): string =
    """{"version":4,"num_agents":0,"max_steps":""" & $maxSteps &
    ""","map_size":[10,10],"action_names":["noop"],"item_names":["ore"],"type_names":["wall","extractor"],"objects":""" &
    objectsJson & """}"""

  # Test 1: Object always alive (bare true).
  block alive_constant_true:
    let json = makeReplayJson("""[{"id":1,"alive":true,"type_name":"extractor","location":[1,1],"orientation":0,"inventory":[],"inventory_max":0,"color":0}]""")
    let r = loadReplayString(json, "test.json")
    doAssert r.objects.len == 1
    doAssert r.objects[0].alive.len >= 1
    # All steps should be alive.
    for s in 0 ..< r.maxSteps:
      doAssert r.objects[0].alive.at(s) == true, &"Expected alive at step {s}"
    echo "  ✓ alive constant true"

  # Test 2: Object starts alive, dies at step 5.
  block alive_dies_midway:
    let json = makeReplayJson("""[{"id":1,"alive":[[0,true],[5,false]],"type_name":"extractor","location":[1,1],"orientation":0,"inventory":[],"inventory_max":0,"color":0}]""")
    let r = loadReplayString(json, "test.json")
    doAssert r.objects[0].alive.at(0) == true
    doAssert r.objects[0].alive.at(4) == true
    doAssert r.objects[0].alive.at(5) == false
    doAssert r.objects[0].alive.at(9) == false
    echo "  ✓ alive dies at step 5"

  # Test 3: Object starts dead, becomes alive at step 3.
  block alive_spawns_later:
    let json = makeReplayJson("""[{"id":1,"alive":[[0,false],[3,true]],"type_name":"extractor","location":[1,1],"orientation":0,"inventory":[],"inventory_max":0,"color":0}]""")
    let r = loadReplayString(json, "test.json")
    doAssert r.objects[0].alive.at(0) == false
    doAssert r.objects[0].alive.at(2) == false
    doAssert r.objects[0].alive.at(3) == true
    doAssert r.objects[0].alive.at(9) == true
    echo "  ✓ alive spawns at step 3"

  # Test 4: Object dies and comes back (oscillating).
  block alive_oscillating:
    let json = makeReplayJson("""[{"id":1,"alive":[[0,true],[3,false],[7,true]],"type_name":"extractor","location":[1,1],"orientation":0,"inventory":[],"inventory_max":0,"color":0}]""")
    let r = loadReplayString(json, "test.json")
    doAssert r.objects[0].alive.at(0) == true
    doAssert r.objects[0].alive.at(2) == true
    doAssert r.objects[0].alive.at(3) == false
    doAssert r.objects[0].alive.at(6) == false
    doAssert r.objects[0].alive.at(7) == true
    doAssert r.objects[0].alive.at(9) == true
    echo "  ✓ alive oscillating (dies and revives)"

  # Test 5: Missing alive field defaults to true.
  block alive_missing_defaults_true:
    let json = makeReplayJson("""[{"id":1,"type_name":"extractor","location":[1,1],"orientation":0,"inventory":[],"inventory_max":0,"color":0}]""")
    let r = loadReplayString(json, "test.json")
    doAssert r.objects[0].alive.at(0) == true
    doAssert r.objects[0].alive.at(9) == true
    echo "  ✓ alive missing defaults to true"

  # Test 6: Validation accepts alive field.
  block alive_validation:
    let json = parseJson(makeReplayJson("""[{"id":1,"alive":[[0,true],[5,false]],"type_name":"extractor","location":[1,1],"orientation":0,"inventory":[],"inventory_max":0,"color":0}]"""))
    let issues = validateReplay(json)
    for issue in issues:
      doAssert "alive" notin issue.field, &"Unexpected alive validation issue: {issue.message}"
    echo "  ✓ alive validation passes"

  echo "✓ All alive field unit tests passed"
