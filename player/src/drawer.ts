/// <reference types="@webgpu/types" />

import { Vec2f, Mat3f } from './vector_math.js';

// Type definition for atlas data
interface AtlasData {
  [key: string]: [number, number, number, number]; // [x, y, width, height]
}

class Drawer {
  // Canvas and WebGPU state
  public canvas: HTMLCanvasElement;
  public device: GPUDevice | null;
  private context: GPUCanvasContext | null;
  private pipeline: GPURenderPipeline | null;
  private sampler: GPUSampler | null;
  private atlasTexture: GPUTexture | null;
  private textureSize: Vec2f;
  public atlasData: AtlasData | null;
  private vertexBuffer: GPUBuffer | null;
  private indexBuffer: GPUBuffer | null;
  private bindGroup: GPUBindGroup | null;
  private renderPassDescriptor: GPURenderPassDescriptor | null;
  private canvasSizeUniformBuffer: GPUBuffer | null;
  private canvasSize: Vec2f;
  private atlasMargin: number;

  // Transformation state
  private currentTransform: Mat3f;
  private transformStack: Mat3f[];

  // Buffer management
  private maxQuads: number;
  private vertexCapacity: number;
  private indexCapacity: number;
  private vertexData: Float32Array;
  private indexData: Uint16Array;
  private currentQuad: number;
  private currentVertex: number;
  private currentIndex: number;

  // State tracking
  public ready: boolean;

  constructor(canvas: HTMLCanvasElement) {
    this.canvas = canvas;
    this.device = null;
    this.context = null;
    this.pipeline = null;
    this.sampler = null;
    this.atlasTexture = null;
    this.textureSize = new Vec2f(0, 0);
    this.atlasData = null;
    this.vertexBuffer = null;
    this.indexBuffer = null;
    this.bindGroup = null;
    this.renderPassDescriptor = null;
    this.canvasSizeUniformBuffer = null;
    this.canvasSize = new Vec2f(0, 0);
    this.atlasMargin = 4; // Default margin for texture sampling.

    // Transformation matrix and stack for Canvas 2D API-like interface.
    this.currentTransform = Mat3f.identity();
    this.transformStack = [];

    // Pre-allocated buffers for better performance.
    this.maxQuads = 10000; // Maximum number of quads we can render at once.
    this.vertexCapacity = this.maxQuads * 4; // 4 vertices per quad.
    this.indexCapacity = this.maxQuads * 6; // 6 indices per quad (2 triangles).

    // Pre-allocated CPU-side buffers.
    this.vertexData = new Float32Array(this.vertexCapacity * 8); // 8 floats per vertex (pos*2, uv*2, color*4).
    this.indexData = new Uint16Array(this.indexCapacity);

    // Counters to track buffer usage.
    this.currentQuad = 0;
    this.currentVertex = 0;
    this.currentIndex = 0;

    // Create the index pattern once (it's always the same for quads).
    this.setupIndexPattern();

    this.ready = false;
  }

  // Set up the index buffer pattern once.
  setupIndexPattern(): void {
    // For each quad: triangles are formed by indices
    // 0-1-2 (top-left, bottom-left, top-right)
    // 2-1-3 (top-right, bottom-left, bottom-right).
    for (let i = 0; i < this.maxQuads; i++) {
      const baseVertex = i * 4;
      const baseIndex = i * 6;

      this.indexData[baseIndex + 0] = baseVertex + 0; // Top-left.
      this.indexData[baseIndex + 1] = baseVertex + 1; // Bottom-left.
      this.indexData[baseIndex + 2] = baseVertex + 2; // Top-right.

      this.indexData[baseIndex + 3] = baseVertex + 2; // Top-right.
      this.indexData[baseIndex + 4] = baseVertex + 1; // Bottom-left.
      this.indexData[baseIndex + 5] = baseVertex + 3; // Bottom-right.
    }
  }

  // Canvas 2D API-like methods for transform manipulation
  save(): void {
    // Push a copy of the current transform onto the stack
    this.transformStack.push(new Mat3f(
      this.currentTransform.get(0, 0), this.currentTransform.get(0, 1), this.currentTransform.get(0, 2),
      this.currentTransform.get(1, 0), this.currentTransform.get(1, 1), this.currentTransform.get(1, 2),
      this.currentTransform.get(2, 0), this.currentTransform.get(2, 1), this.currentTransform.get(2, 2)
    ));
  }

