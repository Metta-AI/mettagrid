import
  std/[algorithm, json, math, os, osproc, parseopt, strutils, tables],
  pixie,
  render_sprite as gltfRenderer,
  artgen/tripo3d as tripo3dConnection,
  artgen/gemini as geminiConnection,
  artgen/openai as openAiConnection,
  artgen/stability as stabilityConnection,
  artgen/xai as xaiConnection,
  artgen/claude as claudeConnection

const
  DefaultInputDir = "artin"
  DefaultOutputDir = "artout"
  AwsSecretsId = "mettascope/artgen"
  AwsSecretsRegion = "us-east-1"
  GeminiDefaultModel = "gemini-2.5-flash-image"
  OpenAiDefaultModel = "gpt-image-1"
  XaiDefaultModel = "grok-imagine-image"
  StabilityDefaultModel = "stable-image-core"
  OpenAiDefaultGenerationSize = "1024x1024"
  XaiDefaultGenerationSize = "2k"
  GeminiDefaultGenerationSize = ""
  StabilityDefaultGenerationSize = ""

type
  Provider* = enum
    openai
    claude
    gemini
    xai
    stability

  SectionKind = enum
    sectionBody
    sectionPrefix
    sectionPostfix

  ArtGenConfig* = object
    inputDir*: string
    outputDir*: string
    force*: bool
    keep3d*: bool
    keepConcept*: bool
    verbose*: bool

  ParsedMarkdown = object
    prefix: string
    body: string
    postfix: string
    args: Table[string, string]

  ResolvedAsset* = object
    sourcePath*: string
    outputPath*: string
    prompt*: string
    args*: Table[string, string]

  DirectionVariant* = object
    suffix*: string
    rotYOffsetDeg*: float32

  ProviderSettings* = object
    defaultModel*: string
    defaultGenerationSize*: string
    supportsTransparentBackground*: bool

  ArtgenSecrets* = object
    openAiKey*: string
    geminiKey*: string
    xaiKey*: string
    stabilityKey*: string
    tripo3dKey*: string
    claudeKey*: string

  ArtGenError* = object of CatchableError

proc defaultArtGenConfig*(): ArtGenConfig =
  ## Returns the default ArtGen configuration.
  let toolDir = splitFile(currentSourcePath()).dir
  ArtGenConfig(
    inputDir: joinPath(toolDir, DefaultInputDir),
    outputDir: joinPath(toolDir, DefaultOutputDir),
    force: false,
    keep3d: false,
    keepConcept: false,
    verbose: false
  )

proc parseOutputSize(outputSize: string): (int, int)
proc ensureOutputDirectory(outputPath: string)

proc resolveDirections*(text: string): seq[DirectionVariant] =
  ## Resolves one allowed directions setting into directional render variants.
  let a = -90.0
  case text.strip()
  of "", "1":
    @[DirectionVariant(suffix: "", rotYOffsetDeg: 0.0)]
  of "4":
    @[
      DirectionVariant(suffix: "n", rotYOffsetDeg: a + 0.0),
      DirectionVariant(suffix: "e", rotYOffsetDeg: a + 90.0),
      DirectionVariant(suffix: "s", rotYOffsetDeg: a + 180.0),
      DirectionVariant(suffix: "w", rotYOffsetDeg: a + 270.0)
    ]
  of "8":
    @[
      DirectionVariant(suffix: "n", rotYOffsetDeg: a + 0.0),
      DirectionVariant(suffix: "ne", rotYOffsetDeg: a + 45.0),
      DirectionVariant(suffix: "e", rotYOffsetDeg: a + 90.0),
      DirectionVariant(suffix: "se", rotYOffsetDeg: a + 135.0),
      DirectionVariant(suffix: "s", rotYOffsetDeg: a + 180.0),
      DirectionVariant(suffix: "sw", rotYOffsetDeg: a + 225.0),
      DirectionVariant(suffix: "w", rotYOffsetDeg: a + 270.0),
      DirectionVariant(suffix: "nw", rotYOffsetDeg: a + 315.0)
    ]
  else:
    raise newException(
      ArtGenError,
      "Invalid @directions value. Use 1, 4, or 8."
    )

proc secretValue(
  data: JsonNode,
  keys: openArray[string],
  label: string
): string =
  ## Returns the first non-empty secret value from a JSON object.
  for key in keys:
    if key in data:
      let value = data[key].getStr().strip()
      if value.len > 0:
        return value
  raise newException(
    ArtGenError,
    "Missing required artgen secret: " & label
  )

