## Test the asset zip download flow locally without uploading to S3.
import std/[os, osproc, strformat]

const Port = 8000

let serveDir = &"/tmp/mettagrid-assets/"
setCurrentDir(currentSourcePath().parentDir() / "..")
createDir(serveDir)

echo "Packaging assets..."
doAssert execCmd(&"zip -r -q {serveDir}/mettagrid-assets.zip data/ -x 'data/replays/*'") == 0
echo &"Created {serveDir}/mettagrid-assets.zip"

echo &"Starting local asset server on port {Port}..."
let server = startProcess(
  "python3",
  args = ["-m", "http.server", $Port, "-d", "/tmp/mettagrid-assets"],
  options = {poParentStreams, poUsePath}
)

echo "Launching mettascope with local asset server..."
putEnv("METTAGRID_ASSET_URL", &"http://localhost:{Port}")
discard execCmd("uv run mettagrid-demo --render gui")

server.terminate()
