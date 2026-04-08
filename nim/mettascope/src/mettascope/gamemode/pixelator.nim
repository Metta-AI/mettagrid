import
  std/[math, unicode],
  pixie, opengl, silky, silky/drawers/ogl, shady, vmath

# This file specifically deals with the pixel atlas texture.
# It supports pixel art style drawing with pixel perfect AA sampling.
# It is used to draw the objects in the mettascope.

type
  Pixelator* = ref object
    ## The pixelator that draws the AA pixel art sprites.
    sk: Silky
    shader: Shader
    vao: GLuint              ## Vertex array object
    instanceVbo: GLuint      ## Per-instance buffer: aPos(2), aUv(4), aTint(2 as 4xU8), aMaskUv(4), aLampUv(4)
    atlasTexture: GLuint     ## GL texture borrowed from silky
    atlasWidth: int
    atlasHeight: int
    instanceData: seq[uint16]
    instanceCount: int

var
  mvp: Uniform[Mat4]
  atlasSize: Uniform[Vec2]
  atlas: Uniform[Sampler2D]

proc pixelatorVert*(
  vertexPos: UVec2, uv: UVec4, tint: Vec4, maskUv: UVec4, lampUv: UVec4,
  fragmentUv: var Vec2, vTint: var Vec4, vMaskUv: var Vec2, vLampUv: var Vec2
) =
  # Compute the corner of the quad based on the vertex ID.
  # 0:(0,0), 1:(1,0), 2:(0,1), 3:(1,1)
  let corner = ivec2(gl_VertexID mod 2, gl_VertexID div 2)

  # Compute the position of the vertex in the atlas.
  let dx = float(vertexPos.x) + (float(corner.x) - 0.5) * float(uv.z)
  let dy = float(vertexPos.y) + (float(corner.y) - 0.5) * float(uv.w)
  gl_Position = mvp * vec4(dx, dy, 0.0, 1.0)

  # Compute the texture coordinates of the vertex.
  let sx = float(uv.x) + float(corner.x) * float(uv.z)
  let sy = float(uv.y) + float(corner.y) * float(uv.w)
  fragmentUv = vec2(sx, sy) / atlasSize

  # Compute mask UV. When maskUv.z == 0 (no mask), output -1.0 sentinel.
  if float(maskUv.z) < 0.5:
    vMaskUv = vec2(-1.0)
  else:
    let msx = float(maskUv.x) + float(corner.x) * float(maskUv.z)
    let msy = float(maskUv.y) + float(corner.y) * float(maskUv.w)
    vMaskUv = vec2(msx, msy) / atlasSize

  # Compute lamp UV. When lampUv.z == 0 (no lamp), output -1.0 sentinel.
  if float(lampUv.z) < 0.5:
    vLampUv = vec2(-1.0)
  else:
    let lsx = float(lampUv.x) + float(corner.x) * float(lampUv.z)
    let lsy = float(lampUv.y) + float(corner.y) * float(lampUv.w)
    vLampUv = vec2(lsx, lsy) / atlasSize

  # Tint is auto-normalized from 4 x uint8 by GL.
  vTint = tint

proc pixelatorFrag*(
  fragmentUv: Vec2, vTint: Vec4, vMaskUv: Vec2, vLampUv: Vec2,
  FragColor: var Vec4
) =
  # Compute the texture coordinates of the pixel.
  let pixCoord = fragmentUv * atlasSize
  # Compute the AA pixel coordinates.
  let pixAA = floor(pixCoord) + min(fract(pixCoord) / fwidth(pixCoord), 1.0) - 0.5
  let base = texture(atlas, pixAA / atlasSize)
  if vLampUv.x >= 0.0:
    # Lamp mode: add light where lamp is bright, keep base alpha.
    let lampCoord = vLampUv * atlasSize
    let lampAA = floor(lampCoord) + min(fract(lampCoord) / fwidth(lampCoord), 1.0) - 0.5
    let lampR = texture(atlas, lampAA / atlasSize).r
    FragColor = vec4(
      base.rgb + lampR * vTint.rgb * base.a,
      base.a
    )
  elif vMaskUv.x < 0.0:
    # No mask: apply tint to entire sprite (original behavior).
    FragColor = base * vTint
  else:
    # Mask: tint only where mask is white.
    let maskCoord = vMaskUv * atlasSize
    let maskAA = floor(maskCoord) + min(fract(maskCoord) / fwidth(maskCoord), 1.0) - 0.5
    let maskR = texture(atlas, maskAA / atlasSize).r
    FragColor = vec4(base.rgb * mix(vec3(1.0), vTint.rgb, maskR), base.a * vTint.a)

