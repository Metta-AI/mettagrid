import
  std/[json, os, osproc, strutils, times],
  curly

var
  tripo3dKey* = ""
let
  tripo3dTaskUrl = "https://api.tripo3d.ai/v2/openapi/task"
  tripo3dUploadUrl = "https://api.tripo3d.ai/v2/openapi/upload/sts"
  curl = newCurlPool(3)

const
  Tripo3dRetryCount = 3
  Tripo3dRetryDelayMs = 1500
  Tripo3dPollDelayMs = 2000
  Tripo3dTimeoutSeconds = (60 * 3).float32
  Tripo3dDefaultPollTimeoutMs = 60 * 10 * 1000
  Tripo3dDefaultModelVersion = "v2.5-20250123"
  Tripo3dDefaultOutputFormat = "GLTF"
  Tripo3dDefaultTextureFormat = "PNG"

proc shouldRetryHttpStatus*(statusCode: int): bool =
  ## Returns true when a Tripo HTTP status should be retried.
  statusCode == 502

type
  Tripo3dError* = object of CatchableError

  TripoTaskStatus* = enum
    queued
    running
    success
    failed
    banned
    expired
    cancelled
    unknown

  TripoTaskOutput* = object
    model*: string
    baseModel*: string
    pbrModel*: string
    generatedImage*: string
    renderedImage*: string

  TripoTask* = object
    taskId*: string
    kind*: string
    status*: TripoTaskStatus
    progress*: int
    output*: TripoTaskOutput

  TripoModelResult* = object
    uploadToken*: string
    generationTaskId*: string
    conversionTaskId*: string
    renderedImageUrl*: string
    modelUrl*: string
    modelData*: string

proc createTempFilePath(prefix, ext: string): string =
  ## Creates a process-local temp file path suffix.
  let stamp = $int(epochTime() * 1_000_000.0)
  getTempDir() / (prefix & "_" & stamp & ext)

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
  statusCode

proc normalizeImageFormat(text: string): string =
  ## Normalizes image format names to Tripo-compatible lowercase values.
  let clean = text.strip().toLowerAscii()
  case clean
  of "jpg", "jpeg":
    "jpeg"
  of "png":
    "png"
  of "webp":
    "webp"
  else:
    raise newException(
      Tripo3dError,
      "Unsupported Tripo image format: " & text
    )

proc guessImageFormat(imagePath: string): string =
  ## Infers image format from the file extension.
  let ext = splitFile(imagePath).ext.strip(
    chars = {'.', ' ', '\t'}
  )
  if ext.len == 0:
    raise newException(
      Tripo3dError,
      "Cannot infer image format from path: " & imagePath
    )
  normalizeImageFormat(ext)

proc apiHeaders(contentType = "application/json"): seq[(string, string)] =
  ## Builds Tripo API headers for authenticated requests.
  if tripo3dKey.len == 0:
    raise newException(Tripo3dError, "Tripo3D API key is empty.")

  result = @[("Authorization", "Bearer " & tripo3dKey)]
  if contentType.len > 0:
    result.add(("Content-Type", contentType))

proc ensureApiSuccess(data: JsonNode, action: string) =
  ## Validates a Tripo API response wrapper.
  let codeNode = data{"code"}
  if codeNode.kind != JInt or codeNode.getInt() != 0:
    let message = data{"message"}.getStr()
    raise newException(
      Tripo3dError,
      "Tripo3D " & action & " failed" &
        (if message.len > 0: ": " & message else: ".")
    )

proc parseTaskStatus(text: string): TripoTaskStatus =
  ## Parses Tripo task status text.
  case text.strip().toLowerAscii()
  of "queued":
    queued
  of "running":
    running
  of "success":
    success
  of "failed":
    failed
  of "banned":
    banned
  of "expired":
    expired
  of "cancelled":
    cancelled
  else:
    unknown