proc parseArtgenSecrets*(secretString: string): ArtgenSecrets =
  ## Parses the AWS Secrets Manager JSON payload for artgen.
  let data =
    try:
      parseJson(secretString)
    except JsonParsingError as err:
      raise newException(
        ArtGenError,
        "Failed to parse AWS artgen secrets JSON: " & err.msg
      )
  if data.kind != JObject:
    raise newException(
      ArtGenError,
      "AWS artgen secret must be a JSON object."
    )

  ArtgenSecrets(
    openAiKey: secretValue(data, ["openai", "openaiKey", "openai_key"], "openai"),
    geminiKey: secretValue(data, ["gemini", "geminiKey", "gemini_key"], "gemini"),
    xaiKey: secretValue(data, ["xai", "xaiKey", "xai_key"], "xai"),
    stabilityKey: secretValue(
      data,
      ["stability", "stabilityKey", "stability_key"],
      "stability"
    ),
    tripo3dKey: secretValue(
      data,
      ["tripo3d", "tripo3dKey", "tripo3d_key"],
      "tripo3d"
    ),
    claudeKey: secretValue(data, ["claude", "claudeKey", "claude_key"], "claude")
  )

proc applyArtgenSecrets*(secrets: ArtgenSecrets) =
  ## Applies parsed secrets to the connector modules.
  openAiConnection.aiKey = secrets.openAiKey
  geminiConnection.geminiKey = secrets.geminiKey
  xaiConnection.xaiKey = secrets.xaiKey
  stabilityConnection.stabilityKey = secrets.stabilityKey
  tripo3dConnection.tripo3dKey = secrets.tripo3dKey
  claudeConnection.claudeKey = secrets.claudeKey

proc loadArtgenSecrets(): ArtgenSecrets =
  ## Loads connector secrets from AWS Secrets Manager.
  let command =
    "aws secretsmanager get-secret-value " &
    "--secret-id \"" & AwsSecretsId & "\" " &
    "--region \"" & AwsSecretsRegion & "\" " &
    "--query \"SecretString\" " &
    "--output text"
  let commandResult =
    try:
      execCmdEx(command)
    except OSError as err:
      raise newException(
        ArtGenError,
        "Failed to execute AWS CLI for artgen secrets: " & err.msg
      )
  if commandResult.exitCode != 0:
    raise newException(
      ArtGenError,
      "Failed to load artgen secrets from AWS Secrets Manager: " &
      commandResult.output.strip()
    )
  let secretString = commandResult.output.strip()
  if secretString.len == 0:
    raise newException(
      ArtGenError,
      "AWS Secrets Manager returned an empty artgen secret payload."
    )
  parseArtgenSecrets(secretString)

proc initializeArtgenSecrets() =
  ## Loads and applies connector secrets before generation starts.
  applyArtgenSecrets(loadArtgenSecrets())

proc resolveProviderSettings*(provider: Provider): ProviderSettings =
  ## Resolves provider defaults for generation behavior.
  case provider
  of openai:
    ProviderSettings(
      defaultModel: OpenAiDefaultModel,
      defaultGenerationSize: OpenAiDefaultGenerationSize,
      supportsTransparentBackground: false
    )
  of xai:
    ProviderSettings(
      defaultModel: XaiDefaultModel,
      defaultGenerationSize: XaiDefaultGenerationSize,
      supportsTransparentBackground: false
    )
  of gemini:
    ProviderSettings(
      defaultModel: GeminiDefaultModel,
      defaultGenerationSize: GeminiDefaultGenerationSize,
      supportsTransparentBackground: false
    )
  of stability:
    ProviderSettings(
      defaultModel: StabilityDefaultModel,
      defaultGenerationSize: StabilityDefaultGenerationSize,
      supportsTransparentBackground: false
    )
  of claude:
    ProviderSettings()

proc logVerbose(config: ArtGenConfig, message: string) =
  ## Writes a verbose log line when verbose mode is active.
  if config.verbose:
    echo "[artgen] ", message

proc parseProvider(text: string): Provider =
  ## Parses provider text into a provider enum value.
  case text.strip().toLowerAscii()
  of "openai":
    openai
  of "claude":
    claude
  of "gemini":
    gemini
  of "xai":
    xai
  of "stability":
    stability
  else:
    raise newException(
      ArtGenError,
      "Unknown provider: " & text
    )

proc normalizeKey(text: string): string =
  ## Normalizes an argument key for storage and comparison.
  text.strip().toLowerAscii()

proc isSectionHeading(line, name: string): bool =
  ## Returns true when a markdown heading matches the section name.
  let stripped = line.strip()
  if not stripped.startsWith("#"):
    return false
  let heading = stripped.strip(chars = {'#', ' ', '\t'}).toLowerAscii()
  heading == name

proc addParagraph(target: var seq[string], paragraph: var seq[string]) =
  ## Flushes one paragraph into the target collection.
  if paragraph.len == 0:
    return
  target.add paragraph.join("\n")
  paragraph.setLen(0)