  restore(): void {
    // Pop the last transform from the stack
    if (this.transformStack.length > 0) {
      this.currentTransform = this.transformStack.pop()!;
    } else {
      console.warn("Transform stack is empty");
    }
  }

  translate(x: number, y: number): void {
    // Create a translation matrix and multiply current transform by it
    const translateMatrix = Mat3f.translate(x, y);
    this.currentTransform = this.currentTransform.mul(translateMatrix);
  }

  rotate(angle: number): void {
    // Create a rotation matrix and multiply current transform by it
    const rotateMatrix = Mat3f.rotate(angle);
    this.currentTransform = this.currentTransform.mul(rotateMatrix);
  }

  scale(x: number, y: number): void {
    // Create a scaling matrix and multiply current transform by it
    const scaleMatrix = Mat3f.scale(x, y);
    this.currentTransform = this.currentTransform.mul(scaleMatrix);
  }

  // Reset transform to identity
  resetTransform(): void {
    this.currentTransform = Mat3f.identity();
  }

  async init(atlasJsonUrl: string, atlasImageUrl: string): Promise<boolean> {
    // Initialize WebGPU device.
    const adapter = await navigator.gpu?.requestAdapter();
    this.device = await adapter?.requestDevice() || null;
    if (!this.device) {
      this.fail('Need a browser that supports WebGPU');
      return false;
    }

    // Load Atlas and Texture.
    const [atlasData, source] = await Promise.all([
      this.loadAtlasJson(atlasJsonUrl),
      this.loadAtlasImage(atlasImageUrl)
    ]);

    if (!atlasData || !source) {
      this.fail('Failed to load atlas or texture');
      return false;
    }
    this.atlasData = atlasData;
    this.textureSize = new Vec2f(source.width, source.height);

    // Configure Canvas.
    this.context = this.canvas.getContext('webgpu');
    if (!this.context) {
      this.fail('Failed to get WebGPU context');
      return false;
    }

    const presentationFormat = navigator.gpu.getPreferredCanvasFormat();
    this.context.configure({
      device: this.device,
      format: presentationFormat,
    });

    // Calculate number of mip levels.
    const mipLevels = Math.floor(Math.log2(Math.max(this.textureSize.x(), this.textureSize.y()))) + 1;
    // Create Texture and Sampler.
    this.atlasTexture = this.device.createTexture({
      label: atlasImageUrl,
      format: 'rgba8unorm',
      size: [this.textureSize.x(), this.textureSize.y()],
      usage: GPUTextureUsage.TEXTURE_BINDING |
        GPUTextureUsage.COPY_DST |
        GPUTextureUsage.RENDER_ATTACHMENT,
      mipLevelCount: mipLevels,
    });
    this.device.queue.copyExternalImageToTexture(
      { source, flipY: false }, // Don't flip Y if UVs start top-left.
      { texture: this.atlasTexture },
      { width: this.textureSize.x(), height: this.textureSize.y() },
    );

    // Generate mipmaps for the texture.
    this.generateMipmaps(this.atlasTexture, this.textureSize.x(), this.textureSize.y());

    this.sampler = this.device.createSampler({
      addressModeU: 'repeat',
      addressModeV: 'repeat',
      magFilter: 'linear', // Normal smooth style (was 'nearest').
      minFilter: 'linear', // Normal smooth style (was 'nearest').
      mipmapFilter: 'linear', // Linear filtering between mipmap levels.
    });

    // Create fixed-size GPU buffers.
    this.vertexBuffer = this.device.createBuffer({
      label: 'vertex buffer',
      size: this.vertexCapacity * 8 * Float32Array.BYTES_PER_ELEMENT,
      // x, y, u, v, r, g, b, a.
      usage: GPUBufferUsage.VERTEX | GPUBufferUsage.COPY_DST,
    });
    this.indexBuffer = this.device.createBuffer({
      label: 'index buffer',
      size: this.indexCapacity * Uint16Array.BYTES_PER_ELEMENT,
      // Using 16-bit indices.
      usage: GPUBufferUsage.INDEX | GPUBufferUsage.COPY_DST,
    });

    // Write the index pattern to the GPU immediately (it never changes)
    this.device.queue.writeBuffer(
      this.indexBuffer,
      0,
      this.indexData,
      0,
      this.indexData.length
    );

    this.canvasSizeUniformBuffer = this.device.createBuffer({
      label: 'canvas size uniform buffer',
      size: 2 * Float32Array.BYTES_PER_ELEMENT, // vec2f (width, height).
      usage: GPUBufferUsage.UNIFORM | GPUBufferUsage.COPY_DST,
    });

    // Shader Module.
    const shaderModule = this.device.createShaderModule({
      label: 'Sprite Shader Module',
      code: `
        struct VertexInput {
          @location(0) position: vec2f,
          @location(1) texcoord: vec2f,
          @location(2) color: vec4f,
        };

        struct VertexOutput {
          @builtin(position) position: vec4f,
          @location(0) texcoord: vec2f,
          @location(1) color: vec4f,
        };

        struct CanvasInfo {
          resolution: vec2f,
        };
        @group(0) @binding(2) var<uniform> canvas: CanvasInfo;

        @vertex fn vs(vert: VertexInput) -> VertexOutput {
          var out: VertexOutput;
          let zero_to_one = vert.position / canvas.resolution;
          let zero_to_two = zero_to_one * 2.0;
          let clip_space = zero_to_two - vec2f(1.0, 1.0);
          out.position = vec4f(clip_space.x, -clip_space.y, 0.0, 1.0);
          out.texcoord = vert.texcoord;
          out.color = vert.color;
          return out;
        }

        @group(0) @binding(0) var imgSampler: sampler;
        @group(0) @binding(1) var imgTexture: texture_2d<f32>;

        @fragment fn fs(in: VertexOutput) -> @location(0) vec4f {
          let texColor = textureSample(imgTexture, imgSampler, in.texcoord);
          // For premultiplied alpha, we multiply the RGB of the color but keep its alpha
          return vec4f(texColor.rgb * in.color.rgb, texColor.a * in.color.a);
        }
      `,
    });

    // Render Pipeline.
    this.pipeline = this.device.createRenderPipeline({
      label: 'Sprite Render Pipeline',
      layout: 'auto',
      vertex: {
        module: shaderModule,
        entryPoint: 'vs',
        buffers: [
          {
            // Vertex buffer layout.
            arrayStride: 8 * Float32Array.BYTES_PER_ELEMENT, // 2 pos, 2 uv, 4 color.
            attributes: [
              { shaderLocation: 0, offset: 0, format: 'float32x2' }, // Position.
              { shaderLocation: 1, offset: 2 * Float32Array.BYTES_PER_ELEMENT, format: 'float32x2' }, // Texcoord.
              { shaderLocation: 2, offset: 4 * Float32Array.BYTES_PER_ELEMENT, format: 'float32x4' }, // Color.
            ],
          },
        ],
      },
      fragment: {
        module: shaderModule,
        entryPoint: 'fs',
        targets: [{
          format: presentationFormat,
          blend: {
            color: {
              srcFactor: 'one',
              dstFactor: 'one-minus-src-alpha',
              operation: 'add'
            },
            alpha: {
              srcFactor: 'one',
              dstFactor: 'one-minus-src-alpha',
              operation: 'add'
            }
          }
        }],
      },
      primitive: {
        topology: 'triangle-list', // Each sprite is 2 triangles.
      },
    });

    // Bind Group for the pipeline.
    this.bindGroup = this.device.createBindGroup({
      label: 'Sprite Bind Group',
      layout: this.pipeline.getBindGroupLayout(0),
      entries: [
        { binding: 0, resource: this.sampler },
        { binding: 1, resource: this.atlasTexture.createView() },
        { binding: 2, resource: { buffer: this.canvasSizeUniformBuffer } },
      ],
    });

    // Render Pass Descriptor for the pipeline.
    this.renderPassDescriptor = {
      label: 'Canvas Render Pass',
      colorAttachments: [
        {
          // View is acquired later.
          clearValue: { r: 0.1, g: 0.1, b: 0.1, a: 1.0 }, // Dark grey clear.
          loadOp: 'clear',
          storeOp: 'store',
          view: undefined!, // This is set just before render in flush()
        },
      ] as GPURenderPassColorAttachment[],
    } as GPURenderPassDescriptor;

    this.ready = true;
    return true;
  }

