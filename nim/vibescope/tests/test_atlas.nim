import
  std/[json, os],
  ../src/vibescope,
  ../src/vibescope/[pixelator, common]

block test_silky_atlas:
  echo "Testing silky atlas generation"
  let silkyImagePath = "silky.atlas.png"
  let silkyJsonPath = "silky.atlas.json"

  buildSilkyAtlas(dataDir / silkyImagePath, dataDir / silkyJsonPath)

  doAssert fileExists(dataDir / silkyJsonPath), "Silky atlas JSON file should be created"

  let silkyJson = parseJson(readFile(dataDir / silkyJsonPath))
  doAssert silkyJson.hasKey("entries"), "Silky atlas JSON should have entries"

  let silkyEntries = silkyJson["entries"]
  doAssert silkyEntries.hasKey("ui/help"), "Silky atlas should contain ui/help"
  doAssert silkyEntries.hasKey("vibe/black-circle"), "Silky atlas should contain vibe/black-circle"
  doAssert silkyEntries.hasKey("resources/ore_blue"), "Silky atlas should contain resources/ore_blue"
  echo "Silky atlas test passed"

block test_pixel_atlas:
  echo "Testing pixel atlas generation"
  let pixelImagePath = "atlas.png"
  let pixelJsonPath = "atlas.json"

  generatePixelAtlas(
    size = 2048,
    margin = 4,
    dirsToScan = @[
      dataDir / "agents",
      dataDir / "objects",
      dataDir / "view",
      dataDir / "minimap"
    ],
    outputImagePath = dataDir / pixelImagePath,
    outputJsonPath = dataDir / pixelJsonPath,
    stripPrefix = dataDir & "/"
  )

  doAssert fileExists(dataDir / pixelJsonPath), "Pixel atlas JSON file should be created"
  
  let pixelJson = parseJson(readFile(dataDir / pixelJsonPath))
  doAssert pixelJson.hasKey("entries"), "Pixel atlas JSON should have entries"

  let pixelEntries = pixelJson["entries"]
  doAssert pixelEntries.hasKey("agents/tracks.ss"), "Pixel atlas should contain agents/tracks.ss"
  doAssert pixelEntries.hasKey("objects/selection"), "Pixel atlas should contain objects/selection"
  doAssert pixelEntries.hasKey("objects/altar"), "Pixel atlas should contain objects/altar"
  echo "Pixel atlas test passed"