proc parseCommandLine(line: string): (string, string) =
  ## Parses one @key value or @key=value command line.
  let stripped = line.strip()
  if stripped.len == 0 or stripped[0] != '@':
    raise newException(
      ArtGenError,
      "Invalid command line: " & line
    )

  let text = stripped[1 .. ^1].strip()
  if text.len == 0:
    raise newException(
      ArtGenError,
      "Missing command name: " & line
    )

  let equalsIndex = text.find('=')
  var spaceIndex = -1
  for i, ch in text:
    if ch in {' ', '\t'}:
      spaceIndex = i
      break

  let splitIndex =
    if equalsIndex >= 0 and (spaceIndex < 0 or equalsIndex < spaceIndex):
      equalsIndex
    else:
      spaceIndex

  if splitIndex < 0:
    return (normalizeKey(text), "true")

  let
    key = normalizeKey(text[0 ..< splitIndex])
    value = text[splitIndex + 1 .. ^1].strip()
  if key.len == 0:
    raise newException(
      ArtGenError,
      "Missing command name: " & line
    )
  (key, value)

proc parseMarkdownFile(path: string): ParsedMarkdown =
  ## Parses markdown text into prefix, body, postfix, and commands.
  result.args = initTable[string, string]()

  var
    section = sectionBody
    prefixParagraphs: seq[string]
    bodyParagraphs: seq[string]
    postfixParagraphs: seq[string]
    paragraph: seq[string]

  for rawLine in readFile(path).splitLines():
    let line = rawLine.strip()

    if line.len == 0:
      case section
      of sectionPrefix:
        addParagraph(prefixParagraphs, paragraph)
      of sectionBody:
        addParagraph(bodyParagraphs, paragraph)
      of sectionPostfix:
        addParagraph(postfixParagraphs, paragraph)
      continue

    if line.startsWith("@"):
      let (key, value) = parseCommandLine(line)
      result.args[key] = value
      continue

    if isSectionHeading(line, "prefix"):
      case section
      of sectionPrefix:
        addParagraph(prefixParagraphs, paragraph)
      of sectionBody:
        addParagraph(bodyParagraphs, paragraph)
      of sectionPostfix:
        addParagraph(postfixParagraphs, paragraph)
      section = sectionPrefix
      continue

    if isSectionHeading(line, "postfix"):
      case section
      of sectionPrefix:
        addParagraph(prefixParagraphs, paragraph)
      of sectionBody:
        addParagraph(bodyParagraphs, paragraph)
      of sectionPostfix:
        addParagraph(postfixParagraphs, paragraph)
      section = sectionPostfix
      continue

    if line.startsWith("#"):
      continue

    paragraph.add line

  case section
  of sectionPrefix:
    addParagraph(prefixParagraphs, paragraph)
  of sectionBody:
    addParagraph(bodyParagraphs, paragraph)
  of sectionPostfix:
    addParagraph(postfixParagraphs, paragraph)

  result.prefix = prefixParagraphs.join("\n\n")
  result.body = bodyParagraphs.join("\n\n")
  result.postfix = postfixParagraphs.join("\n\n")

proc mergeArgs(
  target: var Table[string, string],
  source: Table[string, string]
) =
  ## Merges one argument table into another with override semantics.
  for key, value in source.pairs():
    target[key] = value

proc pathChain(rootDir, leafDir: string): seq[string] =
  ## Returns the directory chain from root to leaf inclusive.
  let
    root = absolutePath(rootDir)
    leaf = absolutePath(leafDir)
  var current = leaf
  while true:
    result.add current
    if current == root:
      break
    let parent = current.parentDir()
    if parent == current:
      raise newException(
        ArtGenError,
        "Path is outside input tree: " & leafDir
      )
    current = parent
  result.reverse()

proc joinNonEmpty(parts: seq[string]): string =
  ## Joins non-empty sections with blank lines.
  var clean: seq[string]
  for part in parts:
    let text = part.strip()
    if text.len > 0:
      clean.add text
  clean.join("\n\n")

proc relativeOutputPath(
  config: ArtGenConfig,
  assetPath: string,
  args: Table[string, string]
): string =
  ## Resolves the output path for one asset.
  let format = args.getOrDefault("format", "png").strip(
    chars = {' ', '\t', '.'}
  ).toLowerAscii()

  if args.hasKey("output"):
    let outputValue = args["output"].strip()
    if outputValue.isAbsolute():
      if splitFile(outputValue).ext.len == 0:
        return outputValue & "." & format
      return outputValue

    let joined = joinPath(config.outputDir, outputValue)
    if splitFile(joined).ext.len == 0:
      return joined & "." & format
    return joined

  let
    assetDir = assetPath.parentDir()
    relativeDir = relativePath(assetDir, config.inputDir)
    baseName = args.getOrDefault("name", splitFile(assetPath).name).strip()
    fileName = baseName & "." & format
  if relativeDir.len == 0 or relativeDir == ".":
    return joinPath(config.outputDir, fileName)
  joinPath(config.outputDir, relativeDir, fileName)

