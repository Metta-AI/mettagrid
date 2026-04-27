## Test the asset zip download flow end-to-end via Nim ensureAssets.
## Sets METTAGRID_NO_LOCAL_DATA to skip the local data/ directory and force
## the S3/HTTP download path.
##
## Modes:
##   nim r test_asset_zip.nim            — local: zip data/, serve via HTTP, download from localhost
##   nim r test_asset_zip.nim --s3 0.25.6 — s3: download from real S3 (version required)
import std/[os, osproc, strformat, net]
import windy
import ../src/mettascope/assets

const ServerPort = 8000

let params = commandLineParams()
let s3Idx = params.find("--s3")
let useS3 = s3Idx >= 0

setCurrentDir(currentSourcePath().parentDir() / "..")
putEnv("METTAGRID_NO_LOCAL_DATA", "1")

var server: Process

if useS3:
  doAssert s3Idx + 1 < params.len,
    "Usage: nim r test_asset_zip.nim --s3 <version>  (e.g. --s3 0.25.6)"
  let version = params[s3Idx + 1]
  echo &"Testing asset download from S3 (version {version})..."
  let dataDir = ensureAssets(version)
  echo &"Assets cached at: {dataDir}"
  doAssert dirExists(dataDir), &"Asset directory does not exist: {dataDir}"
  putEnv("METTAGRID_ASSET_DIR", dataDir)
  echo "Launching mettascope with S3 assets..."
  discard execCmd("uv run mettagrid-demo --render gui")
else:
  echo "Testing asset download from local server..."

  echo "Querying mettagrid package version..."
  let versionOutput = execProcess(
    "python3",
    args = ["-c",
      "from importlib.metadata import version; print(version('mettagrid'))"],
    options = {poUsePath}
  )
  let version = versionOutput.strip()
  doAssert version.len > 0, "Could not determine mettagrid version"
  echo &"Package version: {version}"

  let serveDir = "/tmp/mettagrid-assets"
  let versionDir = serveDir / &"v{version}"
  createDir(versionDir)

  echo "Packaging assets..."
  doAssert execCmd(
    &"zip -r -q {versionDir}/mettagrid-assets.zip data/ -x 'data/replays/*'"
  ) == 0
  echo &"Created {versionDir}/mettagrid-assets.zip"

  # Kill any stale server from a previous crashed run.
  discard execCmd(
    &"kill $(lsof -ti :{ServerPort}) 2>/dev/null || true"
  )
  sleep(500)

  echo &"Starting local asset server on port {ServerPort}..."
  server = startProcess(
    "python3",
    args = ["-m", "http.server", $ServerPort, "-d", serveDir],
    options = {poParentStreams, poUsePath}
  )

  try:
    putEnv("METTAGRID_ASSET_URL", &"http://localhost:{ServerPort}")

    # Wait for the server to accept connections.
    for i in 0 ..< 50:
      try:
        let sock = newSocket()
        sock.connect("localhost", Port(ServerPort))
        sock.close()
        break
      except OSError:
        sleep(100)

    # Clear any cached assets so the download is actually tested.
    let cacheDir =
      getConfigHome("mettascope") / "cache" / "assets" / "v" & version
    if dirExists(cacheDir):
      echo &"Clearing cached assets at {cacheDir}..."
      removeDir(cacheDir)

    echo "Downloading assets via Nim ensureAssets..."
    let dataDir = ensureAssets(version)
    echo &"Assets cached at: {dataDir}"
    doAssert dirExists(dataDir),
      &"Asset directory does not exist: {dataDir}"

    echo "Launching mettascope with downloaded assets..."
    putEnv("METTAGRID_ASSET_DIR", dataDir)
    discard execCmd("uv run mettagrid-demo --render gui")
  finally:
    server.terminate()
