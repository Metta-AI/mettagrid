import
  std/[os, strutils, tables],
  pixie, opengl, silky, silky/[shaders], jsony, shady, vmath,
  allocator

# This file specifically deals with the pixel atlas texture.
# It supports pixel art style drawing with pixel perfect AA sampling.
# It is used to draw the objects in the mettascope.

type
  Entry* = object
    ## The position and size of a sprite in the atlas.
    x*: int
    y*: int
    width*: int
    height*: int

  PixelAtlas* = ref object
    ## The pixel atlas that gets converted to JSON.
    size*: int
    entries*: Table[string, Entry]

  Pixelator* = ref object
    ## The pixelator that draws the AA pixel art sprites.
    atlas: PixelAtlas
    image: Image
    shader: Shader
    vao: GLuint              ## Vertex array object
    instanceVbo: GLuint      ## Per-instance buffer: aPos(2 x uint16), aUv(4 x uint16), aTint(4 x uint8)
    atlasTexture: GLuint     ## GL texture for the atlas image
    instanceData: seq[uint16]
    instanceCount: int

var
  mvp: Uniform[Mat4]
  atlasSize: Uniform[Vec2]
  atlas: Uniform[Sampler2D]

proc pixelatorVert*(vertexPos: UVec2, uv: UVec4, tint: Vec4, fragmentUv: var Vec2, vTint: var Vec4) =
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

  # Tint is auto-normalized from 4 x uint8 by GL.
  vTint = tint

proc pixelatorFrag*(fragmentUv: Vec2, vTint: Vec4, FragColor: var Vec4) =
  # Compute the texture coordinates of the pixel.
  let pixCoord = fragmentUv * atlasSize
  # Compute the AA pixel coordinates.
  let pixAA = floor(pixCoord) + min(fract(pixCoord) / fwidth(pixCoord), 1.0) - 0.5
  FragColor = texture(atlas, pixAA / atlasSize) * vTint

proc generatePixelAtlas*(
  size: int,
  margin: int,
  dirsToScan: seq[string],
  outputImagePath: string,
  outputJsonPath: string,
  stripPrefix: string = "data/"
) {.measure.} =
  ## Generates a pixel atlas from the given directories.
  let atlasImage = newImage(size, size)
  let atlas = PixelAtlas(size: size)
  let allocator = newSkylineAllocator(size, margin)

  for dir in dirsToScan:
    for file in walkDir(dir):
      if file.path.endsWith(".png"):
        let image = readImage(file.path)
        let allocation = allocator.allocate(image.width, image.height)
        if allocation.success:
          atlasImage.draw(
            image,
            translate(vec2(allocation.x.float32, allocation.y.float32)),
            OverwriteBlend
          )
        else:
          raise newException(
            ValueError,
            "Failed to allocate space for " & file.path & "\n" &
            "You need to increase the size of the atlas"
          )
        let entry = Entry(
          x: allocation.x,
          y: allocation.y,
          width: image.width,
          height: image.height
        )
        var key = file.path
        key.removePrefix(stripPrefix)
        key.removeSuffix(".png")
        atlas.entries[key] = entry

  atlasImage.writeFile(outputImagePath)
  writeFile(outputJsonPath, atlas.toJson())