proc directionalOutputPaths*(
  baseOutputPath: string,
  directions: seq[DirectionVariant]
): seq[string] =
  ## Resolves one output path per direction variant.
  let parsed = splitFile(baseOutputPath)
  for direction in directions:
    if direction.suffix.len == 0:
      result.add baseOutputPath
    else:
      result.add joinPath(
        parsed.dir,
        parsed.name & "." & direction.suffix & parsed.ext
      )

proc shouldSkipDirectionalOutputs*(
  force: bool,
  outputPaths: seq[string]
): bool =
  ## Returns true when all directional output files already exist.
  if force:
    return false
  for outputPath in outputPaths:
    if not fileExists(outputPath):
      return false
  outputPaths.len > 0

proc conceptOutputPath*(config: ArtGenConfig, outputPath: string): string =
  ## Resolves the concept image path under arttmp.
  let
    outputRoot = absolutePath(config.outputDir)
    tempRoot = joinPath(outputRoot.parentDir(), "arttmp")
    absoluteOutputPath = absolutePath(outputPath)
    relativePathText = relativePath(absoluteOutputPath, outputRoot)
    parsed = splitFile(relativePathText)
    extension =
      if parsed.ext.len > 0:
        parsed.ext
      else:
        ".png"
    fileName = parsed.name & ".concept" & extension
  if parsed.dir.len == 0 or parsed.dir == ".":
    return joinPath(tempRoot, fileName)
  joinPath(tempRoot, parsed.dir, fileName)

proc prepareConceptPath*(config: ArtGenConfig, outputPath: string): string =
  ## Resolves the active concept cache path.
  conceptOutputPath(config, outputPath)

proc modelOutputPath*(config: ArtGenConfig, outputPath: string): string =
  ## Resolves the Tripo-generated model path under arttmp.
  let
    outputRoot = absolutePath(config.outputDir)
    tempRoot = joinPath(outputRoot.parentDir(), "arttmp")
    absoluteOutputPath = absolutePath(outputPath)
    relativePathText = relativePath(absoluteOutputPath, outputRoot)
    parsed = splitFile(relativePathText)
    fileName = parsed.name & ".glb"
  if parsed.dir.len == 0 or parsed.dir == ".":
    return joinPath(tempRoot, fileName)
  joinPath(tempRoot, parsed.dir, fileName)

proc shouldReuseConcept*(config: ArtGenConfig, conceptPath: string): bool =
  ## Returns true when an existing concept cache should be reused.
  config.keepConcept and fileExists(conceptPath)

proc shouldReuse3d*(config: ArtGenConfig, modelPath: string): bool =
  ## Returns true when an existing GLB should be reused.
  config.keep3d and fileExists(modelPath)

proc resolveAsset*(config: ArtGenConfig, assetPath: string): ResolvedAsset =
  ## Resolves inherited prompt sections and final arguments for one asset.
  let directoryChain = pathChain(config.inputDir, assetPath.parentDir())

  var
    prefixes: seq[string]
    postfixes: seq[string]
    mergedArgs = initTable[string, string]()

  for directory in directoryChain:
    let contextPath = joinPath(directory, "_.md")
    if not fileExists(contextPath):
      continue
    let parsed = parseMarkdownFile(contextPath)
    if parsed.prefix.strip().len > 0:
      prefixes.add parsed.prefix.strip()
    if parsed.postfix.strip().len > 0:
      postfixes.add parsed.postfix.strip()
    mergeArgs(mergedArgs, parsed.args)

  let asset = parseMarkdownFile(assetPath)
  mergeArgs(mergedArgs, asset.args)

  if not mergedArgs.hasKey("format"):
    mergedArgs["format"] = "png"

  result.sourcePath = assetPath
  result.outputPath = relativeOutputPath(config, assetPath, mergedArgs)
  result.prompt = joinNonEmpty(prefixes & @[asset.body] & postfixes)
  result.args = mergedArgs

proc resolveGltfRenderConfig*(
  asset: ResolvedAsset,
  modelPath, outputPath: string,
  rotYOffsetDeg: float32
): gltfRenderer.ViewerConfig =
  ## Resolves a GLTF viewer config from inherited asset arguments.
  let
    sizeText = asset.args.getOrDefault("size", "")
    (targetWidth, targetHeight) = parseOutputSize(sizeText)
    defaultWidth =
      if targetWidth > 0:
        targetWidth
      else:
        128
    defaultHeight =
      if targetHeight > 0:
        targetHeight
      else:
        128
  result = gltfRenderer.viewerConfigFromArgs(
    asset.args,
    modelPath,
    outputPath,
    defaultWidth,
    defaultHeight
  )
  result.rotYDeg += rotYOffsetDeg

proc collectAssetFiles(inputDir: string): seq[string] =
  ## Collects all asset markdown files under the input directory.
  for path in walkDirRec(inputDir):
    if path.toLowerAscii().endsWith(".md") and splitFile(path).name != "_":
      result.add path
  result.sort()

proc escapeHtml(text: string): string =
  ## Escapes one string for safe HTML output.
  result = text
  result = result.replace("&", "&amp;")
  result = result.replace("<", "&lt;")
  result = result.replace(">", "&gt;")
  result = result.replace("\"", "&quot;")

