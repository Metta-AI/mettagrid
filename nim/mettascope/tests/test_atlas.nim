import
  std/os,
  silky,
  ../src/mettascope/atlas

let testDataDir = currentSourcePath().parentDir() / ".." / "data"
setDataDir(testDataDir)

block test_silky_atlas:
  echo "Testing shared silky atlas generation"
  let builder = buildSilkyAtlas()
  doAssert builder.atlas.entries.len > 0, "Silky atlas should have entries"
  doAssert "ui/help" in builder.atlas.entries, "Silky atlas should contain ui/help"
  doAssert "vibe/black-circle" in builder.atlas.entries, "Silky atlas should contain vibe/black-circle"
  doAssert "resources/ore_blue" in builder.atlas.entries, "Silky atlas should contain resources/ore_blue"
  doAssert "agents/tracks.ss" in builder.atlas.entries, "Silky atlas should contain agents/tracks.ss"
  doAssert "objects/selection" in builder.atlas.entries, "Silky atlas should contain objects/selection"
  doAssert "objects/altar" in builder.atlas.entries, "Silky atlas should contain objects/altar"
  doAssert "minimap/agent" in builder.atlas.entries, "Silky atlas should contain minimap/agent"
  doAssert "minimap/hub" in builder.atlas.entries, "Silky atlas should contain minimap/hub"
  doAssert "minimap/unknown" in builder.atlas.entries, "Silky atlas should contain minimap/unknown"
  if dirExists(testDataDir / "amongus"):
    doAssert "objects/crew_station" in builder.atlas.entries
    doAssert "amongus/terrain/stamp.among_us_wiring" in builder.atlas.entries
  echo "Shared silky atlas test passed"