proc newPixelator*(imagePath, jsonPath: string): Pixelator {.measure.} =
  ## Creates a new pixelator.
  result = Pixelator()
  result.image = readImage(imagePath)
  result.atlas = readFile(jsonPath).fromJson(PixelAtlas)
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

  # Upload atlas image to GL texture
  glGenTextures(1, result.atlasTexture.addr)
  glActiveTexture(GL_TEXTURE0)
  glBindTexture(GL_TEXTURE_2D, result.atlasTexture)
  glTexImage2D(
    GL_TEXTURE_2D,
    0,
    GL_RGBA8.GLint,
    result.image.width.GLint,
    result.image.height.GLint,
    0,
    GL_RGBA,
    GL_UNSIGNED_BYTE,
    cast[pointer](result.image.data[0].addr)
  )
  glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR_MIPMAP_LINEAR.GLint)
  glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR.GLint)
  glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE.GLint)
  glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE.GLint)
  glGenerateMipmap(GL_TEXTURE_2D)

  # Set up VAO and instance buffer.
  glGenVertexArrays(1, result.vao.addr)
  glBindVertexArray(result.vao)
  glGenBuffers(1, result.instanceVbo.addr)
  glBindBuffer(GL_ARRAY_BUFFER, result.instanceVbo)
  glBufferData(GL_ARRAY_BUFFER, 0, nil, GL_STREAM_DRAW)  # will resize each frame

  # Interleaved attributes of 16 bytes (8 * uint16).
  let stride = 8 * sizeof(uint16)
  # Location 0: aPos (2 x uint16) at offset 0.
  glEnableVertexAttribArray(0)
  glVertexAttribIPointer(0, 2, GL_UNSIGNED_SHORT, stride.GLsizei, cast[pointer](0))
  glVertexAttribDivisor(0, 1)
  # Location 1: aUv (4 x uint16) at offset 2 * uint16.
  glEnableVertexAttribArray(1)
  glVertexAttribIPointer(1, 4, GL_UNSIGNED_SHORT, stride.GLsizei, cast[pointer](2 * sizeof(uint16)))
  glVertexAttribDivisor(1, 1)
  # Location 2: aTint (4 x uint8, normalized to 0.0-1.0) at offset 12 bytes.
  glEnableVertexAttribArray(2)
  glVertexAttribPointer(2, 4, GL_UNSIGNED_BYTE, GL_TRUE, stride.GLsizei, cast[pointer](6 * sizeof(uint16)))
  glVertexAttribDivisor(2, 1)

  # Unbind the buffers.
  glBindBuffer(GL_ARRAY_BUFFER, 0)
  glBindVertexArray(0)

const WhiteTint* = rgbx(255, 255, 255, 255)

proc drawSprite*(
  px: Pixelator,
  name: string,
  x, y: uint16,
  tint: ColorRGBX = WhiteTint
) =
  ## Draws a sprite at the given position with optional tint color.
  if name notin px.atlas.entries:
    echo "[Warning] Sprite not found in atlas: " & name
    return
  let uv = px.atlas.entries[name]
  px.instanceData.add(x.uint16)
  px.instanceData.add(y.uint16)
  px.instanceData.add(uv.x.uint16)
  px.instanceData.add(uv.y.uint16)
  px.instanceData.add(uv.width.uint16)
  px.instanceData.add(uv.height.uint16)
  # Pack 4 tint bytes into 2 uint16 slots (read as 4 x GL_UNSIGNED_BYTE on GPU)
  px.instanceData.add(uint16(tint.r) or (uint16(tint.g) shl 8))
  px.instanceData.add(uint16(tint.b) or (uint16(tint.a) shl 8))
  inc px.instanceCount

proc drawSprite*(
  px: Pixelator,
  name: string,
  pos: IVec2,
  tint: ColorRGBX = WhiteTint
) =
  ## Draws a sprite at the given position with optional tint color.
  px.drawSprite(name, pos.x.uint16, pos.y.uint16, tint)

proc contains*(px: Pixelator, name: string): bool =
  ## Checks if the given sprite is in the atlas.
  name in px.atlas.entries

proc spriteSize*(px: Pixelator, name: string): IVec2 =
  ## Returns sprite dimensions from the atlas, or (0, 0) if missing.
  if name notin px.atlas.entries:
    return ivec2(0, 0)
  let uv = px.atlas.entries[name]
  ivec2(uv.width.int32, uv.height.int32)

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
  px.shader.setUniform("atlasSize", vec2(px.image.width.float32, px.image.height.float32))
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
