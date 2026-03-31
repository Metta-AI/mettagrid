import
  std/os,
  silky,
  ../src/mettascope/common

export common

proc buildSilkyAtlas*(imagePath: string) =
  ## Build the silky UI atlas as one PNG with embedded metadata.
  var builder = newAtlasBuilder(8192, 4)
  builder.addDir(dataDir / "theme/", dataDir / "theme/")
  builder.addDir(dataDir / "ui/", dataDir & "/")
  builder.addDir(dataDir / "vibe/", dataDir & "/")
  builder.addDir(dataDir / "resources/", dataDir & "/")
  builder.addDir(dataDir / "icons/", dataDir & "/")
  builder.addDir(dataDir / "profiles/", dataDir & "/")
  builder.addDir(dataDir / "icons/agents/", dataDir & "/")
  builder.addDir(dataDir / "icons/objects/", dataDir & "/")
  builder.addDir(dataDir / "agents/", dataDir & "/")
  builder.addDir(dataDir / "objects/", dataDir & "/")
  builder.addDir(dataDir / "view/", dataDir & "/")
  builder.addDir(dataDir / "terrain/", dataDir & "/")
  builder.addDir(dataDir / "minimap/", dataDir & "/")
  builder.addFont(dataDir / "fonts/Inter-Regular.ttf", "H1", 32.0)
  builder.addFont(dataDir / "fonts/Inter-Regular.ttf", "Default", 18.0, subpixelSteps = 10)
  builder.addFont(dataDir / "fonts/pf_tempesta_five_compressed.ttf", "pixelated", 32.0)
  builder.write(imagePath)

when isMainModule:
  setDataDir("data")
  buildSilkyAtlas(dataDir / "silky.atlas.png")
