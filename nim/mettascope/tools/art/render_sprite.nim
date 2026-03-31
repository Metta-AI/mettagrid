import
  std/[math, os, parseopt, strformat, strutils, tables, times],
  chroma, gltf, opengl, pixie, silky, vmath, windy

type
  TextureKind* = enum
    baseColorTextureKind
    metallicRoughnessTextureKind
    normalTextureKind
    occlusionTextureKind
    emissiveTextureKind

  TextureColorSpace* = enum
    linearTextureColorSpace
    srgbTextureColorSpace

  ProjectionKind* = enum
    perspectiveProjection
    orthoProjection

  ViewerConfig* = object
    modelPath*: string
    projectionKind*: ProjectionKind
    rotXDeg*: float32
    rotYDeg*: float32
    rotZDeg*: float32
    zoom*: float32
    lightDirection*: Vec3
    lightColor*: Vec3
    lightStrength*: float32
    ambientLightColor*: Vec3
    ambientLightStrength*: float32
    rimLightColor*: Vec3
    rimLightStrength*: float32
    screenshotPath*: string
    quitAfterScreenshot*: bool
    transparentBackground*: bool
    screenshotMultisample*: int
    windowWidth*: int
    windowHeight*: int

  ViewerUiState* = object
    showControls*: bool
    lightColorText*: string
    ambientLightColorText*: string
    rimLightColorText*: string

  SceneState* = object
    model*: Mat4
    view*: Mat4
    proj*: Mat4
    cameraPosition*: Vec3
    cameraDolly*: float32

