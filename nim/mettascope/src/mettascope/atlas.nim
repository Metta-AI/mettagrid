import
  std/os,
  silky,
  common

export common

proc buildSilkyAtlas*(): AtlasBuilder =
  ## Build the silky UI atlas in memory.
  result = newAtlasBuilder(8192, 4)
  result.addDir(dataDir / "theme/", dataDir / "theme/")
  result.addDir(dataDir / "ui/", dataDir & "/")
  result.addDir(dataDir / "vibe/", dataDir & "/")
  result.addDir(dataDir / "resources/", dataDir & "/")
  result.addDir(dataDir / "icons/", dataDir & "/")
  result.addDir(dataDir / "profiles/", dataDir & "/")
  result.addDir(dataDir / "icons/agents/", dataDir & "/")
  result.addDir(dataDir / "icons/objects/", dataDir & "/")
  result.addDir(dataDir / "agents/", dataDir & "/")
  result.addDir(dataDir / "objects/", dataDir & "/")
  result.addDir(dataDir / "view/", dataDir & "/")
  result.addDir(dataDir / "terrain/", dataDir & "/")
  result.addDir(dataDir / "minimap/", dataDir & "/")
  result.addFont(dataDir / "fonts/Inter-Regular.ttf", "H1", 32.0)
  result.addFont(dataDir / "fonts/Inter-Regular.ttf", "Default", 18.0, subpixelSteps = 10)
  result.addFont(dataDir / "fonts/pf_tempesta_five_compressed.ttf", "pixelated", 32.0)