proc artTmpRoot(config: ArtGenConfig): string =
  ## Resolves the root arttmp directory next to artout.
  let outputRoot = absolutePath(config.outputDir)
  joinPath(outputRoot.parentDir(), "arttmp")

proc collectOutputImages(config: ArtGenConfig): seq[string] =
  ## Collects final output images under artout for HTML indexing.
  if not dirExists(config.outputDir):
    return
  for path in walkDirRec(config.outputDir):
    if path.toLowerAscii().endsWith(".png"):
      result.add path
  result.sort()

proc buildArttmpIndexHtml*(config: ArtGenConfig, imagePaths: seq[string]): string =
  ## Builds an HTML page that previews artout images grouped by folder.
  let
    outputRoot = absolutePath(config.outputDir)
    tmpRoot = artTmpRoot(config)
  var
    currentGroup = ""
    cards: seq[string]
  cards.add "<!doctype html>"
  cards.add "<html><head><meta charset=\"utf-8\"><title>Art Index</title>"
  cards.add "<style>body{font-family:sans-serif;background:#1a1a1a;color:#eee;margin:24px;}h1{margin-top:32px;}div.grid{display:flex;flex-wrap:wrap;gap:16px;}a.card{display:block;width: 256px;text-decoration:none;color:#eee;}img.preview{width: 256px;height: 256px;object-fit:contain;background:#555;image-rendering: pixelated;image-rendering: crisp-edges;border:1px solid #444;}div.label{margin-top:8px;font-size:14px;word-break:break-word;}</style></head><body>"
  for imagePath in imagePaths:
    let
      relativePath = relativePath(absolutePath(imagePath), outputRoot)
      group =
        if splitFile(relativePath).dir.len > 0 and splitFile(relativePath).dir != ".":
          splitFile(relativePath).dir
        else:
          "."
      linkPath = relativePath(absolutePath(imagePath), tmpRoot).replace("\\", "/")
      label = splitFile(relativePath).name
    if group != currentGroup:
      if currentGroup.len > 0:
        cards.add "</div>"
      cards.add "<h1>" & escapeHtml(group) & "</h1>"
      cards.add "<div class=\"grid\">"
      currentGroup = group
    cards.add(
      "<a class=\"card\" href=\"" & escapeHtml(linkPath) & "\">" &
      "<img class=\"preview\" src=\"" & escapeHtml(linkPath) & "\" alt=\"" &
      escapeHtml(label) & "\">" &
      "<div class=\"label\">" & escapeHtml(label) & "</div></a>"
    )
  if currentGroup.len > 0:
    cards.add "</div>"
  cards.add "</body></html>"
  cards.join("\n")

proc writeArttmpIndex*(config: ArtGenConfig): string =
  ## Writes an HTML index in arttmp for quickly scanning generated outputs.
  let
    tmpRoot = artTmpRoot(config)
    indexPath = joinPath(tmpRoot, "index.html")
    html = buildArttmpIndexHtml(config, collectOutputImages(config))
  ensureOutputDirectory(indexPath)
  writeFile(indexPath, html)
  indexPath

proc printArgs(args: Table[string, string]) =
  ## Prints arguments in a stable key order.
  var keys: seq[string]
  for key in args.keys():
    keys.add key
  keys.sort()
  for key in keys:
    echo "@", key, ": ", args[key]

proc printResolvedAsset(asset: ResolvedAsset) =
  ## Prints the resolved prompt, output path, and arguments.
  echo "Source: ", asset.sourcePath
  echo "Output: ", asset.outputPath
  echo "Prompt:"
  if asset.prompt.len == 0:
    echo "(empty)"
  else:
    echo asset.prompt
  echo "Args:"
  printArgs(asset.args)
  echo ""

proc parseOutputSize(outputSize: string): (int, int) =
  ## Parses size text in WxH format and returns width and height.
  let text = outputSize.strip()
  if text.len == 0:
    return (0, 0)

  let divider = text.find('x')
  if divider <= 0 or divider >= text.len - 1:
    raise newException(
      ArtGenError,
      "Invalid size format. Use WxH, for example 128x128."
    )

  let
    widthText = text[0 ..< divider].strip()
    heightText = text[divider + 1 .. ^1].strip()
  try:
    let
      width = parseInt(widthText)
      height = parseInt(heightText)
    if width <= 0 or height <= 0:
      raise newException(
        ArtGenError,
        "Invalid size values. Width and height must be > 0."
      )
    (width, height)
  except ValueError:
    raise newException(
      ArtGenError,
      "Invalid size format. Width and height must be integers."
    )

proc gcdInt(a, b: int): int =
  ## Computes the greatest common divisor for positive integers.
  var
    x = abs(a)
    y = abs(b)
  while y != 0:
    let tmp = x mod y
    x = y
    y = tmp
  if x == 0:
    return 1
  x