proc parseTask(data: JsonNode): TripoTask =
  ## Parses one Tripo task response body.
  ensureApiSuccess(data, "task request")
  let
    taskNode = data{"data"}
    outputNode = taskNode{"output"}

  result.taskId = taskNode{"task_id"}.getStr()
  result.kind = taskNode{"type"}.getStr()
  result.status = parseTaskStatus(taskNode{"status"}.getStr())
  result.progress = taskNode{"progress"}.getInt()
  result.output = TripoTaskOutput(
    model: outputNode{"model"}.getStr(),
    baseModel: outputNode{"base_model"}.getStr(),
    pbrModel: outputNode{"pbr_model"}.getStr(),
    generatedImage: outputNode{"generated_image"}.getStr(),
    renderedImage: outputNode{"rendered_image"}.getStr()
  )

proc postJson(url: string, body: JsonNode, action: string): JsonNode =
  ## Sends an authenticated JSON POST request to Tripo.
  var lastErrorMessage = ""
  for attempt in 1 .. Tripo3dRetryCount:
    try:
      let response = curl.post(
        url,
        apiHeaders(),
        $body,
        Tripo3dTimeoutSeconds
      )
      if response.code != 200:
        lastErrorMessage = "HTTP " & $response.code & ": " & response.body
        if shouldRetryHttpStatus(response.code) and attempt < Tripo3dRetryCount:
          sleep(Tripo3dRetryDelayMs)
          continue
        raise newException(Tripo3dError, lastErrorMessage)
      let data = parseJson(response.body)
      ensureApiSuccess(data, action)
      return data
    except Tripo3dError:
      raise
    except CatchableError as err:
      lastErrorMessage = err.msg
      if attempt < Tripo3dRetryCount:
        sleep(Tripo3dRetryDelayMs)

  raise newException(
    Tripo3dError,
    "Tripo3D " & action & " failed after " &
      $Tripo3dRetryCount & " attempts: " & lastErrorMessage
  )

proc getJson(url: string, action: string): JsonNode =
  ## Sends an authenticated GET request to Tripo.
  var lastErrorMessage = ""
  for attempt in 1 .. Tripo3dRetryCount:
    try:
      let response = curl.get(
        url,
        apiHeaders(""),
        Tripo3dTimeoutSeconds
      )
      if response.code != 200:
        lastErrorMessage = "HTTP " & $response.code & ": " & response.body
        if shouldRetryHttpStatus(response.code) and attempt < Tripo3dRetryCount:
          sleep(Tripo3dRetryDelayMs)
          continue
        raise newException(Tripo3dError, lastErrorMessage)
      let data = parseJson(response.body)
      ensureApiSuccess(data, action)
      return data
    except Tripo3dError:
      raise
    except CatchableError as err:
      lastErrorMessage = err.msg
      if attempt < Tripo3dRetryCount:
        sleep(Tripo3dRetryDelayMs)

  raise newException(
    Tripo3dError,
    "Tripo3D " & action & " failed after " &
      $Tripo3dRetryCount & " attempts: " & lastErrorMessage
  )

