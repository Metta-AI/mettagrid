import std/[strutils, os, osproc, times]

var
  stabilityKey* = ""
let
  stabilityControlUrl =
    "https://api.stability.ai/v2beta/stable-image/control/style"

const
  ImageRequestRetryCount = 3
  ImageRequestRetryDelayMs = 1500

type
  StabilityError* = object of CatchableError

proc parseHttpStatus(headerText: string): int =
  ## Parses the last HTTP status code from curl response headers.
  var statusCode = 0
  for line in headerText.splitLines():
    let clean = line.strip()
    if not clean.startsWith("HTTP/"):
      continue
    let parts = clean.splitWhitespace()
    if parts.len >= 2:
      try:
        statusCode = parseInt(parts[1])
      except ValueError:
        discard
  return statusCode

proc createTempFilePath(prefix, ext: string): string =
  ## Creates a process-local temp file path suffix.
  let stamp = $int(epochTime() * 1_000_000.0)
  return getTempDir() / (prefix & "_" & stamp & ext)

proc createImage*(
  model: string,
  prompt: string,
  inspirationImagePng: string,
  inspirationPath = "",
  verbose = false,
  aspectRatio = "1:1",
  outputFormat = "png"
): string =
  ## Creates an image and returns PNG/JPEG/WebP bytes.
  if verbose:
    let pathText = if inspirationPath.len > 0: inspirationPath else: "<memory>"
    echo "[stability] Sending inspiration image: ", pathText,
      " (", inspirationImagePng.len, " bytes)"

  if stabilityKey.len == 0:
    raise newException(StabilityError, "Stability API key is empty.")
  if prompt.len == 0:
    raise newException(StabilityError, "Stability image prompt must not be empty.")
  if inspirationImagePng.len == 0:
    raise newException(
      StabilityError,
      "Stability inspiration image payload must not be empty."
    )
  if aspectRatio.len == 0:
    raise newException(StabilityError, "Stability aspect ratio must not be empty.")
  if outputFormat.len == 0:
    raise newException(StabilityError, "Stability output format must not be empty.")

  var inputPath = inspirationPath
  var createdInputPath = ""
  if inputPath.len == 0 or not fileExists(inputPath):
    createdInputPath = createTempFilePath("stability_input", ".png")
    writeFile(createdInputPath, inspirationImagePng)
    inputPath = createdInputPath

  let
    outputPath = createTempFilePath("stability_output", "." & outputFormat)
    headerPath = createTempFilePath("stability_headers", ".txt")
  defer:
    if createdInputPath.len > 0 and fileExists(createdInputPath):
      removeFile(createdInputPath)
    if fileExists(outputPath):
      removeFile(outputPath)
    if fileExists(headerPath):
      removeFile(headerPath)

  var lastErrorMessage = ""
  for attempt in 1 .. ImageRequestRetryCount:
    try:
      var args = @[
        "-sS",
        "-D", headerPath,
        "-o", outputPath,
        "-X", "POST",
        stabilityControlUrl,
        "-H", "Authorization: Bearer " & stabilityKey,
        "-H", "Accept: image/*",
        "--form-string", "prompt=" & prompt,
        "--form-string", "aspect_ratio=" & aspectRatio,
        "--form-string", "output_format=" & outputFormat,
        "-F", "image=@" & inputPath
      ]
      if model.len > 0:
        args.add("--form-string")
        args.add("model=" & model)

      let curlOutput = execProcess(
        "curl",
        args = args,
        options = {poUsePath, poStdErrToStdOut}
      )
      let
        headerText = if fileExists(headerPath): readFile(headerPath) else: ""
        statusCode = parseHttpStatus(headerText)
      if statusCode != 200:
        let bodyText = if fileExists(outputPath): readFile(outputPath) else: ""
        raise newException(
          StabilityError,
          "Stability image generation failed with HTTP " &
          $statusCode & ": " & (if bodyText.len > 0: bodyText else: curlOutput)
        )
      if not fileExists(outputPath):
        raise newException(
          StabilityError,
          "Stability image generation did not return an output image."
        )
      return readFile(outputPath)
    except StabilityError:
      raise
    except CatchableError as err:
      lastErrorMessage = err.msg
      if attempt < ImageRequestRetryCount:
        sleep(ImageRequestRetryDelayMs)

  raise newException(
    StabilityError,
    "Stability image request failed after " &
    $ImageRequestRetryCount & " attempts: " & lastErrorMessage
  )