proc toAspectRatio(width, height: int): string =
  ## Converts pixel dimensions to a reduced aspect ratio string.
  let g = gcdInt(width, height)
  $(width div g) & ":" & $(height div g)

proc ensureOutputDirectory(outputPath: string) =
  ## Creates the output directory if it does not already exist.
  let directory = outputPath.parentDir()
  if directory.len > 0 and directory != "." and not dirExists(directory):
    createDir(directory)

proc writeRenderedOutput*(outputPath: string, image: Image) =
  ## Writes one rendered PNG output, creating parent directories first.
  ensureOutputDirectory(outputPath)
  writeFile(outputPath, image.encodeImage(PngFormat))

proc decodeGeneratedImage(imageBytes: string): Image =
  ## Decodes generated image bytes into a Pixie image.
  try:
    decodeImage(imageBytes)
  except PixieError as err:
    raise newException(
      ArtGenError,
      "Failed to decode generated image: " & err.msg
    )

proc resizeAndCropImage(
  config: ArtGenConfig,
  source: Image,
  targetWidth, targetHeight: int,
  label: string
): Image =
  ## Applies cover-resize then centered crop to a target image size.
  logVerbose(
    config,
    "Applying resize/crop to " & label & " " &
    $targetWidth & "x" & $targetHeight & "."
  )
  if source.width <= 0 or source.height <= 0:
    raise newException(ArtGenError, "Generated image has invalid dimensions.")

  let
    widthScale = targetWidth.float / source.width.float
    heightScale = targetHeight.float / source.height.float
    coverScale = max(widthScale, heightScale)
    scaledWidth = max(1, int(ceil(source.width.float * coverScale)))
    scaledHeight = max(1, int(ceil(source.height.float * coverScale)))

  try:
    let resized = source.resize(scaledWidth, scaledHeight)
    let
      cropX = max(0, (scaledWidth - targetWidth) div 2)
      cropY = max(0, (scaledHeight - targetHeight) div 2)
    resized.subImage(cropX, cropY, targetWidth, targetHeight)
  except PixieError as err:
    raise newException(
      ArtGenError,
      "Failed to resize/crop generated image: " & err.msg
    )

proc createFallbackInspirationPng(width, height: int): string =
  ## Creates a blank PNG inspiration image for prompt-only generation.
  let image = newImage(max(1, width), max(1, height))
  image.encodeImage(PngFormat)

proc resolvePathCandidate(baseDir, pathText: string): string =
  ## Resolves a relative or absolute path candidate.
  let trimmed = pathText.strip()
  if trimmed.len == 0:
    return ""
  if trimmed.isAbsolute():
    return trimmed
  joinPath(baseDir, trimmed)

proc loadInspirationPng(
  config: ArtGenConfig,
  asset: ResolvedAsset
): (string, string) =
  ## Loads an explicit or inherited inspiration image, or creates a fallback.
  let sourceDir = asset.sourcePath.parentDir()
  for key in ["inspiration", "reference"]:
    if not asset.args.hasKey(key):
      continue
    let candidate = resolvePathCandidate(sourceDir, asset.args[key])
    if not fileExists(candidate):
      raise newException(
        ArtGenError,
        "Inspiration file does not exist: " & candidate
      )
    try:
      let image = readImage(candidate)
      return (image.encodeImage(PngFormat), candidate)
    except PixieError as err:
      raise newException(
        ArtGenError,
        "Failed to read inspiration image " & candidate & ": " & err.msg
      )

  let directoryChain = pathChain(config.inputDir, sourceDir)
  for i in countdown(directoryChain.high, 0):
    let candidate = joinPath(directoryChain[i], "_.png")
    if not fileExists(candidate):
      continue
    try:
      let image = readImage(candidate)
      return (image.encodeImage(PngFormat), candidate)
    except PixieError as err:
      raise newException(
        ArtGenError,
        "Failed to read inspiration image " & candidate & ": " & err.msg
      )

  let sizeText = asset.args.getOrDefault("size", "")
  let (width, height) = parseOutputSize(sizeText)
  let fallbackWidth = if width > 0: width else: 1024
  let fallbackHeight = if height > 0: height else: 1024
  (
    createFallbackInspirationPng(fallbackWidth, fallbackHeight),
    ""
  )

proc generateOpenAiImage(
  config: ArtGenConfig,
  model, prompt, inspirationPng, inspirationPath, generationSize: string
): string =
  ## Calls the OpenAI connector and returns generated image bytes.
  logVerbose(config, "Requesting image from OpenAI connector.")
  try:
    openAiConnection.createImage(
      model = model,
      prompt = prompt,
      inspirationImagePng = inspirationPng,
      inspirationPath = inspirationPath,
      verbose = config.verbose,
      size = generationSize,
      quality = "high",
      background = "opaque",
      outputFormat = "png",
      inputFidelity = "high",
      action = "edit"
    )
  except openAiConnection.OpenAiError as err:
    raise newException(
      ArtGenError,
      "OpenAI connector error: " & err.msg
    )