proc uploadImage*(
  imageBytes: string,
  imagePath = "",
  verbose = false
): string =
  ## Uploads an image to Tripo and returns an image token.
  if tripo3dKey.len == 0:
    raise newException(Tripo3dError, "Tripo3D API key is empty.")
  if imageBytes.len == 0:
    raise newException(Tripo3dError, "Tripo3D image payload must not be empty.")

  let format =
    if imagePath.len > 0:
      guessImageFormat(imagePath)
    else:
      "png"

  var
    inputPath = imagePath
    createdInputPath = ""
  if inputPath.len == 0 or not fileExists(inputPath):
    createdInputPath = createTempFilePath("tripo3d_upload", "." & format)
    writeFile(createdInputPath, imageBytes)
    inputPath = createdInputPath

  let
    outputPath = createTempFilePath("tripo3d_upload_response", ".json")
    headerPath = createTempFilePath("tripo3d_upload_headers", ".txt")
  defer:
    if createdInputPath.len > 0 and fileExists(createdInputPath):
      removeFile(createdInputPath)
    if fileExists(outputPath):
      removeFile(outputPath)
    if fileExists(headerPath):
      removeFile(headerPath)

  if verbose:
    let pathText = if imagePath.len > 0: imagePath else: "<memory>"
    echo "[tripo3d] Uploading image: ", pathText,
      " (", imageBytes.len, " bytes)"

  var lastErrorMessage = ""
  for attempt in 1 .. Tripo3dRetryCount:
    try:
      let curlOutput = execProcess(
        "curl",
        args = @[
          "-sS",
          "-D", headerPath,
          "-o", outputPath,
          "-X", "POST",
          tripo3dUploadUrl,
          "-H", "Authorization: Bearer " & tripo3dKey,
          "-F", "file=@" & inputPath
        ],
        options = {poUsePath, poStdErrToStdOut}
      )
      let
        headerText = if fileExists(headerPath): readFile(headerPath) else: ""
        statusCode = parseHttpStatus(headerText)
      if statusCode != 200:
        let bodyText = if fileExists(outputPath): readFile(outputPath) else: ""
        lastErrorMessage =
          "Tripo3D upload failed with HTTP " &
          $statusCode & ": " &
          (if bodyText.len > 0: bodyText else: curlOutput)
        if shouldRetryHttpStatus(statusCode) and attempt < Tripo3dRetryCount:
          sleep(Tripo3dRetryDelayMs)
          continue
        raise newException(Tripo3dError, lastErrorMessage)
      let bodyText = readFile(outputPath)
      let data = parseJson(bodyText)
      ensureApiSuccess(data, "upload")
      let token = data{"data"}{"image_token"}.getStr()
      if token.len == 0:
        raise newException(
          Tripo3dError,
          "Tripo3D upload response did not contain image_token."
        )
      return token
    except Tripo3dError:
      raise
    except CatchableError as err:
      lastErrorMessage = err.msg
      if attempt < Tripo3dRetryCount:
        sleep(Tripo3dRetryDelayMs)

  raise newException(
    Tripo3dError,
    "Tripo3D upload failed after " &
      $Tripo3dRetryCount & " attempts: " & lastErrorMessage
  )

proc createTask(body: JsonNode, action: string): string =
  ## Creates a Tripo task and returns its task id.
  let data = postJson(tripo3dTaskUrl, body, action)
  let taskId = data{"data"}{"task_id"}.getStr()
  if taskId.len == 0:
    raise newException(
      Tripo3dError,
      "Tripo3D " & action & " response did not contain task_id."
    )
  taskId

proc getTask*(taskId: string): TripoTask =
  ## Fetches one Tripo task by id.
  if taskId.len == 0:
    raise newException(Tripo3dError, "Tripo3D task id must not be empty.")
  let url = tripo3dTaskUrl & "/" & taskId
  parseTask(getJson(url, "task request"))

proc waitForTaskSuccess*(
  taskId: string,
  verbose = false,
  pollDelayMs = Tripo3dPollDelayMs,
  timeoutMs = Tripo3dDefaultPollTimeoutMs
): TripoTask =
  ## Polls a Tripo task until it succeeds or fails.
  let startMs = int(epochTime() * 1000.0)
  while true:
    let task = getTask(taskId)
    if verbose:
      echo "[tripo3d] Task ", task.taskId,
        " status=", $task.status,
        " progress=", task.progress
    case task.status
    of success:
      return task
    of queued, running:
      discard
    of failed, banned, expired, cancelled, unknown:
      raise newException(
        Tripo3dError,
        "Tripo3D task " & taskId &
          " ended with status " & $task.status & "."
      )

    let nowMs = int(epochTime() * 1000.0)
    if nowMs - startMs > timeoutMs:
      raise newException(
        Tripo3dError,
        "Tripo3D task timed out: " & taskId
      )
    sleep(pollDelayMs)

proc chooseModelUrl(task: TripoTask, preferPbr: bool): string =
  ## Selects the richest available output model URL.
  if preferPbr and task.output.pbrModel.len > 0:
    return task.output.pbrModel
  if task.output.model.len > 0:
    return task.output.model
  if task.output.baseModel.len > 0:
    return task.output.baseModel
  raise newException(
    Tripo3dError,
    "Tripo3D task output did not contain a model URL."
  )

