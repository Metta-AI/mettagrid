import
  std/[math, random, os, strutils],
  opengl, windy, silky/drawers/ogl, shady, vmath, chroma,
  ../common,
  ./[tilemap, pixelator, shaderquad]

const
  TileSize = 128
  Ts = 1.0 / TileSize.float32
  SplatMinSpacingPx = 500.0f
  SplatMaxPlacementAttempts = 100
  SplatDensityAreaPerSpritePx = 500_000.0f
  RandomSplatSprites = @[
    "terrain/splat1",
    "terrain/splat2",
    "terrain/splat3",
    "terrain/splat4",
    "terrain/splat5",
    "terrain/splat6",
    "terrain/splat7",
    "terrain/splat8"
  ]

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

proc stampForTypeName(typeName: string): tuple[sprite: string, offset: IVec2] =
  let normalized = normalizeTypeName(typeName)
  case normalized
  of "carbon_extractor":
    (sprite: "terrain/stamp.carbon", offset: ivec2(0, 0))
  of "germanium_extractor":
    (sprite: "terrain/stamp.germanium", offset: ivec2(0, 0))
  of "germenium_extractor":
    (sprite: "terrain/stamp.germenium", offset: ivec2(0, 0))
  of "silicon_extractor":
    (sprite: "terrain/stamp.silicon", offset: ivec2(0, 0))
  of "oxygen_extractor":
    (sprite: "terrain/stamp.oxygen", offset: ivec2(0, 0))
  of "junction":
    (sprite: "terrain/stamp.junction", offset: ivec2(0, 0))
  of "hub":
    (sprite: "terrain/stamp.hub", offset: ivec2(0, 0))
  of "wall", "agent", "aligner", "scrambler", "miner", "scout":
    (sprite: "", offset: ivec2(0, 0))
  of "ship":
    (sprite: "objects/ship.shadow", offset: ivec2(148, 148))
  else:
    echo "Missing splat stamp mapping for ", normalized
    (sprite: "", offset: ivec2(0, 0))

proc rebuildSplats*() =
  splats.setLen(0)
  if replay.isNil: return

  for obj in replay.objects:
    let stamp = stampForTypeName(obj.renderName)
    if stamp.sprite == "":
      continue

    var firstAliveStep = -1
    for s in 0 ..< min(replay.maxSteps, obj.alive.len):
      if obj.alive[s]:
        firstAliveStep = s
        break
    if firstAliveStep < 0 or obj.location.len == 0:
      continue

    splats.add((
      sprite: stamp.sprite,
      pos: obj.location.at(firstAliveStep).xy * TileSize + stamp.offset
    ))

  let
    mapWidthPx = replay.mapSize[0] * TileSize
    mapHeightPx = replay.mapSize[1] * TileSize
    mapAreaPx = mapWidthPx.float32 * mapHeightPx.float32
    randomSplatTarget = max(0, floor(mapAreaPx / SplatDensityAreaPerSpritePx).int)
    minSpacingSq = SplatMinSpacingPx * SplatMinSpacingPx
  if mapWidthPx <= 0 or mapHeightPx <= 0 or randomSplatTarget <= 0:
    return

  var randomSplatPositions: seq[IVec2] = @[]
  for _ in 0 ..< randomSplatTarget:
    var placed = false
    for _ in 0 ..< SplatMaxPlacementAttempts:
      let candidate = ivec2(
        rand(mapWidthPx - 1).int32,
        rand(mapHeightPx - 1).int32
      )
      var tooClose = false
      for pos in randomSplatPositions:
        let
          dx = (candidate.x - pos.x).float32
          dy = (candidate.y - pos.y).float32
          distSq = dx * dx + dy * dy
        if distSq < minSpacingSq:
          tooClose = true
          break
      if tooClose:
        continue

      randomSplatPositions.add(candidate)
      splats.add((
        sprite: RandomSplatSprites[rand(RandomSplatSprites.high)],
        pos: candidate
      ))
      placed = true
      break
    if not placed:
      # Stop generation if no valid spot is found after many attempts.
      break

proc resetTerrainCaches*() =
  terrainMap = nil
  maskMap = nil
  splatSandQuad = nil
  splatCompositePass = nil
  splats.setLen(0)

proc drawTerrain*(mvp: Mat4, px: var Pixelator, pxMini: var Pixelator) =
  if terrainMap == nil:
    terrainMap = generateTerrainMap(dataDir / "terrain/blob7x8.png")
    px = newPixelator(sk)
    pxMini = newPixelator(sk)
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
    var tint = WhiteTint
    if splat.sprite.startsWith("terrain/splat"):
      tint = rgbx(100, 100, 100, 100)
    px.drawSprite(stamp, splat.pos, tint)

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