proc generateXaiImage(
  config: ArtGenConfig,
  model, prompt, inspirationPng, inspirationPath, generationSize, aspectRatio: string
): string =
  ## Calls the xAI connector and returns generated image bytes.
  logVerbose(config, "Requesting image from xAI connector.")
  try:
    xaiConnection.createImage(
      model = model,
      prompt = prompt,
      inspirationImagePng = inspirationPng,
      inspirationPath = inspirationPath,
      verbose = config.verbose,
      resolution = generationSize,
      aspectRatio = aspectRatio
    )
  except xaiConnection.XaiError as err:
    raise newException(
      ArtGenError,
      "xAI connector error: " & err.msg
    )

proc generateGeminiImage(
  config: ArtGenConfig,
  model, prompt, inspirationPng, inspirationPath, aspectRatio: string
): string =
  ## Calls the Gemini connector and returns generated image bytes.
  logVerbose(config, "Requesting image from Gemini connector.")
  try:
    geminiConnection.createImage(
      model = model,
      prompt = prompt,
      inspirationImagePng = inspirationPng,
      inspirationPath = inspirationPath,
      verbose = config.verbose,
      aspectRatio = aspectRatio
    )
  except geminiConnection.GeminiError as err:
    raise newException(
      ArtGenError,
      "Gemini connector error: " & err.msg
    )

proc generateStabilityImage(
  config: ArtGenConfig,
  model, prompt, inspirationPng, inspirationPath, generationSize, aspectRatio: string
): string =
  ## Calls the Stability connector and returns generated image bytes.
  logVerbose(config, "Requesting image from Stability connector.")
  let resolvedAspectRatio =
    if generationSize.strip().len > 0:
      generationSize.strip()
    else:
      aspectRatio
  try:
    stabilityConnection.createImage(
      model = model,
      prompt = prompt,
      inspirationImagePng = inspirationPng,
      inspirationPath = inspirationPath,
      verbose = config.verbose,
      aspectRatio = resolvedAspectRatio,
      outputFormat = "png"
    )
  except stabilityConnection.StabilityError as err:
    raise newException(
      ArtGenError,
      "Stability connector error: " & err.msg
    )

