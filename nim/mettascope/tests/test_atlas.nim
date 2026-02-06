import
  std/[json, os],
  ../tools/gen_atlas

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

  buildPixelAtlas()

  let pixelJsonPath = dataDir / "atlas.json"
  doAssert fileExists(pixelJsonPath), "Pixel atlas JSON file should be created"

  let pixelJson = parseJson(readFile(pixelJsonPath))
  doAssert pixelJson.hasKey("entries"), "Pixel atlas JSON should have entries"

  let pixelEntries = pixelJson["entries"]
  doAssert pixelEntries.hasKey("agents/tracks.ss"), "Pixel atlas should contain agents/tracks.ss"
  doAssert pixelEntries.hasKey("objects/selection"), "Pixel atlas should contain objects/selection"
  doAssert pixelEntries.hasKey("objects/altar"), "Pixel atlas should contain objects/altar"
  echo "Pixel atlas test passed"

block test_minimap_atlas:
  echo "Testing minimap atlas generation"

  buildMinimapAtlas()

  let minimapJsonPath = dataDir / "atlas_mini.json"
  doAssert fileExists(minimapJsonPath), "Minimap atlas JSON file should be created"

  let minimapJson = parseJson(readFile(minimapJsonPath))
  doAssert minimapJson.hasKey("entries"), "Minimap atlas JSON should have entries"

  let minimapEntries = minimapJson["entries"]
  doAssert minimapEntries.hasKey("minimap/agent"), "Minimap atlas should contain minimap/agent"
  doAssert minimapEntries.hasKey("minimap/hub"), "Minimap atlas should contain minimap/hub"
  doAssert minimapEntries.hasKey("minimap/unknown"), "Minimap atlas should contain minimap/unknown"
  echo "Minimap atlas test passed"
