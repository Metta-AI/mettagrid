import
  std/os,
  silky,
  ../src/mettascope/pixelator,
  ../src/mettascope/common

export pixelator, common

proc buildSilkyAtlas*(imagePath, jsonPath: string) =
  ## Build the silky UI atlas.
  var builder = newAtlasBuilder(2048, 4)
  builder.addDir(dataDir / "theme/", dataDir / "theme/")
  builder.addDir(dataDir / "ui/", dataDir & "/")
  builder.addDir(dataDir / "vibe/", dataDir & "/")
  builder.addDir(dataDir / "resources/", dataDir & "/")
  builder.addDir(dataDir / "icons/", dataDir & "/")
  builder.addDir(dataDir / "icons/agents/", dataDir & "/")
  builder.addDir(dataDir / "icons/objects/", dataDir & "/")
  builder.addFont(dataDir / "fonts/Inter-Regular.ttf", "H1", 32.0)
  builder.addFont(dataDir / "fonts/Inter-Regular.ttf", "Default", 18.0)
  builder.write(imagePath, jsonPath)

proc buildPixelAtlas*() =
  ## Build the main pixel atlas.
  generatePixelAtlas(
    size = 4096,
    margin = 4,
    dirsToScan = @[
      dataDir / "agents",
      dataDir / "objects",
      dataDir / "view",
    ],
    outputImagePath = dataDir / "atlas.png",
    outputJsonPath = dataDir / "atlas.json",
    stripPrefix = dataDir & "/"
  )

proc buildMinimapAtlas*() =
  ## Build the minimap pixel atlas.
  generatePixelAtlas(
    size = 256,
    margin = 4,
    dirsToScan = @[
      dataDir / "minimap"
    ],
    outputImagePath = dataDir / "atlas_mini.png",
    outputJsonPath = dataDir / "atlas_mini.json",
    stripPrefix = dataDir & "/"
  )

when isMainModule:
  setDataDir("data")
  buildSilkyAtlas(dataDir / "silky.atlas.png", dataDir / "silky.atlas.json")
  buildPixelAtlas()
  buildMinimapAtlas()