  fail(msg: string): void {
    console.error(msg);
    const failDiv = document.createElement('div');
    failDiv.id = 'fail';
    failDiv.textContent =
      `Initialization Error: ${msg}. See console for details.`;
    document.body.appendChild(failDiv);
  }

  async loadAtlasImage(url: string): Promise<ImageBitmap | null> {
    try {
      const res = await fetch(url);
      if (!res.ok) {
        throw new Error(`Failed to fetch image: ${res.statusText}`);
      }
      const blob = await res.blob();
      // Use premultiplied alpha to fix border issues
      return await createImageBitmap(blob, {
        colorSpaceConversion: 'none',
        premultiplyAlpha: 'premultiply'
      });
    } catch (err) {
      console.error(`Error loading image ${url}:`, err);
      return null;
    }
  }

  async loadAtlasJson(url: string): Promise<AtlasData | null> {
    try {
      const res = await fetch(url);
      if (!res.ok) {
        throw new Error(`Failed to fetch atlas: ${res.statusText}`);
      }
      return await res.json();
    } catch (err) {
      console.error(`Error loading atlas ${url}:`, err);
      return null;
    }
  }

  // Clears the buffer for the new frame.
  clear(): void {
    if (!this.ready) return;

    // Reset counters instead of recreating arrays.
    this.currentQuad = 0;
    this.currentVertex = 0;
    this.currentIndex = 0;

    // Reset transform for new frame.
    this.resetTransform();
    this.transformStack = [];
  }