proc generateAsset(config: ArtGenConfig, asset: ResolvedAsset) =
  ## Generates one asset image, resizes it, and writes the final output.
  let format = asset.args.getOrDefault("format", "png").strip().toLowerAscii()
  if format != "png":
    raise newException(
      ArtGenError,
      "Only @format png is supported right now: " & asset.sourcePath
    )

  let providerText = asset.args.getOrDefault("provider", "").strip()
  if providerText.len == 0:
    raise newException(
      ArtGenError,
      "Missing @provider for asset: " & asset.sourcePath
    )
  let provider = parseProvider(providerText)
  let providerSettings = resolveProviderSettings(provider)
  let model = asset.args.getOrDefault(
    "model",
    providerSettings.defaultModel
  )
  if model.len == 0:
    raise newException(
      ArtGenError,
      "No default model exists for provider " & $provider & "."
    )

  let
    generationSize = asset.args.getOrDefault(
      "generationsize",
      providerSettings.defaultGenerationSize
    )
    directions = resolveDirections(asset.args.getOrDefault("directions", "1"))
    outputPaths = directionalOutputPaths(asset.outputPath, directions)
    sizeText = asset.args.getOrDefault("size", "")
    (targetWidth, targetHeight) = parseOutputSize(sizeText)
    aspectRatio =
      if targetWidth > 0 and targetHeight > 0:
        toAspectRatio(targetWidth, targetHeight)
      else:
        "1:1"

  if shouldSkipDirectionalOutputs(config.force, outputPaths):
    for outputPath in outputPaths:
      echo "Skipped existing output: ", outputPath
    return

  let
    conceptPath = prepareConceptPath(config, asset.outputPath)
    modelPath = modelOutputPath(config, asset.outputPath)
    reuse3d = shouldReuse3d(config, modelPath)

  var conceptPngBytes = ""
  if reuse3d:
    logVerbose(config, "Keeping existing model: " & modelPath)
  else:
    if shouldReuseConcept(config, conceptPath):
      conceptPngBytes = readFile(conceptPath)
      discard decodeGeneratedImage(conceptPngBytes)
      logVerbose(config, "Keeping existing concept: " & conceptPath)
    else:
      let (inspirationPng, inspirationPath) = loadInspirationPng(config, asset)
      let imageBytes = case provider
        of openai:
          generateOpenAiImage(
            config,
            model,
            asset.prompt,
            inspirationPng,
            inspirationPath,
            if generationSize.len > 0:
              generationSize
            else:
              OpenAiDefaultGenerationSize
          )
        of xai:
          generateXaiImage(
            config,
            model,
            asset.prompt,
            inspirationPng,
            inspirationPath,
            generationSize,
            aspectRatio
          )
        of gemini:
          generateGeminiImage(
            config,
            model,
            asset.prompt,
            inspirationPng,
            inspirationPath,
            aspectRatio
          )
        of stability:
          generateStabilityImage(
            config,
            model,
            asset.prompt,
            inspirationPng,
            inspirationPath,
            generationSize,
            aspectRatio
          )
        of claude:
          raise newException(
            ArtGenError,
            "Provider " & $provider & " is not implemented yet."
          )
      let
        conceptImage = decodeGeneratedImage(imageBytes)
        encodedConcept = conceptImage.encodeImage(PngFormat)
      conceptPngBytes = encodedConcept
      ensureOutputDirectory(conceptPath)
      writeFile(conceptPath, encodedConcept)
      logVerbose(config, "Wrote concept: " & conceptPath)

    let tripoResult = tripo3dConnection.createModel(
      imageBytes = conceptPngBytes,
      imagePath = conceptPath,
      verbose = config.verbose
    )
    ensureOutputDirectory(modelPath)
    writeFile(modelPath, tripoResult.modelData)
    logVerbose(config, "Wrote model: " & modelPath)

  for i, direction in directions:
    let outputPath = outputPaths[i]
    if not config.force and fileExists(outputPath):
      echo "Skipped existing output: ", outputPath
      continue

    let renderConfig = resolveGltfRenderConfig(
      asset,
      modelPath,
      outputPath,
      direction.rotYOffsetDeg
    )
    gltfRenderer.renderModel(renderConfig)
    logVerbose(config, "Rendered model view: " & outputPath)

    if targetWidth > 0 and targetHeight > 0 and (
      renderConfig.windowWidth != targetWidth or
      renderConfig.windowHeight != targetHeight
    ):
      try:
        let renderedImage = readImage(outputPath)
        let finalImage = resizeAndCropImage(
          config,
          renderedImage,
          targetWidth,
          targetHeight,
          splitFile(outputPath).name
        )
        writeRenderedOutput(outputPath, finalImage)
      except PixieError as err:
        raise newException(
          ArtGenError,
          "Failed to post-process rendered model image: " & err.msg
        )

    if not (
      targetWidth > 0 and targetHeight > 0 and (
        renderConfig.windowWidth != targetWidth or
        renderConfig.windowHeight != targetHeight
      )
    ):
      try:
        let renderedImage = readImage(outputPath)
        writeRenderedOutput(outputPath, renderedImage)
      except PixieError as err:
        raise newException(
          ArtGenError,
          "Failed to finalize rendered model image: " & err.msg
        )

    echo "Wrote sprite: ", outputPath
  return

proc parseCli(): ArtGenConfig =
  ## Parses command line options into an ArtGen config.
  result = defaultArtGenConfig()

  var parser = initOptParser(commandLineParams())
  while true:
    parser.next()
    case parser.kind
    of cmdEnd:
      break
    of cmdLongOption, cmdShortOption:
      let
        key = normalizeKey(parser.key)
        value = parser.val.strip()
      case key
      of "input", "i":
        result.inputDir = value
      of "output", "o":
        result.outputDir = value
      of "force", "f":
        result.force = true
      of "keep3d":
        result.keep3d = true
      of "keepconcept":
        result.keepConcept = true
      of "verbose", "v":
        result.verbose = true
      of "help", "h":
        echo "Usage:"
        echo "  nim r tools/artgen/artgen.nim [options]"
        echo ""
        echo "Options:"
        echo "  --input=DIR"
        echo "  --output=DIR"
        echo "  --force"
        echo "  --keep3d"
        echo "  --keepConcept"
        echo "  --verbose"
        quit(0)
      else:
        raise newException(
          ArtGenError,
          "Unknown option: --" & parser.key
        )
    of cmdArgument:
      raise newException(
        ArtGenError,
        "Unexpected argument: " & parser.key
      )

proc validateConfig(config: ArtGenConfig) =
  ## Validates that the input directory exists before processing.
  if config.inputDir.len == 0:
    raise newException(
      ArtGenError,
      "Missing input directory."
    )
  if not dirExists(config.inputDir):
    raise newException(
      ArtGenError,
      "Input directory does not exist: " & config.inputDir
    )

proc main() =
  ## Resolves all asset specs and generates output images.
  let config = parseCli()
  validateConfig(config)
  initializeArtgenSecrets()

  let assets = collectAssetFiles(config.inputDir)
  for assetPath in assets:
    let resolved = resolveAsset(config, assetPath)
    if config.verbose:
      printResolvedAsset(resolved)
    generateAsset(config, resolved)
  let indexPath = writeArttmpIndex(config)
  logVerbose(config, "Wrote arttmp index: " & indexPath)

when isMainModule:
  try:
    main()
  except ArtGenError as err:
    stderr.writeLine("[artgen] ", err.msg)
    quit(1)