proc newPixelator*(sk: Silky): Pixelator {.measure.} =
  ## Creates a new pixelator that borrows the silky atlas.
  result = Pixelator()
  result.sk = sk
  result.atlasTexture = sk.atlasTextureId()
  let atlasSize = sk.atlasImageSize()
  result.atlasWidth = atlasSize.x.int
  result.atlasHeight = atlasSize.y.int
  result.instanceData = @[]
  result.instanceCount = 0

  when defined(emscripten):
    result.shader = newShader(
      ("pixelatorVert", toGLSL(pixelatorVert, glslES3)),
      ("pixelatorFrag", toGLSL(pixelatorFrag, glslES3))
    )
  else:
    result.shader = newShader(
      ("pixelatorVert", toGLSL(pixelatorVert, glslDesktop)),
      ("pixelatorFrag", toGLSL(pixelatorFrag, glslDesktop))
    )

  # Set up VAO and instance buffer.
  glGenVertexArrays(1, result.vao.addr)
  glBindVertexArray(result.vao)
  glGenBuffers(1, result.instanceVbo.addr)
  glBindBuffer(GL_ARRAY_BUFFER, result.instanceVbo)
  glBufferData(GL_ARRAY_BUFFER, 0, nil, GL_STREAM_DRAW)  # will resize each frame

  # Interleaved attributes of 32 bytes (16 * uint16).
  let
    stride = 16 * sizeof(uint16)
    vertexPosLoc = glGetAttribLocation(result.shader.programId, "vertexPos")
    uvLoc = glGetAttribLocation(result.shader.programId, "uv")
    tintLoc = glGetAttribLocation(result.shader.programId, "tint")
    maskUvLoc = glGetAttribLocation(result.shader.programId, "maskUv")
    lampUvLoc = glGetAttribLocation(result.shader.programId, "lampUv")
  if vertexPosLoc == -1:
    raise newException(ValueError, "vertexPos attribute not found")
  if uvLoc == -1:
    raise newException(ValueError, "uv attribute not found")
  if tintLoc == -1:
    raise newException(ValueError, "tint attribute not found")
  if maskUvLoc == -1:
    raise newException(ValueError, "maskUv attribute not found")
  if lampUvLoc == -1:
    raise newException(ValueError, "lampUv attribute not found")

  glEnableVertexAttribArray(vertexPosLoc.GLuint)
  glVertexAttribIPointer(
    vertexPosLoc.GLuint,
    2,
    GL_UNSIGNED_SHORT,
    stride.GLsizei,
    cast[pointer](0)
  )
  glVertexAttribDivisor(vertexPosLoc.GLuint, 1)

  glEnableVertexAttribArray(uvLoc.GLuint)
  glVertexAttribIPointer(
    uvLoc.GLuint,
    4,
    GL_UNSIGNED_SHORT,
    stride.GLsizei,
    cast[pointer](2 * sizeof(uint16))
  )
  glVertexAttribDivisor(uvLoc.GLuint, 1)

  glEnableVertexAttribArray(tintLoc.GLuint)
  glVertexAttribPointer(
    tintLoc.GLuint,
    4,
    GL_UNSIGNED_BYTE,
    GL_TRUE,
    stride.GLsizei,
    cast[pointer](6 * sizeof(uint16))
  )
  glVertexAttribDivisor(tintLoc.GLuint, 1)

  glEnableVertexAttribArray(maskUvLoc.GLuint)
  glVertexAttribIPointer(
    maskUvLoc.GLuint,
    4,
    GL_UNSIGNED_SHORT,
    stride.GLsizei,
    cast[pointer](8 * sizeof(uint16))
  )
  glVertexAttribDivisor(maskUvLoc.GLuint, 1)

  glEnableVertexAttribArray(lampUvLoc.GLuint)
  glVertexAttribIPointer(
    lampUvLoc.GLuint,
    4,
    GL_UNSIGNED_SHORT,
    stride.GLsizei,
    cast[pointer](12 * sizeof(uint16))
  )
  glVertexAttribDivisor(lampUvLoc.GLuint, 1)

  # Unbind the buffers.
  glBindBuffer(GL_ARRAY_BUFFER, 0)
  glBindVertexArray(0)

const WhiteTint* = rgbx(255, 255, 255, 255)

proc drawQuad*(
  px: Pixelator,
  x, y: uint16,
  uvX, uvY, uvW, uvH: uint16,
  tint: ColorRGBX = WhiteTint,
  maskX, maskY, maskW, maskH: uint16 = 0,
  lampX, lampY, lampW, lampH: uint16 = 0
) =
  ## Emits one instanced quad at the given center with atlas UV region.
  px.instanceData.add(x)
  px.instanceData.add(y)
  px.instanceData.add(uvX)
  px.instanceData.add(uvY)
  px.instanceData.add(uvW)
  px.instanceData.add(uvH)
  px.instanceData.add(uint16(tint.r) or (uint16(tint.g) shl 8))
  px.instanceData.add(uint16(tint.b) or (uint16(tint.a) shl 8))
  px.instanceData.add(maskX)
  px.instanceData.add(maskY)
  px.instanceData.add(maskW)
  px.instanceData.add(maskH)
  px.instanceData.add(lampX)
  px.instanceData.add(lampY)
  px.instanceData.add(lampW)
  px.instanceData.add(lampH)
  inc px.instanceCount