  // Draws a textured rectangle with the given coordinates and UV mapping.
  drawRect(
    x: number,
    y: number,
    width: number,
    height: number,
    u0: number,
    v0: number,
    u1: number,
    v1: number,
    color: number[] = [1, 1, 1, 1]
  ): void {
    if (!this.ready) {
      return;
    }

    // Check if we need to flush before adding more vertices.
    if (this.currentQuad >= this.maxQuads) {
      this.flush();
    }

    const pos = new Vec2f(x, y);

    // Calculate vertex positions (screen pixels, origin top-left).
    // We'll make 4 vertices for a quad.
    const untransformedTopLeft = pos;
    const untransformedBottomLeft = new Vec2f(pos.x(), pos.y() + height);
    const untransformedTopRight = new Vec2f(pos.x() + width, pos.y());
    const untransformedBottomRight = new Vec2f(pos.x() + width, pos.y() + height);

    // Apply current transformation to each vertex.
    const topLeft = this.currentTransform.transform(untransformedTopLeft);
    const bottomLeft = this.currentTransform.transform(untransformedBottomLeft);
    const topRight = this.currentTransform.transform(untransformedTopRight);
    const bottomRight = this.currentTransform.transform(untransformedBottomRight);

    // Calculate base offset for this quad in the vertex data array.
    const baseVertex = this.currentVertex;
    const baseOffset = baseVertex * 8; // Each vertex has 8 floats.

    // Top-left vertex.
    this.vertexData[baseOffset + 0] = topLeft.x();
    this.vertexData[baseOffset + 1] = topLeft.y();
    this.vertexData[baseOffset + 2] = u0;
    this.vertexData[baseOffset + 3] = v0;
    this.vertexData[baseOffset + 4] = color[0];
    this.vertexData[baseOffset + 5] = color[1];
    this.vertexData[baseOffset + 6] = color[2];
    this.vertexData[baseOffset + 7] = color[3];

    // Bottom-left vertex.
    this.vertexData[baseOffset + 8] = bottomLeft.x();
    this.vertexData[baseOffset + 9] = bottomLeft.y();
    this.vertexData[baseOffset + 10] = u0;
    this.vertexData[baseOffset + 11] = v1;
    this.vertexData[baseOffset + 12] = color[0];
    this.vertexData[baseOffset + 13] = color[1];
    this.vertexData[baseOffset + 14] = color[2];
    this.vertexData[baseOffset + 15] = color[3];

    // Top-right vertex.
    this.vertexData[baseOffset + 16] = topRight.x();
    this.vertexData[baseOffset + 17] = topRight.y();
    this.vertexData[baseOffset + 18] = u1;
    this.vertexData[baseOffset + 19] = v0;
    this.vertexData[baseOffset + 20] = color[0];
    this.vertexData[baseOffset + 21] = color[1];
    this.vertexData[baseOffset + 22] = color[2];
    this.vertexData[baseOffset + 23] = color[3];

    // Bottom-right vertex.
    this.vertexData[baseOffset + 24] = bottomRight.x();
    this.vertexData[baseOffset + 25] = bottomRight.y();
    this.vertexData[baseOffset + 26] = u1;
    this.vertexData[baseOffset + 27] = v1;
    this.vertexData[baseOffset + 28] = color[0];
    this.vertexData[baseOffset + 29] = color[1];
    this.vertexData[baseOffset + 30] = color[2];
    this.vertexData[baseOffset + 31] = color[3];

    // Update counters.
    this.currentVertex += 4;
    this.currentQuad += 1;
  }

