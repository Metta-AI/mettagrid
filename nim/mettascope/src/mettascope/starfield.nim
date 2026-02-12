import
  std/[os, strutils],
  opengl, silky, silky/[shaders], shady, vmath, pixie, windy,
  common, replays, panels

## Starfield and cloud background layers.
## The starfield is a static fullscreen image that always fills the viewport
## maintaining its aspect ratio (cover mode). The clouds layer is drawn
## slightly larger and offset based on camera position for a parallax effect.

type
  BackgroundLayer = object
    texture: GLuint
    texW: float32
    texH: float32

var
  # Shader uniforms for the fullscreen textured quad.
  starfieldScreenSize: Uniform[Vec2]
  starfieldTexSize: Uniform[Vec2]
  starfieldOffset: Uniform[Vec2]
  starfieldScale: Uniform[float32]
  starfieldTex: Uniform[Sampler2D]
  starfieldShader: Shader
  starfieldVao: GLuint
  bgStarfield: BackgroundLayer
  bgClouds: BackgroundLayer
  starfieldInitialized: bool = false

proc starfieldVert(fragUV: var Vec2) =
  ## Fullscreen quad vertex shader. Generates corners from gl_VertexID.
  let corner = ivec2(gl_VertexID mod 2, gl_VertexID div 2)
  fragUV = vec2(float(corner.x), float(corner.y))
  gl_Position = vec4(fragUV.x * 2.0 - 1.0, 1.0 - fragUV.y * 2.0, 0.0, 1.0)

proc starfieldFrag(fragUV: Vec2, FragColor: var Vec4) =
  ## Textured quad fragment shader with aspect-correct cover mapping,
  ## optional scale and parallax offset.
  let
    sa = starfieldScreenSize.x / starfieldScreenSize.y
    ta = starfieldTexSize.x / starfieldTexSize.y
    ratio = sa / ta
    # Cover mapping: scale UVs so the image fills the screen, cropping the excess.
    uCov = min(ratio, 1.0)
    vCov = min(1.0 / ratio, 1.0)
  var
    u = fragUV.x * uCov + (1.0 - uCov) * 0.5
    v = fragUV.y * vCov + (1.0 - vCov) * 0.5

  # Apply scale (>1.0 zooms in, showing less of the texture) and parallax offset.
  u = (u - 0.5) / starfieldScale + 0.5 + starfieldOffset.x
  v = (v - 0.5) / starfieldScale + 0.5 + starfieldOffset.y

  FragColor = texture(starfieldTex, vec2(u, v))

proc loadLayer(imagePath: string): BackgroundLayer {.measure.} =
  ## Load an image as a background layer texture.
  let image = readImage(imagePath)
  result.texW = image.width.float32
  result.texH = image.height.float32

  glGenTextures(1, result.texture.addr)
  glActiveTexture(GL_TEXTURE0)
  glBindTexture(GL_TEXTURE_2D, result.texture)
  glTexImage2D(
    GL_TEXTURE_2D, 0, GL_RGBA8.GLint,
    image.width.GLint, image.height.GLint, 0,
    GL_RGBA, GL_UNSIGNED_BYTE,
    cast[pointer](image.data[0].addr)
  )
  glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR.GLint)
  glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR.GLint)
  glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE.GLint)
  glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE.GLint)
  glBindTexture(GL_TEXTURE_2D, 0)

proc initStarfield() =
  ## Initialize the shared shader, VAO, and load both layer textures.
  when defined(emscripten):
    starfieldShader = newShader(
      ("starfieldVert", toGLSL(starfieldVert, glslES3)),
      ("starfieldFrag", toGLSL(starfieldFrag, glslES3))
    )
  else:
    starfieldShader = newShader(
      ("starfieldVert", toGLSL(starfieldVert, glslDesktop)),
      ("starfieldFrag", toGLSL(starfieldFrag, glslDesktop))
    )

  # Empty VAO; vertices are generated from gl_VertexID.
  glGenVertexArrays(1, starfieldVao.addr)

  bgStarfield = loadLayer(dataDir / "starfield/starfield.png")
  bgClouds = loadLayer(dataDir / "starfield/clouds.png")

  starfieldInitialized = true

proc drawLayer(layer: BackgroundLayer, screenSize: Vec2, offset: Vec2, scale: float32) =
  ## Draw a single background layer as a fullscreen quad.
  glUseProgram(starfieldShader.programId)
  starfieldShader.setUniform("starfieldScreenSize", screenSize)
  starfieldShader.setUniform("starfieldTexSize", vec2(layer.texW, layer.texH))
  starfieldShader.setUniform("starfieldOffset", offset)
  starfieldShader.setUniform("starfieldScale", scale)
  glActiveTexture(GL_TEXTURE0)
  glBindTexture(GL_TEXTURE_2D, layer.texture)
  starfieldShader.setUniform("starfieldTex", 0)
  starfieldShader.bindUniforms()

  glBindVertexArray(starfieldVao)
  glDrawArrays(GL_TRIANGLE_STRIP, 0, 4)
  glBindVertexArray(0)
  glUseProgram(0)

proc drawStarfield*() {.measure.} =
  ## Draw the starfield background and parallax cloud layer.
  if replay.isNil:
    return

  if not starfieldInitialized:
    initStarfield()

  # Save current viewport and set it to the panel content area.
  var prevViewport: array[4, GLint]
  glGetIntegerv(GL_VIEWPORT, prevViewport[0].addr)
  let
    r = worldMapZoomInfo.rect
    screenSize = vec2(r.w.float32, r.h.float32)
  glViewport(r.x, window.size.y - r.y - r.h, r.w, r.h)

  # Draw starfield: static background, fills screen with cover mapping.
  drawLayer(bgStarfield, screenSize, vec2(0, 0), 1.0)

  # Calculate parallax offset for clouds based on camera position over the map.
  let
    z = worldMapZoomInfo.zoom * worldMapZoomInfo.zoom
    cx = (screenSize.x / 2.0 - worldMapZoomInfo.pos.x) / z
    cy = (screenSize.y / 2.0 - worldMapZoomInfo.pos.y) / z
    mapW = max(1.0, replay.mapSize[0].float32)
    mapH = max(1.0, replay.mapSize[1].float32)
    parallaxStrength = 0.08
    offsetX = (cx / mapW - 0.5) * parallaxStrength
    offsetY = (cy / mapH - 0.5) * parallaxStrength

  # Draw clouds: slightly larger (scale 1.2) with parallax offset, blended on top.
  drawLayer(bgClouds, screenSize, vec2(offsetX, offsetY), 1.2)

  # Restore viewport.
  glViewport(prevViewport[0], prevViewport[1], prevViewport[2], prevViewport[3])
