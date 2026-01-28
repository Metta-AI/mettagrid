import ../src/mettascope/pixelator

generatePixelAtlas(
  size = 2048,
  margin = 4,
  dirsToScan = @[
    "data/agents",
    "data/objects",
    "data/view",
  ],
  outputImagePath = "data/atlas.png",
  outputJsonPath = "data/atlas.json"
)

generatePixelAtlas(
  size = 256,
  margin = 4,
  dirsToScan = @[
    "data/minimap"
  ],
  outputImagePath = "data/atlas_mini.png",
  outputJsonPath = "data/atlas_mini.json"
)