  // Draws an image from the atlas with its top-right corner at (x, y).
  drawImage(imageName: string, x: number, y: number, color: number[] = [1, 1, 1, 1]): void {
    if (!this.ready || !this.atlasData?.[imageName]) {
      console.warn(
        `Image "${imageName}" not found in atlas or drawer not ready.`
      );
      return;
    }

    const [sx, sy, sw, sh] = this.atlasData[imageName];
    const m = this.atlasMargin;

    // Calculate UV coordinates (normalized 0.0 to 1.0).
    // Add the margin to allow texture filtering to handle edge anti-aliasing.
    const u0 = (sx - m) / this.textureSize.x();
    const v0 = (sy - m) / this.textureSize.y();
    const u1 = (sx + sw + m) / this.textureSize.x();
    const v1 = (sy + sh + m) / this.textureSize.y();

    // Draw the rectangle with the image's texture coordinates.
    // Adjust both UVs and vertex positions by the margin.
    this.drawRect(
      x - m, // Adjust x position by adding margin (from the right).
      y - m,      // Adjust y position by adding margin.
      sw + 2 * m,   // Reduce width by twice the margin (left and right).
      sh + 2 * m,   // Reduce height by twice the margin (top and bottom).
      u0, v0, u1, v1, color
    );
  }

  // Draws an image from the atlas centered at (x, y).
  drawSprite(imageName: string, x: number, y: number, color: number[] = [1, 1, 1, 1]): void {
    if (!this.ready || !this.atlasData?.[imageName]) {
      console.warn(
        `Image "${imageName}" not found in atlas or drawer not ready.`
      );
      return;
    }

    const [sx, sy, sw, sh] = this.atlasData[imageName]; // Source x, y, width, height from atlas.
    const m = this.atlasMargin;

    // Calculate UV coordinates (normalized 0.0 to 1.0).
    // Add the margin to allow texture filtering to handle edge anti-aliasing.
    const u0 = (sx - m) / this.textureSize.x();
    const v0 = (sy - m) / this.textureSize.y();
    const u1 = (sx + sw + m) / this.textureSize.x();
    const v1 = (sy + sh + m) / this.textureSize.y();

    // Draw the rectangle with the image's texture coordinates.
    // For centered drawing, we need to account for the reduced size.
    this.drawRect(
      x - sw / 2 - m, // Center horizontally with margin adjustment.
      y - sh / 2 - m, // Center vertically with margin adjustment.
      sw + 2 * m,         // Reduce width by twice the margin.
      sh + 2 * m,         // Reduce height by twice the margin.
      u0, v0, u1, v1, color
    );
  }

  // Flushes the buffer to the GPU. This is what actually renders images.
  flush(): void {
    if (!this.ready || this.currentQuad === 0 || !this.device) {
      // Don't submit empty command buffers.
      return;
    }

    const device = this.device;

    // Calculate data sizes based on current usage.
    const vertexDataCount = this.currentVertex * 8; // 8 floats per vertex.
    const indexDataCount = this.currentQuad * 6; // 6 indices per quad.

    // Write Data to Buffers.
    this.canvasSize = new Vec2f(this.canvas.width, this.canvas.height);
    device.queue.writeBuffer(
      this.canvasSizeUniformBuffer!,
      0, // Buffer offset.
      this.canvasSize.data // Use Vec2f data directly.
    );

    // Only write the portion of vertex data that we're actually using.
    device.queue.writeBuffer(
      this.vertexBuffer!,
      0, // Buffer offset.
      this.vertexData, // Data.
      0, // Data offset.
      vertexDataCount // Size - only write what we need.
    );

    // Note: We don't need to write the index buffer again since it never changes.

    // Render.
    const commandEncoder = device.createCommandEncoder({ label: 'Frame Command Encoder' });

    // Acquire the canvas texture view *just before* the render pass.
    if (this.renderPassDescriptor && this.context) {
      // Cast the descriptor to help TypeScript understand the structure
      const descriptor = this.renderPassDescriptor as {
        colorAttachments: GPURenderPassColorAttachment[];
      };

      // Update the view
      descriptor.colorAttachments[0].view = this.context.getCurrentTexture().createView();

      const passEncoder = commandEncoder.beginRenderPass(this.renderPassDescriptor);
      passEncoder.setPipeline(this.pipeline!);
      passEncoder.setBindGroup(0, this.bindGroup!);
      passEncoder.setVertexBuffer(0, this.vertexBuffer!);
      passEncoder.setIndexBuffer(this.indexBuffer!, 'uint16'); // Use 16-bit indices.
      passEncoder.drawIndexed(indexDataCount); // Draw only the indices we need.
      passEncoder.end();
    }

    const commandBuffer = commandEncoder.finish();
    device.queue.submit([commandBuffer]);

    // Reset counters after rendering so we can start fresh.
    // This matches the behavior in the auto-flush mechanism.
    this.currentQuad = 0;
    this.currentVertex = 0;
    this.currentIndex = 0;
  }

