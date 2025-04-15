import { Vec2f, Mat3f } from './vector_math.js';

export class Frame {
  private device: GPUDevice;
  private presentationFormat: GPUTextureFormat;
  private offscreenTexture: GPUTexture;
  private offscreenTextureSize: Vec2f;
  private offscreenView: GPUTextureView;
  private offscreenRenderPassDescriptor: GPURenderPassDescriptor;

  // Texture rendering pipeline and resources
  private texturePipeline: GPURenderPipeline;
  private textureBindGroup: GPUBindGroup;
  private textureSampler: GPUSampler;
  private transformUniformBuffer: GPUBuffer;
  private canvasSizeUniformBuffer: GPUBuffer;
  private quadVertexBuffer: GPUBuffer;
  private quadIndexBuffer: GPUBuffer;

  constructor(
    device: GPUDevice,
    presentationFormat: GPUTextureFormat,
    size: Vec2f = new Vec2f(4096 * 2, 4096 * 2),
    canvasSizeUniformBuffer: GPUBuffer | null = null
  ) {
    this.device = device;
    this.presentationFormat = presentationFormat;
    this.offscreenTextureSize = size;

    // Create the offscreen texture
    this.offscreenTexture = this.device.createTexture({
      label: 'Offscreen Render Target',
      format: presentationFormat,
      size: [this.offscreenTextureSize.x(), this.offscreenTextureSize.y()],
      usage: GPUTextureUsage.RENDER_ATTACHMENT | GPUTextureUsage.TEXTURE_BINDING,
    });

    // Create the offscreen texture view
    this.offscreenView = this.offscreenTexture.createView();

    // Create render pass descriptor for offscreen rendering
    this.offscreenRenderPassDescriptor = {
      label: 'Offscreen Render Pass',
      colorAttachments: [
        {
          view: this.offscreenView,
          clearValue: { r: 0.1, g: 0.1, b: 0.1, a: 1.0 }, // Clear to dark gray
          loadOp: 'clear',
          storeOp: 'store',
        },
      ] as GPURenderPassColorAttachment[],
    } as GPURenderPassDescriptor;

    // Store or create the canvas size uniform buffer
    if (canvasSizeUniformBuffer) {
      this.canvasSizeUniformBuffer = canvasSizeUniformBuffer;
    } else {
      this.canvasSizeUniformBuffer = this.device.createBuffer({
        label: 'canvas size uniform buffer',
        size: 2 * Float32Array.BYTES_PER_ELEMENT, // vec2f (width, height).
        usage: GPUBufferUsage.UNIFORM | GPUBufferUsage.COPY_DST,
      });

      // Initialize with offscreen texture size
      this.device.queue.writeBuffer(
        this.canvasSizeUniformBuffer,
        0,
        this.offscreenTextureSize.data
      );
    }

    // Create a buffer for the transformation matrix
    this.transformUniformBuffer = this.device.createBuffer({
      label: 'transform uniform buffer',
      size: 48, // 48 bytes to match shader's requirement
      usage: GPUBufferUsage.UNIFORM | GPUBufferUsage.COPY_DST,
    });

    // Create a sampler for the offscreen texture
    this.textureSampler = this.device.createSampler({
      addressModeU: 'clamp-to-edge',
      addressModeV: 'clamp-to-edge',
      magFilter: 'linear',
      minFilter: 'linear',
    });

    // Create a quad mesh for rendering the texture
    const quadVertices = new Float32Array([
      // Top down quad like UI, 0 to 1.
      0, 0, 0, 0, // top left
      1, 0, 1, 0, // top right
      0, -1, 0, 1, // bottom left
      1, -1, 1, 1, // bottom right
    ]);

    this.quadVertexBuffer = this.device.createBuffer({
      label: 'quad vertex buffer',
      size: quadVertices.byteLength,
      usage: GPUBufferUsage.VERTEX | GPUBufferUsage.COPY_DST,
    });
    this.device.queue.writeBuffer(this.quadVertexBuffer, 0, quadVertices);

    const quadIndices = new Uint16Array([0, 1, 2, 2, 1, 3]);
    this.quadIndexBuffer = this.device.createBuffer({
      label: 'quad index buffer',
      size: quadIndices.byteLength,
      usage: GPUBufferUsage.INDEX | GPUBufferUsage.COPY_DST,
    });
    this.device.queue.writeBuffer(this.quadIndexBuffer, 0, quadIndices);

    // Create a shader for rendering the texture
    const textureShaderModule = this.device.createShaderModule({
      label: 'Texture Render Shader',
      code: `
        struct VertexInput {
          @location(0) position: vec2f,
          @location(1) texcoord: vec2f,
        };

        struct VertexOutput {
          @builtin(position) position: vec4f,
          @location(0) texcoord: vec2f,
        };

        struct TransformInfo {
          matrix: mat3x3f,
        };
        @group(0) @binding(0) var<uniform> transform: TransformInfo;

        struct CanvasInfo {
          resolution: vec2f,
        };
        @group(0) @binding(1) var<uniform> canvas: CanvasInfo;

        @vertex fn vs(vert: VertexInput) -> VertexOutput {
          var out: VertexOutput;
          // Combined matrix does everything in one step
          let clipPos = transform.matrix * vec3f(vert.position, 1.0);

          out.position = vec4f(clipPos.xy, 0.0, 1.0);
          out.texcoord = vert.texcoord;
          return out;
        }

        @group(0) @binding(2) var texSampler: sampler;
        @group(0) @binding(3) var texture: texture_2d<f32>;

        @fragment fn fs(in: VertexOutput) -> @location(0) vec4f {
          return textureSample(texture, texSampler, in.texcoord);
        }
      `,
    });

    // Create an explicit bind group layout
    const textureBindGroupLayout = this.device.createBindGroupLayout({
      label: 'Texture Bind Group Layout',
      entries: [
        {
          // Transform matrix - used in vertex shader
          binding: 0,
          visibility: GPUShaderStage.VERTEX,
          buffer: {
            type: 'uniform',
            hasDynamicOffset: false,
            minBindingSize: 48 // 48 bytes to match shader's actual usage
          }
        },
        {
          // Canvas resolution - used in vertex shader
          binding: 1,
          visibility: GPUShaderStage.VERTEX,
          buffer: {
            type: 'uniform',
            hasDynamicOffset: false,
            minBindingSize: 2 * Float32Array.BYTES_PER_ELEMENT // vec2f
          }
        },
        {
          // Texture sampler - used in fragment shader
          binding: 2,
          visibility: GPUShaderStage.FRAGMENT,
          sampler: { type: 'filtering' }
        },
        {
          // Texture view - used in fragment shader
          binding: 3,
          visibility: GPUShaderStage.FRAGMENT,
          texture: {
            sampleType: 'float',
            viewDimension: '2d'
          }
        }
      ]
    });

    // Create a pipeline layout using our bind group layout
    const texturePipelineLayout = this.device.createPipelineLayout({
      label: 'Texture Pipeline Layout',
      bindGroupLayouts: [textureBindGroupLayout]
    });

    // Create the pipeline for rendering the texture
    this.texturePipeline = this.device.createRenderPipeline({
      label: 'Texture Render Pipeline',
      layout: texturePipelineLayout, // Use our explicit layout
      vertex: {
        module: textureShaderModule,
        entryPoint: 'vs',
        buffers: [
          {
            // Vertex buffer layout for the quad
            arrayStride: 4 * Float32Array.BYTES_PER_ELEMENT, // 2 pos, 2 uv
            attributes: [
              { shaderLocation: 0, offset: 0, format: 'float32x2' }, // Position
              { shaderLocation: 1, offset: 2 * Float32Array.BYTES_PER_ELEMENT, format: 'float32x2' }, // Texcoord
            ],
          },
        ],
      },
      fragment: {
        module: textureShaderModule,
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
        topology: 'triangle-list',
      },
    });

    // Create the bind group for the texture pipeline
    this.textureBindGroup = this.device.createBindGroup({
      label: 'Texture Render Bind Group',
      layout: textureBindGroupLayout, // Use our explicit layout
      entries: [
        { binding: 0, resource: { buffer: this.transformUniformBuffer } },
        { binding: 1, resource: { buffer: this.canvasSizeUniformBuffer } },
        { binding: 2, resource: this.textureSampler },
        { binding: 3, resource: this.offscreenView },
      ],
    });
  }