const
  DefaultLightDirection = vec3(-0.5'f32, -1.0'f32, -0.3'f32)
  VerticalFov = 45'f32
  FitPadding = 1.15'f32

proc parseColorOption(value, name: string): Vec3
proc buildInitialRotation(rxDeg, ryDeg, rzDeg: float32): Mat4

proc textureColorSpace*(kind: TextureKind): TextureColorSpace =
  ## Returns the color space expected for one texture kind.
  case kind
  of baseColorTextureKind, emissiveTextureKind:
    srgbTextureColorSpace
  of metallicRoughnessTextureKind, normalTextureKind, occlusionTextureKind:
    linearTextureColorSpace

proc resolveOcclusion*(sample, strength: float32): float32 =
  ## Blends occlusion strength the way glTF expects.
  mix(1.0'f32, sample, strength)

proc defaultViewerConfig*(): ViewerConfig =
  ## Returns the default viewer configuration.
  ViewerConfig(
    projectionKind: perspectiveProjection,
    rotXDeg: 0.0,
    rotYDeg: 0.0,
    rotZDeg: 0.0,
    zoom: 1.0,
    lightDirection: DefaultLightDirection,
    lightColor: vec3(1.0'f32, 1.0'f32, 1.0'f32),
    lightStrength: 1.0,
    ambientLightColor: vec3(0.12'f32, 0.12'f32, 0.14'f32),
    ambientLightStrength: 1.0,
    rimLightColor: vec3(0.55'f32, 0.60'f32, 0.75'f32),
    rimLightStrength: 1.0,
    screenshotPath: "",
    quitAfterScreenshot: false,
    transparentBackground: false,
    screenshotMultisample: 4,
    windowWidth: 1600,
    windowHeight: 1000
  )

proc defaultUiDataDir*(): string =
  ## Returns the absolute mettascope data directory for the GLTF UI.
  let toolDir = splitFile(currentSourcePath()).dir
  joinPath(toolDir.parentDir().parentDir(), "data")

proc defaultUiAtlasPath*(): string =
  ## Returns the absolute atlas path used by the GLTF UI.
  joinPath(defaultUiDataDir(), "silky.atlas.png")

proc shouldBuildUiAtlas*(): bool =
  ## Returns true when the GLTF viewer should rebuild the UI atlas.
  false

proc shouldShowUi*(config: ViewerConfig): bool =
  ## Returns true when the interactive Silky control UI should be shown.
  config.screenshotPath.len == 0

proc colorText(color: Vec3): string =
  ## Formats a color as uppercase HTML hex without '#'.
  Color(r: color.x, g: color.y, b: color.z, a: 1.0).toHex()

proc normalizeOrDefault(v, fallback: Vec3): Vec3 =
  ## Returns a normalized vector or a fallback when too small.
  if length(v) <= 0.000001:
    return normalize(fallback)
  normalize(v)

proc hasGeometry(node: Node): bool =
  ## Returns true when a node tree contains drawable geometry.
  if node == nil:
    return false
  if node.points.len > 0:
    return true
  for child in node.nodes:
    if child.hasGeometry():
      return true
  false

proc resolveSceneState*(
  config: ViewerConfig,
  center: Vec3,
  radius, aspectRatio: float32
): SceneState =
  ## Resolves model, view, projection, and camera position for one frame.
  let cameraDolly = max(2.0'f32, radius * 2.5'f32 / config.zoom)
  result.model = buildInitialRotation(
    config.rotXDeg,
    config.rotYDeg,
    config.rotZDeg
  ) * translate(-center)
  result.view = translate(vec3(0, 0, -cameraDolly))
  result.proj =
    case config.projectionKind
    of perspectiveProjection:
      perspective(
        45'f32,
        aspectRatio,
        0.01'f32,
        max(1000'f32, radius * 20)
      )
    of orthoProjection:
      let halfHeight = max(0.05'f32, radius * 1.5'f32 / config.zoom)
      let halfWidth = halfHeight * aspectRatio
      ortho(
        -halfWidth,
        halfWidth,
        -halfHeight,
        halfHeight,
        -max(1000'f32, radius * 20),
        max(1000'f32, radius * 20)
      )
  result.cameraPosition = inverse(result.view) * vec3(0, 0, 0)
  result.cameraDolly = cameraDolly

proc fitCameraDolly(bounds: Bounds, aspectRatio: float32): float32 =
  ## Returns a camera dolly distance that fits bounds on screen.
  if bounds.radius <= 0:
    return 4.0'f32

  let
    verticalHalfFov = VerticalFov.toRadians / 2.0'f32
    horizontalHalfFov = arctan(tan(verticalHalfFov) * aspectRatio)
    fitHalfFov = min(verticalHalfFov, horizontalHalfFov)
    fitDistance = bounds.radius / max(0.001'f32, sin(fitHalfFov))
  max(0.01'f32, fitDistance * FitPadding)

proc resolveModelSceneState(
  model: Node,
  config: ViewerConfig,
  baseCenter: Vec3,
  aspectRatio: float32
): SceneState =
  ## Resolves scene transforms by fitting the rotated model bounds.
  let zoom = max(0.05'f32, config.zoom)
  let rotatedModel =
    buildInitialRotation(
      config.rotXDeg,
      config.rotYDeg,
      config.rotZDeg
    ) * translate(-baseCenter)
  let rotatedBounds = model.computeBounds(rotatedModel)
  result.model = translate(-rotatedBounds.center) * rotatedModel

  let fittedBounds = model.computeBounds(result.model)
  let radius = max(0.5'f32, fittedBounds.radius)

  case config.projectionKind
  of perspectiveProjection:
    result.cameraDolly = fitCameraDolly(fittedBounds, aspectRatio) / zoom
    result.view = translate(vec3(0, 0, -result.cameraDolly))
    result.proj = perspective(
      VerticalFov,
      aspectRatio,
      0.01'f32,
      max(1000'f32, radius * 20.0'f32)
    )
  of orthoProjection:
    let
      halfWidth = fittedBounds.size.x * 0.5'f32 * FitPadding / zoom
      halfHeight = fittedBounds.size.y * 0.5'f32 * FitPadding / zoom
      orthoHalfHeight = max(
        0.05'f32,
        max(halfHeight, halfWidth / max(0.001'f32, aspectRatio))
      )
      orthoHalfWidth = orthoHalfHeight * aspectRatio
      depthHalf = max(1000'f32, radius * 20.0'f32)
    result.cameraDolly = max(2.0'f32, radius * 2.5'f32)
    result.view = translate(vec3(0, 0, -result.cameraDolly))
    result.proj = ortho(
      -orthoHalfWidth,
      orthoHalfWidth,
      -orthoHalfHeight,
      orthoHalfHeight,
      -depthHalf,
      depthHalf
    )

  result.cameraPosition = inverse(result.view) * vec3(0, 0, 0)

proc tryApplyColorText(text, name: string, target: var Vec3): string =
  ## Applies a color string to one target, returning an error when invalid.
  try:
    target = parseColorOption(text, name)
    ""
  except ValueError as err:
    err.msg

proc initViewerUiState*(config: ViewerConfig): ViewerUiState =
  ## Initializes editable UI state from the current viewer config.
  ViewerUiState(
    showControls: true,
    lightColorText: colorText(config.lightColor),
    ambientLightColorText: colorText(config.ambientLightColor),
    rimLightColorText: colorText(config.rimLightColor)
  )

proc applyViewerUiColorTexts*(
  ui: ViewerUiState,
  config: var ViewerConfig
): seq[string] =
  ## Applies UI color text fields back onto the live viewer config.
  let
    lightError = tryApplyColorText(
      ui.lightColorText,
      "light_color",
      config.lightColor
    )
    ambientError = tryApplyColorText(
      ui.ambientLightColorText,
      "ambient_light_color",
      config.ambientLightColor
    )
    rimError = tryApplyColorText(
      ui.rimLightColorText,
      "rim_light_color",
      config.rimLightColor
    )
  for err in [lightError, ambientError, rimError]:
    if err.len > 0:
      result.add err

proc drawViewerUi(
  sk: Silky,
  window: Window,
  ui: var ViewerUiState,
  config: var ViewerConfig,
  frameMs: float32
) =
  ## Draws the interactive Silky controls for the viewer.
  if ui.showControls:
    subWindow("GLTF Controls", ui.showControls, vec2(16, 16), vec2(360, 760)):
      text("Projection")
      radioButton("Perspective", config.projectionKind, perspectiveProjection)
      radioButton("Ortho", config.projectionKind, orthoProjection)

      text(&"Zoom: {config.zoom:>5.2f}")
      scrubber("zoom", config.zoom, 0.1'f32, 8.0'f32)

      text(&"Rot X: {config.rotXDeg:>6.2f}")
      scrubber("rotX", config.rotXDeg, -180.0'f32, 180.0'f32)
      text(&"Rot Y: {config.rotYDeg:>6.2f}")
      scrubber("rotY", config.rotYDeg, -180.0'f32, 180.0'f32)
      text(&"Rot Z: {config.rotZDeg:>6.2f}")
      scrubber("rotZ", config.rotZDeg, -180.0'f32, 180.0'f32)

      checkBox("Transparent background", config.transparentBackground)

      text("Light direction")
      text(&"Light X: {config.lightDirection.x:>5.2f}")
      scrubber("lightX", config.lightDirection.x, -2.0'f32, 2.0'f32)
      text(&"Light Y: {config.lightDirection.y:>5.2f}")
      scrubber("lightY", config.lightDirection.y, -2.0'f32, 2.0'f32)
      text(&"Light Z: {config.lightDirection.z:>5.2f}")
      scrubber("lightZ", config.lightDirection.z, -2.0'f32, 2.0'f32)

      text("Light color")
      textInput("lightColor", ui.lightColorText)
      let lightError = tryApplyColorText(
        ui.lightColorText,
        "light_color",
        config.lightColor
      )
      if lightError.len > 0:
        text(lightError)
      text(&"Light strength: {config.lightStrength:>5.2f}")
      scrubber("lightStrength", config.lightStrength, 0.0'f32, 10.0'f32)

      text("Ambient color")
      textInput("ambientColor", ui.ambientLightColorText)
      let ambientError = tryApplyColorText(
        ui.ambientLightColorText,
        "ambient_light_color",
        config.ambientLightColor
      )
      if ambientError.len > 0:
        text(ambientError)
      text(&"Ambient strength: {config.ambientLightStrength:>5.2f}")
      scrubber(
        "ambientStrength",
        config.ambientLightStrength,
        0.0'f32,
        2.0'f32
      )

      text("Rim color")
      textInput("rimColor", ui.rimLightColorText)
      let rimError = tryApplyColorText(
        ui.rimLightColorText,
        "rim_light_color",
        config.rimLightColor
      )
      if rimError.len > 0:
        text(rimError)
      text(&"Rim strength: {config.rimLightStrength:>5.2f}")
      scrubber("rimStrength", config.rimLightStrength, 0.0'f32, 4.0'f32)

      text(&"Frame: {frameMs:>6.2f} ms")
  else:
    button("Show Controls"):
      ui.showControls = true

proc ensureParentDirectory(path: string) =
  ## Creates the parent directory for an output file when needed.
  let directory = splitFile(path).dir
  if directory.len > 0 and not dirExists(directory):
    createDir(directory)

proc parseProjectionKind(text: string): ProjectionKind =
  ## Parses a projection mode from command line text.
  case text.strip().toLowerAscii()
  of "perspective", "perspectiveprojection":
    perspectiveProjection
  of "ortho", "orthographic", "orthoprojection":
    orthoProjection
  else:
    raise newException(
      ValueError,
      "Invalid projection. Use 'perspective' or 'ortho'."
    )

proc parseFloatOption(value, name: string): float32 =
  ## Parses one float32 command line option.
  try:
    parseFloat(value).float32
  except ValueError:
    raise newException(
      ValueError,
      "Invalid value for " & name & ": " & value
    )

proc parseBoolOption(value, name: string): bool =
  ## Parses one boolean option value.
  case value.strip().toLowerAscii()
  of "", "true", "1", "yes", "on":
    true
  of "false", "0", "no", "off":
    false
  else:
    raise newException(
      ValueError,
      "Invalid value for " & name & ": " & value
    )

proc buildInitialRotation(rxDeg, ryDeg, rzDeg: float32): Mat4 =
  ## Builds the initial camera rotation matrix from degrees.
  rotateX(rxDeg.toRadians) * rotateY(ryDeg.toRadians) * rotateZ(rzDeg.toRadians)

proc parseWindowSize(text: string): (int, int) =
  ## Parses a window size in WxH format.
  let clean = text.strip()
  let splitIndex = clean.find('x')
  if splitIndex <= 0 or splitIndex >= clean.len - 1:
    raise newException(
      ValueError,
      "Invalid window size. Use WxH, for example 1600x1000."
    )
  try:
    let
      width = parseInt(clean[0 ..< splitIndex])
      height = parseInt(clean[splitIndex + 1 .. ^1])
    if width <= 0 or height <= 0:
      raise newException(
        ValueError,
        "Window size must be greater than zero."
      )
    (width, height)
  except ValueError:
    raise newException(
      ValueError,
      "Invalid window size. Use WxH, for example 1600x1000."
    )

proc parsePositiveIntOption(value, name: string): int =
  ## Parses one positive integer command line option.
  try:
    let parsed = parseInt(value)
    if parsed <= 0:
      raise newException(
        ValueError,
        name & " must be greater than 0."
      )
    parsed
  except ValueError:
    raise newException(
      ValueError,
      "Invalid value for " & name & ": " & value
    )

proc getArg(
  args: Table[string, string],
  keys: openArray[string]
): string =
  ## Returns the first present argument value from a key list.
  for key in keys:
    if args.hasKey(key):
      return args[key]
  ""

proc parseVec3Option(value, name: string): Vec3 =
  ## Parses a vec3 option from `x,y,z` text.
  let
    normalized = value.strip().replace(" ", "")
    parts = normalized.split(',')
  if parts.len != 3:
    raise newException(
      ValueError,
      "Invalid value for " & name & ". Use x,y,z."
    )
  try:
    vec3(
      parseFloat(parts[0]).float32,
      parseFloat(parts[1]).float32,
      parseFloat(parts[2]).float32
    )
  except ValueError:
    raise newException(
      ValueError,
      "Invalid value for " & name & ". Use x,y,z."
    )

proc parseColorOption(value, name: string): Vec3 =
  ## Parses a color from `RRGGBB`, `#RRGGBB`, HTML colors, or `x,y,z`.
  let normalized = value.strip().replace(" ", "")
  if normalized.contains(','):
    return parseVec3Option(value, name)

  let colorTextValue =
    if normalized.len in [3, 4, 6, 8] and normalized[0] != '#':
      "#" & normalized
    else:
      normalized
  try:
    let parsed = parseHtmlColor(colorTextValue)
    vec3(parsed.r, parsed.g, parsed.b)
  except InvalidColor:
    raise newException(
      ValueError,
      "Invalid value for " & name &
      ". Use HTML color text like FFFFFF or #FFFFFF, or x,y,z."
    )

proc viewerConfigFromArgs*(
  args: Table[string, string],
  modelPath, screenshotPath: string,
  defaultWidth, defaultHeight: int
): ViewerConfig =
  ## Builds a viewer config from markdown-style render arguments.
  result = defaultViewerConfig()
  result.modelPath = modelPath
  result.screenshotPath = screenshotPath
  if screenshotPath.len > 0:
    result.quitAfterScreenshot = true
  if defaultWidth > 0:
    result.windowWidth = defaultWidth
  if defaultHeight > 0:
    result.windowHeight = defaultHeight

  let projectionText = getArg(args, ["projection"])
  if projectionText.len > 0:
    result.projectionKind = parseProjectionKind(projectionText)

  let rotXText = getArg(args, ["rotx"])
  if rotXText.len > 0:
    result.rotXDeg = parseFloatOption(rotXText, "@rotX")

  let rotYText = getArg(args, ["roty"])
  if rotYText.len > 0:
    result.rotYDeg = parseFloatOption(rotYText, "@rotY")

  let rotZText = getArg(args, ["rotz"])
  if rotZText.len > 0:
    result.rotZDeg = parseFloatOption(rotZText, "@rotZ")

  let zoomText = getArg(args, ["zoom"])
  if zoomText.len > 0:
    result.zoom = parseFloatOption(zoomText, "@zoom")

  let lightXText = getArg(args, ["lightx"])
  if lightXText.len > 0:
    result.lightDirection.x = parseFloatOption(lightXText, "@lightX")

  let lightYText = getArg(args, ["lighty"])
  if lightYText.len > 0:
    result.lightDirection.y = parseFloatOption(lightYText, "@lightY")

  let lightZText = getArg(args, ["lightz"])
  if lightZText.len > 0:
    result.lightDirection.z = parseFloatOption(lightZText, "@lightZ")

  let lightColorText = getArg(args, ["light_color"])
  if lightColorText.len > 0:
    result.lightColor = parseColorOption(lightColorText, "@light_color")

  let lightStrengthText = getArg(args, ["light_strength"])
  if lightStrengthText.len > 0:
    result.lightStrength = parseFloatOption(
      lightStrengthText,
      "@light_strength"
    )

  let ambientColorText = getArg(args, ["ambient_light_color", "ambient_light"])
  if ambientColorText.len > 0:
    result.ambientLightColor = parseColorOption(
      ambientColorText,
      "@ambient_light_color"
    )

  let ambientStrengthText = getArg(args, ["ambient_light_strength"])
  if ambientStrengthText.len > 0:
    result.ambientLightStrength = parseFloatOption(
      ambientStrengthText,
      "@ambient_light_strength"
    )

  let rimColorText = getArg(args, ["rim_light_color"])
  if rimColorText.len > 0:
    result.rimLightColor = parseColorOption(
      rimColorText,
      "@rim_light_color"
    )

  let rimStrengthText = getArg(
    args,
    ["rim_light_strength", "rim_light"]
  )
  if rimStrengthText.len > 0:
    result.rimLightStrength = parseFloatOption(
      rimStrengthText,
      "@rim_light_strength"
    )

  let windowText = getArg(args, ["window"])
  if windowText.len > 0:
    let (width, height) = parseWindowSize(windowText)
    result.windowWidth = width
    result.windowHeight = height

  let multisampleText = getArg(args, ["multisample"])
  if multisampleText.len > 0:
    result.screenshotMultisample = parsePositiveIntOption(
      multisampleText,
      "@multisample"
    )

  let quitText = getArg(args, ["quit"])
  if quitText.len > 0:
    result.quitAfterScreenshot = parseBoolOption(quitText, "@quit")

  let transparentText = getArg(args, ["transparent"])
  if transparentText.len > 0:
    result.transparentBackground = parseBoolOption(
      transparentText,
      "@transparent"
    )

proc drawFrame(
  model: Node,
  config: ViewerConfig,
  sceneState: SceneState,
  sunLightDirection: Vec3,
  sunLightColor: Color,
  ambientLightColor: Color,
  rimLightDirection: Vec3,
  rimLightColor: Color,
  width, height: int
) =
  ## Draws one frame using the shared glTF PBR renderer.
  glViewport(0, 0, width.GLsizei, height.GLsizei)
  if config.transparentBackground:
    glClearColor(0.0, 0.0, 0.0, 0.0)
  else:
    glClearColor(0.10, 0.10, 0.11, 1.0)
  glClear(GL_COLOR_BUFFER_BIT or GL_DEPTH_BUFFER_BIT)
  glEnable(GL_MULTISAMPLE)
  glCullFace(GL_BACK)
  glFrontFace(GL_CCW)
  glEnable(GL_CULL_FACE)
  glEnable(GL_DEPTH_TEST)
  glDepthMask(GL_TRUE)

  if model.hasGeometry():
    model.drawPbrWithShadow(
      sceneState.model,
      sceneState.view,
      sceneState.proj,
      tint = color(1, 1, 1, 1),
      sunLightDirection = sunLightDirection,
      useTrs = true,
      ambientLightColor = ambientLightColor,
      sunLightColor = sunLightColor,
      rimLightDirection = rimLightDirection,
      rimLightColor = rimLightColor,
      cameraPosition = sceneState.cameraPosition
    )

proc captureOffscreenScreenshot(
  path: string,
  width, height: int,
  screenshotMultisample: int,
  model: Node,
  config: ViewerConfig,
  sceneState: SceneState,
  sunLightDirection: Vec3,
  sunLightColor: Color,
  ambientLightColor: Color,
  rimLightDirection: Vec3,
  rimLightColor: Color
) =
  ## Renders to a larger offscreen RGBA framebuffer and downscales it.
  let
    offscreenWidth = width * screenshotMultisample
    offscreenHeight = height * screenshotMultisample
  var
    previousFbo: GLint
    framebuffer: GLuint
    colorTexture: GLuint
    depthRenderbuffer: GLuint
  glGetIntegerv(GL_FRAMEBUFFER_BINDING, previousFbo.addr)

  glGenFramebuffers(1, framebuffer.addr)
  glBindFramebuffer(GL_FRAMEBUFFER, framebuffer)

  glGenTextures(1, colorTexture.addr)
  glBindTexture(GL_TEXTURE_2D, colorTexture)
  glTexImage2D(
    GL_TEXTURE_2D,
    0,
    GL_RGBA8.GLint,
    offscreenWidth.GLsizei,
    offscreenHeight.GLsizei,
    0,
    GL_RGBA,
    GL_UNSIGNED_BYTE,
    nil
  )
  glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
  glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
  glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE)
  glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE)
  glFramebufferTexture2D(
    GL_FRAMEBUFFER,
    GL_COLOR_ATTACHMENT0,
    GL_TEXTURE_2D,
    colorTexture,
    0
  )

  glGenRenderbuffers(1, depthRenderbuffer.addr)
  glBindRenderbuffer(GL_RENDERBUFFER, depthRenderbuffer)
  glRenderbufferStorage(
    GL_RENDERBUFFER,
    GL_DEPTH_COMPONENT24,
    offscreenWidth.GLsizei,
    offscreenHeight.GLsizei
  )
  glFramebufferRenderbuffer(
    GL_FRAMEBUFFER,
    GL_DEPTH_ATTACHMENT,
    GL_RENDERBUFFER,
    depthRenderbuffer
  )

  let status = glCheckFramebufferStatus(GL_FRAMEBUFFER)
  if status != GL_FRAMEBUFFER_COMPLETE:
    glBindFramebuffer(GL_FRAMEBUFFER, previousFbo.GLuint)
    raise newException(
      ValueError,
      "Offscreen framebuffer incomplete: " & $status.int
    )

  drawFrame(
    model,
    config,
    sceneState,
    sunLightDirection,
    sunLightColor,
    ambientLightColor,
    rimLightDirection,
    rimLightColor,
    offscreenWidth,
    offscreenHeight
  )
  glFinish()

  var pixels = newSeq[uint8](offscreenWidth * offscreenHeight * 4)
  glPixelStorei(GL_PACK_ALIGNMENT, 1)
  glReadPixels(
    0,
    0,
    offscreenWidth.GLsizei,
    offscreenHeight.GLsizei,
    GL_RGBA,
    GL_UNSIGNED_BYTE,
    pixels[0].addr
  )
  if config.transparentBackground:
    for i in countup(0, pixels.len - 4, 4):
      if pixels[i + 3] == 0:
        pixels[i + 0] = 0
        pixels[i + 1] = 0
        pixels[i + 2] = 0

  var image = newImage(offscreenWidth, offscreenHeight)
  for y in 0 ..< offscreenHeight:
    let srcY = offscreenHeight - 1 - y
    for x in 0 ..< offscreenWidth:
      let
        srcIndex = (srcY * offscreenWidth + x) * 4
        dstIndex = y * offscreenWidth + x
      image.data[dstIndex] = rgbx(
        pixels[srcIndex + 0],
        pixels[srcIndex + 1],
        pixels[srcIndex + 2],
        pixels[srcIndex + 3]
      )
  let resized =
    if screenshotMultisample > 1:
      image.resize(width, height)
    else:
      image
  ensureParentDirectory(path)
  writeFile(path, resized.encodeImage(PngFormat))

  glBindFramebuffer(GL_FRAMEBUFFER, previousFbo.GLuint)
  glDeleteRenderbuffers(1, depthRenderbuffer.addr)
  glDeleteTextures(1, colorTexture.addr)
  glDeleteFramebuffers(1, framebuffer.addr)

proc parseCli(): ViewerConfig =
  ## Parses command line options into a viewer config.
  result = defaultViewerConfig()

  var parser = initOptParser(commandLineParams())
  while true:
    parser.next()
    case parser.kind
    of cmdEnd:
      break
    of cmdArgument:
      if result.modelPath.len == 0:
        result.modelPath = parser.key
      else:
        raise newException(
          ValueError,
          "Unexpected extra argument: " & parser.key
        )
    of cmdLongOption, cmdShortOption:
      let
        key = parser.key.strip().toLowerAscii()
        value = parser.val.strip()
      case key
      of "projection", "proj":
        result.projectionKind = parseProjectionKind(value)
      of "rotx", "rx":
        result.rotXDeg = parseFloatOption(value, "--rotX")
      of "roty", "ry":
        result.rotYDeg = parseFloatOption(value, "--rotY")
      of "rotz", "rz":
        result.rotZDeg = parseFloatOption(value, "--rotZ")
      of "zoom", "z":
        result.zoom = parseFloatOption(value, "--zoom")
        if result.zoom <= 0:
          raise newException(
            ValueError,
            "--zoom must be greater than 0."
          )
      of "lightx":
        result.lightDirection.x = parseFloatOption(value, "--lightX")
      of "lighty":
        result.lightDirection.y = parseFloatOption(value, "--lightY")
      of "lightz":
        result.lightDirection.z = parseFloatOption(value, "--lightZ")
      of "light_color":
        result.lightColor = parseColorOption(value, "--light_color")
      of "light_strength":
        result.lightStrength = parseFloatOption(value, "--light_strength")
      of "ambient_light_color", "ambient_light":
        result.ambientLightColor =
          parseColorOption(value, "--ambient_light_color")
      of "ambient_light_strength":
        result.ambientLightStrength =
          parseFloatOption(value, "--ambient_light_strength")
      of "rim_light_color":
        result.rimLightColor = parseColorOption(value, "--rim_light_color")
      of "rim_light", "rim_light_strength":
        result.rimLightStrength =
          parseFloatOption(value, "--rim_light_strength")
      of "screenshot":
        result.screenshotPath = value
      of "quit":
        result.quitAfterScreenshot = true
      of "transparent":
        result.transparentBackground = true
      of "window", "size":
        let (width, height) = parseWindowSize(value)
        result.windowWidth = width
        result.windowHeight = height
      of "multisample":
        result.screenshotMultisample =
          parsePositiveIntOption(value, "--multisample")
      of "help", "h":
        echo "Usage:"
        echo "  nim r tools/art/render_sprite.nim [options] path/to/model.glb"
        echo ""
        echo "Options:"
        echo "  --projection=perspective|ortho"
        echo "  --rotX=DEGREES"
        echo "  --rotY=DEGREES"
        echo "  --rotZ=DEGREES"
        echo "  --zoom=NUMBER"
        echo "  --lightX=NUMBER"
        echo "  --lightY=NUMBER"
        echo "  --lightZ=NUMBER"
        echo "  --light_color=R,G,B|#RRGGBB|RRGGBB"
        echo "  --light_strength=NUMBER"
        echo "  --ambient_light_color=R,G,B|#RRGGBB|RRGGBB"
        echo "  --ambient_light_strength=NUMBER"
        echo "  --rim_light_color=R,G,B|#RRGGBB|RRGGBB"
        echo "  --rim_light_strength=NUMBER"
        echo "  --window=WxH"
        echo "  --multisample=NUMBER"
        echo "  --screenshot=FILE.png"
        echo "  --quit"
        echo "  --transparent"
        quit(0)
      else:
        raise newException(
          ValueError,
          "Unknown option: --" & parser.key
        )

  if result.modelPath.len == 0:
    raise newException(
      ValueError,
      "Usage: nim r tools/art/render_sprite.nim [options] path/to/model.glb"
    )
  if not fileExists(result.modelPath):
    raise newException(
      ValueError,
      "File does not exist: " & result.modelPath
    )

proc renderModel*(config: ViewerConfig) =
  ## Opens a window and renders the requested glTF model.
  if config.modelPath.len == 0:
    raise newException(ValueError, "Missing model path.")
  if not fileExists(config.modelPath):
    raise newException(
      ValueError,
      "File does not exist: " & config.modelPath
    )
  if config.windowWidth <= 0 or config.windowHeight <= 0:
    raise newException(
      ValueError,
      "Window size must be greater than zero."
    )
  if config.screenshotMultisample <= 0:
    raise newException(
      ValueError,
      "Screenshot multisample must be greater than zero."
    )

  var window = newWindow(
    "GLTF Viewer - " & extractFilename(config.modelPath),
    ivec2(config.windowWidth.int32, config.windowHeight.int32),
    visible = shouldShowUi(config),
    msaa = msaa8x
  )
  makeContextCurrent(window)
  loadExtensions()
  setupPbr()
  loadDefaultEnvironmentMap()

  var
    currentConfig = config
    uiState = initViewerUiState(config)
    sk: Silky
  if shouldShowUi(config):
    sk = newSilky(window, defaultUiAtlasPath())
    window.runeInputEnabled = true
    window.onRune = proc(rune: Rune) =
      sk.inputRunes.add(rune)

  var model = loadModel(config.modelPath)
  let bounds = model.computeBounds()
  let center = bounds.center
  var
    wroteScreenshot = false
    lastTime = epochTime()

  while not window.closeRequested:
    let nowTime = epochTime()
    let dt = max(0.0'f32, (nowTime - lastTime).float32)
    lastTime = nowTime

    pollEvents()

    if model != nil:
      model.updateAnimation(dt)

    if window.buttonDown[MouseMiddle]:
      if window.buttonDown[MouseRight]:
        let speed = 300.0'f32
        currentConfig.rotZDeg +=
          (window.mouseDelta.x.float32 / speed) *
          (180.0'f32 / PI.float32)
      else:
        let speed = 300.0'f32
        currentConfig.rotYDeg +=
          (-window.mouseDelta.x.float32 / speed) *
          (180.0'f32 / PI.float32)
        currentConfig.rotXDeg +=
          (-window.mouseDelta.y.float32 / speed) *
          (180.0'f32 / PI.float32)

    if window.scrollDelta.y > 0:
      currentConfig.zoom *= 1.1
    elif window.scrollDelta.y < 0:
      currentConfig.zoom *= 0.9
    currentConfig.zoom = max(0.05'f32, currentConfig.zoom)

    let aspectRatio = window.size.x.float32 / max(1, window.size.y).float32
    let
      sunLightDirection = normalizeOrDefault(
        currentConfig.lightDirection,
        DefaultLightDirection
      )
      sunLightColor = color(
        currentConfig.lightColor.x,
        currentConfig.lightColor.y,
        currentConfig.lightColor.z,
        currentConfig.lightStrength
      )
      ambientLightColor = color(
        currentConfig.ambientLightColor.x,
        currentConfig.ambientLightColor.y,
        currentConfig.ambientLightColor.z,
        currentConfig.ambientLightStrength
      )
      rimLightDirection = -sunLightDirection
      rimLightColor = color(
        currentConfig.rimLightColor.x,
        currentConfig.rimLightColor.y,
        currentConfig.rimLightColor.z,
        currentConfig.rimLightStrength
      )
      sceneState = resolveModelSceneState(
        model,
        currentConfig,
        center,
        aspectRatio
      )

    drawFrame(
      model,
      currentConfig,
      sceneState,
      sunLightDirection,
      sunLightColor,
      ambientLightColor,
      rimLightDirection,
      rimLightColor,
      window.size.x,
      window.size.y
    )

    if currentConfig.screenshotPath.len > 0 and not wroteScreenshot:
      captureOffscreenScreenshot(
        currentConfig.screenshotPath,
        window.size.x,
        window.size.y,
        currentConfig.screenshotMultisample,
        model,
        currentConfig,
        sceneState,
        sunLightDirection,
        sunLightColor,
        ambientLightColor,
        rimLightDirection,
        rimLightColor
      )
      wroteScreenshot = true
      if currentConfig.quitAfterScreenshot:
        break

    if shouldShowUi(currentConfig):
      glDisable(GL_DEPTH_TEST)
      glDisable(GL_CULL_FACE)
      glDisable(GL_BLEND)
      sk.beginUI(window, window.size)
      drawViewerUi(sk, window, uiState, currentConfig, dt * 1000)
      sk.endUi()

    window.swapBuffers()

proc main() =
  ## Runs the command line GLTF renderer.
  renderModel(parseCli())

when isMainModule:
  main()
