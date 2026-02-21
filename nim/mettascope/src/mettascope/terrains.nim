import
  std/[math, random, os, strutils],
  opengl, windy, silky/shaders, shady, vmath,
  common, tilemap, pixelator, shaderquad

const
  TileSize = 128
  Ts = 1.0 / TileSize.float32

type
  SplatPassTarget* = enum
    MaskPass
    SplatPass

  SplatComposite* = ref object
    shader: Shader
    vao: GLuint
    fbo: GLuint
    maskTex*: GLuint
    splatTex*: GLuint
    width*: int
    height*: int

var
  terrainMap*: TileMap
  maskMap*: TileMap
  splatSandQuad*: ShaderQuad
  splatCompositePass*: SplatComposite
  splats*: seq[tuple[sprite: string, pos: IVec2]]

  uMvp: Uniform[Mat4]
  uMapSize: Uniform[Vec2]
  uMaskTexture: Uniform[Sampler2D]
  uSplatTexture: Uniform[Sampler2D]

proc weightedRandomInt(weights: seq[int]): int =
  var r = rand(sum(weights))
  var acc = 0
  for i, w in weights:
    acc += w
    if r <= acc:
      return i
  doAssert false, "should not happen"

const patternToTile = @[
  18, 17, 4, 4, 12, 22, 4, 4, 30, 13, 41, 41, 30, 13, 41, 41, 19, 23, 5, 5, 37,
  9, 5, 5, 30, 13, 41, 41, 30, 13, 41, 41, 24, 43, 39, 39, 44, 45, 39, 39, 48,
  32, 46, 46, 48, 32, 46, 46, 24, 43, 39, 39, 44, 45, 39, 39, 48, 32, 46, 46,
  48, 32, 46, 46, 36, 10, 3, 3, 16, 40, 3, 3, 20, 27, 6, 6, 20, 27, 6, 6, 25,
  15, 2, 2, 26, 38, 2, 2, 20, 27, 6, 6, 20, 27, 6, 6, 24, 43, 39, 39, 44, 45,
  39, 39, 48, 32, 46, 46, 48, 32, 46, 46, 24, 43, 39, 39, 44, 45, 39, 39, 48,
  32, 46, 46, 48, 32, 46, 46, 28, 28, 8, 8, 21, 21, 8, 8, 33, 33, 7, 7, 33, 33,
  7, 7, 35, 35, 31, 31, 14, 14, 31, 31, 33, 33, 7, 7, 33, 33, 7, 7, 47, 47, 1,
  1, 42, 42, 1, 1, 34, 34, 0, 0, 34, 34, 0, 0, 47, 47, 1, 1, 42, 42, 1, 1,
  34, 34, 0, 0, 34, 34, 0, 0, 28, 28, 8, 8, 21, 21, 8, 8, 33, 33, 7, 7, 33,
  33, 7, 7, 35, 35, 31, 31, 14, 14, 31, 31, 33, 33, 7, 7, 33, 33, 7, 7, 47, 47,
  1, 1, 42, 42, 1, 1, 34, 34, 0, 0, 34, 34, 0, 0, 47, 47, 1, 1, 42, 42, 1,
  1, 34, 34, 0, 0, 34, 34, 0, 0
]

proc generateTerrainMap(atlasPath: string): TileMap =
  let
    width = ceil(replay.mapSize[0].float32 / 32.0f).int * 32
    height = ceil(replay.mapSize[1].float32 / 32.0f).int * 32

  var tileMap = newTileMap(
    width = width,
    height = height,
    tileSize = 128,
    atlasPath = atlasPath
  )
  let
    tilesPerRow = tileMap.tileAtlas.width div tileMap.tileSize
    tilesPerCol = tileMap.tileAtlas.height div tileMap.tileSize
    maxTileIndex = max(0, tilesPerRow * tilesPerCol - 1)

  var asteroidMap: seq[bool] = newSeq[bool](width * height)
  for y in 0 ..< height:
    for x in 0 ..< width:
      asteroidMap[y * width + x] = x >= replay.mapSize[0] or y >= replay.mapSize[1]

  for obj in replay.objects:
    if obj.typeName == "wall":
      let pos = obj.location.at(0)
      asteroidMap[pos.y * width + pos.x] = true

  for i in 0 ..< tileMap.indexData.len:
    let x = i mod width
    let y = i div width

    proc get(map: seq[bool], x: int, y: int): int =
      if x < 0 or y < 0 or x >= width or y >= height: return 1
      if map[y * width + x]: return 1
      0

    var tile: uint8 = 0
    if asteroidMap[y * width + x]:
      tile = min(49, maxTileIndex).uint8
    else:
      let pattern = (
        1 * asteroidMap.get(x-1, y-1) +
        2 * asteroidMap.get(x, y-1) +
        4 * asteroidMap.get(x+1, y-1) +
        8 * asteroidMap.get(x+1, y) +
        16 * asteroidMap.get(x+1, y+1) +
        32 * asteroidMap.get(x, y+1) +
        64 * asteroidMap.get(x-1, y+1) +
        128 * asteroidMap.get(x-1, y)
      )
      tile = min(patternToTile[pattern], maxTileIndex).uint8
    tileMap.indexData[i] = tile

  for j in 0 ..< tileMap.indexData.len:
    if tileMap.indexData[j] == 29 or tileMap.indexData[j] == 18:
      tileMap.indexData[j] = min(50, maxTileIndex).uint8

  tileMap.setupGPU()
  tileMap