proc downloadBinary(url: string, verbose = false): string =
  ## Downloads binary output bytes from a URL.
  if url.len == 0:
    raise newException(Tripo3dError, "Download URL must not be empty.")

  let
    outputPath = createTempFilePath("tripo3d_download", ".bin")
    headerPath = createTempFilePath("tripo3d_download_headers", ".txt")
  defer:
    if fileExists(outputPath):
      removeFile(outputPath)
    if fileExists(headerPath):
      removeFile(headerPath)

  if verbose:
    echo "[tripo3d] Downloading model: ", url

  var lastErrorMessage = ""
  for attempt in 1 .. Tripo3dRetryCount:
    try:
      let curlOutput = execProcess(
        "curl",
        args = @[
          "-sS",
          "-L",
          "-D", headerPath,
          "-o", outputPath,
          url
        ],
        options = {poUsePath, poStdErrToStdOut}
      )
      let
        headerText = if fileExists(headerPath): readFile(headerPath) else: ""
        statusCode = parseHttpStatus(headerText)
      if statusCode != 200:
        let bodyText = if fileExists(outputPath): readFile(outputPath) else: ""
        lastErrorMessage =
          "Tripo3D download failed with HTTP " &
          $statusCode & ": " &
          (if bodyText.len > 0: bodyText else: curlOutput)
        if shouldRetryHttpStatus(statusCode) and attempt < Tripo3dRetryCount:
          sleep(Tripo3dRetryDelayMs)
          continue
        raise newException(Tripo3dError, lastErrorMessage)
      return readFile(outputPath)
    except Tripo3dError:
      raise
    except CatchableError as err:
      lastErrorMessage = err.msg
      if attempt < Tripo3dRetryCount:
        sleep(Tripo3dRetryDelayMs)

  raise newException(
    Tripo3dError,
    "Tripo3D download failed after " &
      $Tripo3dRetryCount & " attempts: " & lastErrorMessage
  )

proc createModel*(
  imageBytes: string,
  imagePath = "",
  verbose = false,
  modelVersion = Tripo3dDefaultModelVersion,
  faceLimit = 0,
  texture = true,
  pbr = true,
  textureQuality = "standard",
  enableImageAutofix = false,
  orientation = "default",
  outputFormat = Tripo3dDefaultOutputFormat,
  textureFormat = Tripo3dDefaultTextureFormat,
  bake = true,
  packUv = false,
  withAnimation = true,
  timeoutMs = Tripo3dDefaultPollTimeoutMs
): TripoModelResult =
  ## Creates a textured 3D model from an image and downloads the result.
  let imageToken = uploadImage(
    imageBytes = imageBytes,
    imagePath = imagePath,
    verbose = verbose
  )

  var generationBody = %*{
    "type": "image_to_model",
    "model_version": modelVersion,
    "file": {
      "type": guessImageFormat(
        if imagePath.len > 0: imagePath else: "image.png"
      ),
      "file_token": imageToken
    },
    "texture": texture,
    "pbr": pbr,
    "enable_image_autofix": enableImageAutofix,
    "orientation": orientation
  }
  if faceLimit > 0:
    generationBody["face_limit"] = %faceLimit
  if textureQuality.len > 0:
    generationBody["texture_quality"] = %textureQuality

  let generationTaskId = createTask(generationBody, "generation task creation")
  let generationTask = waitForTaskSuccess(
    generationTaskId,
    verbose = verbose,
    timeoutMs = timeoutMs
  )

  var conversionBody = %*{
    "type": "convert_model",
    "format": outputFormat,
    "original_model_task_id": generationTask.taskId,
    "texture_format": textureFormat,
    "with_animation": withAnimation,
    "pack_uv": packUv,
    "bake": bake
  }
  if faceLimit > 0:
    conversionBody["face_limit"] = %faceLimit

  let conversionTaskId = createTask(
    conversionBody,
    "conversion task creation"
  )
  let conversionTask = waitForTaskSuccess(
    conversionTaskId,
    verbose = verbose,
    timeoutMs = timeoutMs
  )

  let modelUrl = chooseModelUrl(conversionTask, preferPbr = pbr)
  result = TripoModelResult(
    uploadToken: imageToken,
    generationTaskId: generationTask.taskId,
    conversionTaskId: conversionTask.taskId,
    renderedImageUrl:
      if conversionTask.output.renderedImage.len > 0:
        conversionTask.output.renderedImage
      else:
        generationTask.output.renderedImage,
    modelUrl: modelUrl,
    modelData: downloadBinary(modelUrl, verbose = verbose)
  )