  // Get the render pass descriptor for rendering to this frame
  getRenderPassDescriptor(): GPURenderPassDescriptor {
    return this.offscreenRenderPassDescriptor;
  }

  // Get the view for this frame
  getView(): GPUTextureView {
    return this.offscreenView;
  }

  // Get the size of this frame
  getSize(): Vec2f {
    return this.offscreenTextureSize;
  }

  // Clear the frame
  clear(): void {
    try {
      const commandEncoder = this.device.createCommandEncoder({ label: 'Clear Command Encoder' });
      const passEncoder = commandEncoder.beginRenderPass(this.offscreenRenderPassDescriptor);
      passEncoder.end();
      this.device.queue.submit([commandEncoder.finish()]);
    } catch (error) {
      console.warn("Error clearing offscreen texture:", error);
    }
  }

  // Draw the frame to a canvas
  drawToScreen(
    canvas: HTMLCanvasElement,
    context: GPUCanvasContext,
    transform: Mat3f = Mat3f.identity(),
    clearScreen: boolean = true
  ): void {
    try {
      // Update the canvas size uniform buffer with actual canvas size
      const canvasSize = new Vec2f(canvas.width, canvas.height);
      this.device.queue.writeBuffer(
        this.canvasSizeUniformBuffer,
        0,
        canvasSize.data
      );

      // Calculate the screen transform to map the offscreen texture to the canvas.
      var screenTransform = Mat3f.identity();
      screenTransform = screenTransform.mul(Mat3f.translate(-1, 1));
      screenTransform = screenTransform.mul(Mat3f.scale(
        2 * this.offscreenTextureSize.x() / canvas.width,
        2 * this.offscreenTextureSize.y() / canvas.height)
      );

      // Convert the provided transform to the screen transform.
      const transformCopy = new Mat3f(
        transform.get(0, 0), transform.get(0, 1), transform.get(0, 2),
        transform.get(1, 0), transform.get(1, 1), transform.get(1, 2),
        transform.get(2, 0), transform.get(2, 1), transform.get(2, 2)
      );
      transformCopy.data[2] = transformCopy.data[2] / this.offscreenTextureSize.x();
      transformCopy.data[5] = - (transformCopy.data[5] / this.offscreenTextureSize.y());
      const finalTransform = screenTransform.mul(transformCopy);

      // Create a padded array for WebGPU's alignment requirements
      // WebGPU expects each row of the matrix to be aligned to 16 bytes (4 floats)
      const paddedMatrix = new Float32Array(12);

      // Copy the matrix data into the padded array with the correct layout
      paddedMatrix[0] = finalTransform.data[0];
      paddedMatrix[1] = finalTransform.data[1];
      paddedMatrix[2] = 0;
      paddedMatrix[3] = 0;

      paddedMatrix[4] = finalTransform.data[3];
      paddedMatrix[5] = finalTransform.data[4];
      paddedMatrix[6] = 0;
      paddedMatrix[7] = 0;

      paddedMatrix[8] = finalTransform.data[2];
      paddedMatrix[9] = finalTransform.data[5];
      paddedMatrix[10] = 1;
      paddedMatrix[11] = 0;

      // Write the transform to the GPU
      this.device.queue.writeBuffer(
        this.transformUniformBuffer,
        0,
        paddedMatrix
      );

      // Create a command encoder for rendering to canvas
      const renderCommandEncoder = this.device.createCommandEncoder({ label: 'Display Texture Encoder' });

      // Create a render pass for the canvas
      const canvasRenderPassDescriptor: GPURenderPassDescriptor = {
        label: 'Canvas Render Pass',
        colorAttachments: [
          {
            view: context.getCurrentTexture().createView(),
            clearValue: { r: 0.1, g: 0.1, b: 0.1, a: 1.0 }, // Dark gray background
            loadOp: clearScreen ? 'clear' : 'load', // Use 'load' if not clearing
            storeOp: 'store',
          },
        ],
      };

      // Render the texture to the canvas
      const passEncoder = renderCommandEncoder.beginRenderPass(canvasRenderPassDescriptor);
      passEncoder.setPipeline(this.texturePipeline);
      passEncoder.setBindGroup(0, this.textureBindGroup);
      passEncoder.setVertexBuffer(0, this.quadVertexBuffer);
      passEncoder.setIndexBuffer(this.quadIndexBuffer, 'uint16');
      passEncoder.drawIndexed(6); // 6 indices for the quad (2 triangles)
      passEncoder.end();

      // Submit the command to render to canvas
      this.device.queue.submit([renderCommandEncoder.finish()]);
    } catch (error) {
      console.error("Error in drawToScreen:", error);
    }
  }
}
