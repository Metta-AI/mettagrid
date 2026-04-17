import
  std/os,
  std/strutils,
  silky,
  ../src/mettascope/atlas

const LfsPointerPrefix = "version https://git-lfs.github.com/spec/"

proc isLfsPointer(path: string): bool =
  ## True when the file at path is a git-lfs pointer stub, not the real blob.
  let f = open(path)
  defer: f.close()
  f.readLine().startsWith(LfsPointerPrefix)

let testDataDir = currentSourcePath().parentDir() / ".." / "data"
setDataDir(testDataDir)

let canary = testDataDir / "ui" / "help.png"
if isLfsPointer(canary):
  echo "Skipping silky atlas test: LFS assets are unsmudged pointer stubs."
  echo "Run `git lfs pull` (or unset GIT_LFS_SKIP_SMUDGE) to exercise this test."
  quit(0)

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
