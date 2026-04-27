## Download and cache mettascope assets from S3.
import
  std/[os, strformat],
  common

when not defined(emscripten):
  import std/times, zippy/ziparchives, windy, windy/http

const
  DefaultS3Url = "https://softmax-public.s3.amazonaws.com/mettagrid-assets"
  AppName = "mettascope"
  DownloadTimeout = 120.float32

proc ensureAssets*(version: string): string =
  ## Resolve the data directory, downloading from S3 if needed.
  let override = getEnv("METTAGRID_ASSET_DIR")
  if override.len > 0:
    doAssert dirExists(override),
      &"METTAGRID_ASSET_DIR={override} does not exist"
    return override

  let skipLocal = getEnv("METTAGRID_NO_LOCAL_DATA").len > 0
  if not skipLocal and dirExists(dataDir):
    return dataDir

  doAssert version.len > 0, "Asset version is required"

  when defined(emscripten):
    return dataDir
  else:
    let
      cacheRoot = getConfigHome(AppName) / "cache"
      versionDir = cacheRoot / "assets" / "v" & version
      assetDataDir = versionDir / "data"
      marker = versionDir / ".complete"

    if fileExists(marker):
      echo &"Assets already cached at {assetDataDir}"
      return assetDataDir

    let
      baseUrl = getEnv(
        "METTAGRID_ASSET_URL",
        DefaultS3Url
      )
      url = baseUrl & "/v" & version & "/mettagrid-assets.zip"

    echo &"Fetching assets from {url}"
    createDir(versionDir)

    let
      tmpZip = versionDir / "tmp_assets.zip"
      tmpExtract = versionDir / "tmp_extract"
    try:
      var
        done = false
        httpError = ""
        httpBody = ""
        httpCode = 0
      let deadline = epochTime() + DownloadTimeout
      let req = startHttpRequest(url, deadline = deadline)
      req.onError = proc(msg: string) =
        httpError = msg
        done = true
      req.onResponse = proc(response: HttpResponse) =
        httpCode = response.code
        httpBody = response.body
        done = true
      req.onDownloadProgress = proc(completed, total: int) =
        if total > 0:
          echo &"Downloading: {completed * 100 div total}%"
      while not done:
        pollHttp()
      doAssert httpError.len == 0,
        &"Asset download failed (network): {httpError}"
      doAssert httpCode == 200,
        &"Asset download failed: HTTP {httpCode} from {url}"
      writeFile(tmpZip, httpBody)

      echo &"Unpacking assets to {versionDir}"
      if dirExists(tmpExtract):
        removeDir(tmpExtract)
      extractAll(tmpZip, tmpExtract)
      removeFile(tmpZip)

      let extractedData = tmpExtract / "data"
      doAssert dirExists(extractedData),
        &"Expected data/ directory in asset zip from {url}"

      if dirExists(assetDataDir):
        removeDir(assetDataDir)
      moveDir(extractedData, assetDataDir)
      writeFile(marker, "")
      echo &"Assets ready at {assetDataDir}"
    finally:
      if fileExists(tmpZip):
        removeFile(tmpZip)
      if dirExists(tmpExtract):
        removeDir(tmpExtract)

    return assetDataDir