proc stampForTypeName(typeName: string): string =
  let normalized = normalizeTypeName(typeName)
  if normalized.contains("carbon_extractor"): return "terrain/stamp.carbon"
  if normalized.contains("germanium_extractor"): return "terrain/stamp.germanium"
  if normalized.contains("germenium_extractor"): return "terrain/stamp.germenium"
  if normalized.contains("silicon_extractor"): return "terrain/stamp.silicon"
  if normalized.contains("oxygen_extractor"): return "terrain/stamp.oxygen"
  if normalized == "junction": return "terrain/stamp.junction"
  if normalized == "hub": return "terrain/stamp.hub"
  ""

proc rebuildSplats*() =
  splats.setLen(0)
  if replay.isNil: return

  for obj in replay.objects:
    let stamp = stampForTypeName(obj.typeName)
    if stamp.len == 0: continue

    var firstAliveStep = -1
    for s in 0 ..< min(replay.maxSteps, obj.alive.len):
      if obj.alive[s]:
        firstAliveStep = s
        break
    if firstAliveStep < 0 or obj.location.len == 0:
      continue

    splats.add((sprite: stamp, pos: obj.location.at(firstAliveStep).xy * TileSize))

proc resetTerrainCaches*() =
  terrainMap = nil
  maskMap = nil
  splatSandQuad = nil
  splatCompositePass = nil
  splats.setLen(0)

proc drawTerrain*(mvp: Mat4, px: var Pixelator, pxMini: var Pixelator) =
  if terrainMap == nil:
    terrainMap = generateTerrainMap(dataDir / "terrain/blob7x8.png")
    px = newPixelator(dataDir / "atlas.png", dataDir / "atlas.json")
    pxMini = newPixelator(dataDir / "atlas_mini.png", dataDir / "atlas_mini.json")
  terrainMap.draw(mvp, 2.0f, 1.5f)

proc drawMask*(mvp: Mat4) =
  if maskMap == nil:
    maskMap = generateTerrainMap(dataDir / "terrain/mask7x8.png")
  maskMap.draw(mvp, 2.0f, 1.5f)

proc drawSplats*(mvp: Mat4, px: Pixelator) =
  if px == nil or replay.isNil:
    return

  proc firstSprite(candidates: openArray[string]): string =
    for name in candidates:
      if name in px:
        return name
    ""

  if splatSandQuad == nil:
    splatSandQuad = newGridQuad(dataDir / "terrain/repeating.sand.png", 1, 1)
  let sandImageSize = splatSandQuad.imageSize()
  let sandTileSpan = vec2(
    max(1.0f, sandImageSize.x.float32 / TileSize.float32),
    max(1.0f, sandImageSize.y.float32 / TileSize.float32)
  )
  splatSandQuad.draw(
    mvp = mvp,
    mapSize = vec2(replay.mapSize[0].float32, replay.mapSize[1].float32),
    tileSize = sandTileSpan,
    gridColor = vec4(1.0f, 1.0f, 1.0f, 1.0f)
  )

  for splat in splats:
    let stamp = firstSprite(@[splat.sprite])
    if stamp.len == 0:
      continue
    px.drawSprite(stamp, splat.pos)

proc maskedSplatVert*(fragmentWorldPos: var Vec2, fragmentUv: var Vec2) =
  let corner = ivec2(gl_VertexID mod 2, gl_VertexID div 2)
  let worldPos = vec2(
    float(corner.x) * uMapSize.x - 0.5,
    float(corner.y) * uMapSize.y - 0.5
  )
  fragmentWorldPos = worldPos
  gl_Position = uMvp * vec4(worldPos.x, worldPos.y, 0.0f, 1.0f)
  let ndc = gl_Position.xy / gl_Position.w
  fragmentUv = (ndc + vec2(1.0f, 1.0f)) * 0.5f

proc maskedSplatFrag*(fragmentWorldPos: Vec2, fragmentUv: Vec2, fragColor: var Vec4) =
  let maskSample = texture(uMaskTexture, fragmentUv)
  let splatSample = texture(uSplatTexture, fragmentUv)
  fragColor = splatSample * maskSample.r

proc newSplatComposite*(): SplatComposite =
  result = SplatComposite()
  when defined(emscripten):
    result.shader = newShader(
      ("maskedSplatVert", toGLSL(maskedSplatVert, glslES3)),
      ("maskedSplatFrag", toGLSL(maskedSplatFrag, glslES3))
    )
  else:
    result.shader = newShader(
      ("maskedSplatVert", toGLSL(maskedSplatVert, glslDesktop)),
      ("maskedSplatFrag", toGLSL(maskedSplatFrag, glslDesktop))
    )

  glGenVertexArrays(1, result.vao.addr)
  glBindVertexArray(result.vao)
  glBindVertexArray(0)
  glGenFramebuffers(1, result.fbo.addr)

