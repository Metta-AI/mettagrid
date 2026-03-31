import
  std/os,
  silky,
  ../tools/gen_atlas

let testDataDir = currentSourcePath().parentDir() / ".." / "data"
setDataDir(testDataDir)

block test_silky_atlas:
  echo "Testing shared silky atlas generation"
  let silkyImagePath = "silky.atlas.png"

  buildSilkyAtlas(dataDir / silkyImagePath)

  doAssert fileExists(dataDir / silkyImagePath), "Silky atlas PNG file should be created"

  let atlas = readAtlasFromPng(dataDir / silkyImagePath)
  doAssert atlas.entries.len > 0, "Silky atlas PNG should have embedded entries"
  doAssert "ui/help" in atlas.entries, "Silky atlas should contain ui/help"
  doAssert "vibe/black-circle" in atlas.entries, "Silky atlas should contain vibe/black-circle"
  doAssert "resources/ore_blue" in atlas.entries, "Silky atlas should contain resources/ore_blue"
  doAssert "agents/tracks.ss" in atlas.entries, "Silky atlas should contain agents/tracks.ss"
  doAssert "objects/selection" in atlas.entries, "Silky atlas should contain objects/selection"
  doAssert "objects/altar" in atlas.entries, "Silky atlas should contain objects/altar"
  doAssert "minimap/agent" in atlas.entries, "Silky atlas should contain minimap/agent"
  doAssert "minimap/hub" in atlas.entries, "Silky atlas should contain minimap/hub"
  doAssert "minimap/unknown" in atlas.entries, "Silky atlas should contain minimap/unknown"
  echo "Shared silky atlas test passed"