  // Helper method to generate mipmaps for a texture.
  generateMipmaps(texture: GPUTexture, width: number, height: number): void {
    // Don't try to generate mipmaps if the device doesn't support it.
    if (!this.device || !texture) return;

    // Create a render pipeline for mipmap generation.
    const mipmapShaderModule = this.device.createShaderModule({
      label: 'Mipmap Shader',
      code: `
        struct VertexOutput {
          @builtin(position) position: vec4f,
          @location(0) texCoord: vec2f,
        };

        @vertex
        fn vertexMain(@builtin(vertex_index) vertexIndex: u32) -> VertexOutput {
          var pos = array<vec2f, 4>(
            vec2f(-1.0, -1.0),
            vec2f(1.0, -1.0),
            vec2f(-1.0, 1.0),
            vec2f(1.0, 1.0)
          );

          var texCoord = array<vec2f, 4>(
            vec2f(0.0, 1.0),
            vec2f(1.0, 1.0),
            vec2f(0.0, 0.0),
            vec2f(1.0, 0.0)
          );

          var output: VertexOutput;
          output.position = vec4f(pos[vertexIndex], 0.0, 1.0);
          output.texCoord = texCoord[vertexIndex];
          return output;
        }

        @group(0) @binding(0) var imgSampler: sampler;
        @group(0) @binding(1) var imgTexture: texture_2d<f32>;

        @fragment
        fn fragmentMain(@location(0) texCoord: vec2f) -> @location(0) vec4f {
          return textureSample(imgTexture, imgSampler, texCoord);
        }
      `
    });

    const mipmapPipeline = this.device.createRenderPipeline({
      label: 'Mipmap Pipeline',
      layout: 'auto',
      vertex: {
        module: mipmapShaderModule,
        entryPoint: 'vertexMain',
      },
      fragment: {
        module: mipmapShaderModule,
        entryPoint: 'fragmentMain',
        targets: [{ format: 'rgba8unorm' }],
      },
      primitive: {
        topology: 'triangle-strip',
        stripIndexFormat: 'uint32',
      },
    });

    // Create a temporary sampler for mipmap generation.
    const mipmapSampler = this.device.createSampler({
      minFilter: 'linear',
      magFilter: 'linear',
    });

    // Calculate number of mip levels.
    const mipLevelCount = Math.floor(Math.log2(Math.max(width, height))) + 1;

    // Generate each mip level.
    const commandEncoder = this.device.createCommandEncoder({
      label: 'Mipmap Command Encoder',
    });

    // Create bind groups and render passes for each mip level.
    for (let i = 1; i < mipLevelCount; i++) {
      const srcView = texture.createView({
        baseMipLevel: i - 1,
        mipLevelCount: 1,
      });

      const dstView = texture.createView({
        baseMipLevel: i,
        mipLevelCount: 1,
      });

      // Create bind group for this mip level.
      const bindGroup = this.device.createBindGroup({
        layout: mipmapPipeline.getBindGroupLayout(0),
        entries: [
          { binding: 0, resource: mipmapSampler },
          { binding: 1, resource: srcView },
        ],
      });

      // Render to the next mip level.
      const renderPassDescriptor: GPURenderPassDescriptor = {
        colorAttachments: [
          {
            view: dstView,
            loadOp: 'clear',
            storeOp: 'store',
            clearValue: [0, 0, 0, 0],
          },
        ],
      };

      const passEncoder = commandEncoder.beginRenderPass(renderPassDescriptor);
      passEncoder.setPipeline(mipmapPipeline);
      passEncoder.setBindGroup(0, bindGroup);
      passEncoder.draw(4);
      passEncoder.end();
    }

    this.device.queue.submit([commandEncoder.finish()]);
  }
}

export { Drawer };