proc initPassTexture(tex: GLuint, width, height: int) =
  glBindTexture(GL_TEXTURE_2D, tex)
  glTexImage2D(
    GL_TEXTURE_2D, 0, GL_RGBA8.GLint, width.GLint, height.GLint, 0, GL_RGBA, GL_UNSIGNED_BYTE, nil
  )
  glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR.GLint)
  glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR.GLint)
  glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE.GLint)
  glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE.GLint)
  glBindTexture(GL_TEXTURE_2D, 0)

proc ensureTargetsSize*(sc: SplatComposite, width, height: int) =
  if sc.isNil or width <= 0 or height <= 0:
    return
  if sc.width == width and sc.height == height and sc.maskTex != 0 and sc.splatTex != 0:
    return

  if sc.maskTex != 0:
    glDeleteTextures(1, sc.maskTex.addr)
    sc.maskTex = 0
  if sc.splatTex != 0:
    glDeleteTextures(1, sc.splatTex.addr)
    sc.splatTex = 0

  glGenTextures(1, sc.maskTex.addr)
  initPassTexture(sc.maskTex, width, height)
  glGenTextures(1, sc.splatTex.addr)
  initPassTexture(sc.splatTex, width, height)
  sc.width = width
  sc.height = height

proc beginPass*(
  sc: SplatComposite,
  target: SplatPassTarget,
  previousFbo: var GLint,
  previousViewport: var array[4, GLint]
) =
  if sc.isNil:
    return

  glGetIntegerv(GL_FRAMEBUFFER_BINDING, previousFbo.addr)
  glGetIntegerv(GL_VIEWPORT, previousViewport[0].addr)

  glBindFramebuffer(GL_FRAMEBUFFER, sc.fbo)
  let textureTarget = if target == MaskPass: sc.maskTex else: sc.splatTex
  glFramebufferTexture2D(GL_FRAMEBUFFER, GL_COLOR_ATTACHMENT0, GL_TEXTURE_2D, textureTarget, 0)
  let status = glCheckFramebufferStatus(GL_FRAMEBUFFER)
  doAssert status == GL_FRAMEBUFFER_COMPLETE, "Splat composite framebuffer incomplete: " & $status.int

  glViewport(0, 0, sc.width.GLint, sc.height.GLint)
  glClearColor(0, 0, 0, 0)
  glClear(GL_COLOR_BUFFER_BIT)

proc endPass*(sc: SplatComposite, previousFbo: GLint, previousViewport: array[4, GLint]) =
  if sc.isNil:
    return
  glBindFramebuffer(GL_FRAMEBUFFER, previousFbo.GLuint)
  glViewport(previousViewport[0], previousViewport[1], previousViewport[2], previousViewport[3])

proc drawComposite*(sc: SplatComposite, mvp: Mat4, mapSize: Vec2) =
  if sc.isNil or sc.maskTex == 0 or sc.splatTex == 0:
    return

  glUseProgram(sc.shader.programId)
  sc.shader.setUniform("uMvp", mvp)
  sc.shader.setUniform("uMapSize", mapSize)

  glActiveTexture(GL_TEXTURE0)
  glBindTexture(GL_TEXTURE_2D, sc.maskTex)
  sc.shader.setUniform("uMaskTexture", 0)

  glActiveTexture(GL_TEXTURE1)
  glBindTexture(GL_TEXTURE_2D, sc.splatTex)
  sc.shader.setUniform("uSplatTexture", 1)
  sc.shader.bindUniforms()

  glBindVertexArray(sc.vao)
  glDrawArrays(GL_TRIANGLE_STRIP, 0, 4)
  glBindVertexArray(0)
  glUseProgram(0)

proc drawMaskedSplatComposite*(mvp: Mat4, px: Pixelator) =
  if replay.isNil:
    return
  if splatCompositePass == nil:
    splatCompositePass = newSplatComposite()
  splatCompositePass.ensureTargetsSize(window.size.x.int, window.size.y.int)
  if splatCompositePass.width <= 0 or splatCompositePass.height <= 0:
    return

  var
    previousFbo: GLint = 0
    previousViewport: array[4, GLint]

  splatCompositePass.beginPass(MaskPass, previousFbo, previousViewport)
  drawMask(mvp)
  splatCompositePass.endPass(previousFbo, previousViewport)

  splatCompositePass.beginPass(SplatPass, previousFbo, previousViewport)
  drawSplats(mvp, px)
  px.flush(mvp * scale(vec3(Ts, Ts, 1.0f)))
  splatCompositePass.endPass(previousFbo, previousViewport)

  splatCompositePass.drawComposite(
    mvp = mvp,
    mapSize = vec2(replay.mapSize[0].float32, replay.mapSize[1].float32)
  )