proc drawSprite*(
  px: Pixelator,
  name: string,
  x, y: uint16,
  tint: ColorRGBX = WhiteTint,
  mask: string = "",
  lamp: string = ""
) =
  ## Draws a sprite at the given position with optional tint color.
  ## When mask is non-empty, tint is applied only where the mask is white.
  ## When lamp is non-empty, lamp sprite is additively blended with tint.
  var uv: Entry
  if not px.sk.getAtlasEntry(name, uv):
    echo "[Warning] Sprite not found in atlas: " & name
    return
  var
    m: Entry
    l: Entry
    mX, mY, mW, mH: uint16
    lX, lY, lW, lH: uint16
  if mask.len > 0 and px.sk.getAtlasEntry(mask, m):
    mX = m.x.uint16; mY = m.y.uint16
    mW = m.width.uint16; mH = m.height.uint16
  if lamp.len > 0 and px.sk.getAtlasEntry(lamp, l):
    lX = l.x.uint16; lY = l.y.uint16
    lW = l.width.uint16; lH = l.height.uint16
  px.drawQuad(
    x, y,
    uv.x.uint16, uv.y.uint16, uv.width.uint16, uv.height.uint16,
    tint, mX, mY, mW, mH, lX, lY, lW, lH
  )

proc drawSprite*(
  px: Pixelator,
  name: string,
  pos: IVec2,
  tint: ColorRGBX = WhiteTint,
  mask: string = "",
  lamp: string = ""
) =
  ## Draws a sprite at the given position with optional tint color.
  px.drawSprite(name, pos.x.uint16, pos.y.uint16, tint, mask, lamp)

proc contains*(px: Pixelator, name: string): bool =
  ## Checks if the given sprite is in the atlas.
  px.sk.contains(name)

proc spriteSize*(px: Pixelator, name: string): IVec2 =
  ## Returns sprite dimensions from the atlas, or (0, 0) if missing.
  var uv: Entry
  if not px.sk.getAtlasEntry(name, uv):
    return ivec2(0, 0)
  ivec2(uv.width.int32, uv.height.int32)

proc textSize*(px: Pixelator, font: string, text: string): Vec2 =
  ## Returns the size of single-line text in pixels.
  px.sk.getTextSize(font, text)

proc drawText*(
  px: Pixelator,
  font: string,
  text: string,
  pos: IVec2,
  tint: ColorRGBX
) =
  ## Draws single-line text at the given top-left position.
  if font notin px.sk.atlas.fonts:
    return
  let
    fontData = px.sk.atlas.fonts[font]
    runedText = text.toRunes
  var cursorX = pos.x.float32
  let baselineY = pos.y.float32 + fontData.ascent
  for i in 0 ..< runedText.len:
    let glyphStr = $runedText[i]
    var entry: LetterEntry
    if glyphStr in fontData.entries:
      entry = fontData.entries[glyphStr][0]
    elif "?" in fontData.entries:
      entry = fontData.entries["?"][0]
    else:
      continue
    if entry.boundsWidth > 0 and entry.boundsHeight > 0:
      let
        glyphX = floor(cursorX) + entry.boundsX
        glyphY = round(baselineY + entry.boundsY)
        w = round(entry.boundsWidth)
        h = round(entry.boundsHeight)
      px.drawQuad(
        (glyphX + w * 0.5).uint16,
        (glyphY + h * 0.5).uint16,
        entry.x.uint16, entry.y.uint16, w.uint16, h.uint16,
        tint
      )
    cursorX += entry.advance
    if i < runedText.len - 1:
      let nextGlyphStr = $runedText[i + 1]
      if nextGlyphStr in entry.kerning:
        cursorX += entry.kerning[nextGlyphStr]

proc clear*(px: Pixelator) =
  ## Clears the current instance queue.
  px.instanceData.setLen(0)
  px.instanceCount = 0

proc flush*(
  px: Pixelator,
  mvp: Mat4
) {.measure.} =
  ## Draw all queued instances for the current sprite.
  if px.instanceCount == 0:
    return

  # Upload instance buffer.
  glBindBuffer(GL_ARRAY_BUFFER, px.instanceVbo)
  let byteLen = px.instanceData.len * sizeof(uint16)
  glBufferData(GL_ARRAY_BUFFER, byteLen, px.instanceData[0].addr, GL_STREAM_DRAW)

  # Bind the shader and the atlas texture.
  glUseProgram(px.shader.programId)
  px.shader.setUniform("mvp", mvp)
  px.shader.setUniform(
    "atlasSize",
    vec2(px.atlasWidth.float32, px.atlasHeight.float32)
  )
  glActiveTexture(GL_TEXTURE0)
  glBindTexture(GL_TEXTURE_2D, px.atlasTexture)
  px.shader.setUniform("atlas", 0)
  px.shader.bindUniforms()
  glBindVertexArray(px.vao)

  # Draw 4-vertex triangle strip per instance (expanded in vertex shader)
  glDrawArraysInstanced(GL_TRIANGLE_STRIP, 0, 4, px.instanceCount.GLsizei)

  # Unbind minimal state
  glBindVertexArray(0)
  glUseProgram(0)
  glBindTexture(GL_TEXTURE_2D, 0)

  # Reset the data for the next frame.
  px.clear()
