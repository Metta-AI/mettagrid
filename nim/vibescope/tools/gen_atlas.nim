import ../src/vibescope/pixelator

generatePixelAtlas(
  size = 2048,
  margin = 4,
  dirsToScan = @[
    "data/agents",
    "data/objects",
    "data/view",
    # Keep legacy vibescope-only icons/sprites in the main atlas too (even if
    # some are also packed into silky.atlas).
    "data/vibe",
    # Keep minimap sprites in the main atlas for backwards compatibility;
    # we also generate a dedicated atlas_mini for minimap rendering.
    "data/minimap",
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
