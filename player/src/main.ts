import { Vec2f, Mat3f } from './vector_math.js';
import { Grid } from './grid.js';
import { Drawer } from './drawer.js';

export class PanelInfo {
  public x: number = 0;
  public y: number = 0;
  public width: number = 0;
  public height: number = 0;
  public name: string = "";
  public panPos: Vec2f = new Vec2f(0, 0);
  public zoomLevel: number = 1;
  public canvas: HTMLCanvasElement;
  //public ctx: CanvasRenderingContext2D | null;
  public div: HTMLDivElement | null;
  public transform: Mat3f;

  constructor(name: string) {
    this.name = name;
    this.canvas = document.createElement('canvas');
    this.canvas.setAttribute('id', name + '-canvas');
    //this.ctx = this.canvas.getContext('2d');
    this.div = null;
    this.transform = Mat3f.identity();
  }

  // Check if a point is inside the panel.
  inside(point: Vec2f): boolean {
    return point.x() >= this.x && point.x() < this.x + this.width &&
      point.y() >= this.y && point.y() < this.y + this.height;
  }

  // Transform a point from the canvas to the map coordinate system.
  transformPoint(point: Vec2f): Vec2f {
    this.transform = Mat3f.translate(
      this.panPos.x() + this.x, this.panPos.y() + this.y
    ).mul(Mat3f.scale(this.zoomLevel, this.zoomLevel));
    return this.transform.inverse().transform(point);
  }

  // Update the pan and zoom level based on the mouse position and scroll delta.
  updatePanAndZoom(): boolean {
    if (mouseDown && mousePos.sub(lastMousePos).length() > 1) {
      this.panPos = this.panPos.add(mousePos.sub(lastMousePos));
      lastMousePos = mousePos;
      return true;
    }

    if (scrollDelta !== 0) {
      const oldMousePoint = this.transformPoint(mousePos);
      this.zoomLevel = this.zoomLevel + scrollDelta / SCROLL_ZOOM_FACTOR;
      this.zoomLevel = Math.max(Math.min(this.zoomLevel, MAX_ZOOM_LEVEL), MIN_ZOOM_LEVEL);
      const newMousePoint = this.transformPoint(mousePos);
      if (oldMousePoint != null && newMousePoint != null) {
        this.panPos = this.panPos.add(newMousePoint.sub(oldMousePoint).mul(this.zoomLevel));
      }
      return true;
    }
    return false;
  }
}

// Constants
const MIN_ZOOM_LEVEL = 0.1;
const MAX_ZOOM_LEVEL = 2.0;
const SPLIT_DRAG_THRESHOLD = 10;  // pixels to detect split dragging
const SCROLL_ZOOM_FACTOR = 1000;  // divisor for scroll delta to zoom conversion
const DEFAULT_TRACE_SPLIT = 0.80;  // default horizontal split ratio
const DEFAULT_INFO_SPLIT = 0.25;   // default vertical split ratio
const PANEL_BOTTOM_MARGIN = 60;    // bottom margin for panels

let drawer: Drawer;

// Get the html elements we will use.
const scrubber = document.getElementById('main-scrubber') as HTMLInputElement;
const playButton = document.getElementById('play-button') as HTMLButtonElement;

// Get the canvas element.
const globalCanvas = document.getElementById('global-canvas') as HTMLCanvasElement;

const mapPanel = new PanelInfo("map");
const tracePanel = new PanelInfo("trace");
const infoPanel = new PanelInfo("info");

// Get the modal element
const modal = document.getElementById('modal');

// Constants
const AGENT_STYLES = {
  "body": 4,
  "eyes": 4,
  "horns": 4,
  "hair": 4,
  "mouth": 4,
}

const ACTION_COLORS = {
  "put_recipe_items": "#3498DB", // blueish
  "get_output": "#2980B9", // blueish
  "noop": "#95A5A6", // grayish
  "move": "#2ECC71", // greenish
  "rotate": "#27AE60", // greenish
  "attack": "#E74C3C", // reddish
  "attack_nearest": "#C0392B", // reddish
  "swap": "#E74C3C", // reddish
  "change_color": "#F39C12" // orange ish
}

const ACTION_IMPORTANCE = {
  "put_recipe_items": 3,
  "get_output": 3,
  "noop": 1,
  "move": 1,
  "rotate": 1,
  "attack": 10,
  "attack_nearest": 10,
  "swap": 6,
  "change_color": 3
}

const INVENTORY = [
  "armor",
  "battery",
  "blueprint",
  "heart",
  "laser",
  "ore.blue",
  "ore.green",
  "ore.red",
]

// Interaction state.
let mouseDown = false;
let mousePos = new Vec2f(0, 0);
let lastMousePos = new Vec2f(0, 0);
let scrollDelta = 0;

let traceSplit = DEFAULT_TRACE_SPLIT;
let traceDragging = false;
let infoSplit = DEFAULT_INFO_SPLIT
let infoDragging = false;
// Replay data and player state.
let replay: any = null;
let step = 0;
let selectedGridObject: any = null;

// Playback state
let isPlaying = false;
let playbackInterval: number | null = null;
let playbackSpeed = 5; // frames per playback step

// Handle resize events.
function onResize() {
  // Adjust for high DPI displays.
  const dpr = window.devicePixelRatio || 1;

  const mapWidth = window.innerWidth;
  const mapHeight = window.innerHeight;

  // Make sure traceSplit and infoSplit are not too small or too large.
  const a = 0.025;
  traceSplit = Math.max(a, Math.min(traceSplit, 1 - a));
  infoSplit = Math.max(a, Math.min(infoSplit, 1 - a));

  mapPanel.x = 0;
  mapPanel.y = 0;
  mapPanel.width = mapWidth * traceSplit;
  mapPanel.height = mapHeight - PANEL_BOTTOM_MARGIN;

  tracePanel.x = mapWidth * traceSplit;
  tracePanel.y = mapHeight * infoSplit;
  tracePanel.width = mapWidth * (1 - traceSplit);
  tracePanel.height = mapHeight * (1 - infoSplit) - PANEL_BOTTOM_MARGIN;

  infoPanel.x = mapWidth * traceSplit;
  infoPanel.y = 0;
  infoPanel.width = mapWidth * (1 - traceSplit);
  infoPanel.height = mapHeight * infoSplit
  if (infoPanel.div === null) {
    infoPanel.div = document.createElement("div");
    infoPanel.div.id = infoPanel.name + "-div";
    document.body.appendChild(infoPanel.div);
  }
  if (infoPanel.div !== null) {
    const div = infoPanel.div;
    div.style.position = 'absolute';
    div.style.top = infoPanel.y + 'px';
    div.style.left = infoPanel.x + 'px';
    div.style.width = infoPanel.width + 'px';
    div.style.height = infoPanel.height + 'px';
  }

  // Redraw the square after resizing.
  onFrame();
}

// Handle mouse down events.
function onMouseDown() {
  lastMousePos = mousePos;

  if (Math.abs(mousePos.x() - mapPanel.width) < SPLIT_DRAG_THRESHOLD) {
    traceDragging = true
    console.log("Started trace dragging")
  } else if (mousePos.x() > mapPanel.width && Math.abs(mousePos.y() - infoPanel.height) < SPLIT_DRAG_THRESHOLD) {
    infoDragging = true
    console.log("Started info dragging")
  } else {
    mouseDown = true;
  }

  onFrame();
}

// Handle mouse up events.
function onMouseUp() {
  mouseDown = false;
  traceDragging = false;
  infoDragging = false;
  onFrame();
}

// Handle mouse move events.
function onMouseMove(event: MouseEvent) {
  mousePos = new Vec2f(event.clientX, event.clientY);

  // If mouse is close to a panels edge change cursor to edge changer.
  document.body.style.cursor = "default";

  if (Math.abs(mousePos.x() - mapPanel.width) < SPLIT_DRAG_THRESHOLD) {
    document.body.style.cursor = "ew-resize";
  }

  if (mousePos.x() > mapPanel.width && Math.abs(mousePos.y() - infoPanel.height) < SPLIT_DRAG_THRESHOLD) {
    document.body.style.cursor = "ns-resize";
  }

  if (traceDragging) {
    traceSplit = mousePos.x() / window.innerWidth
    onResize();
  } else if (infoDragging) {
    infoSplit = mousePos.y() / window.innerHeight
    onResize()
  } else if (mouseDown) {
    onFrame();
  }
}

// Handle scroll events.
function onScroll(event: WheelEvent) {
  scrollDelta = event.deltaY;
  onFrame();
  scrollDelta = 0;
}

// Decompress a stream, used for compressed JSON from fetch or drag and drop.
async function decompressStream(stream: ReadableStream<Uint8Array>): Promise<string> {
  const decompressionStream = new DecompressionStream('deflate');
  const decompressedStream = stream.pipeThrough(decompressionStream);

  const reader = decompressedStream.getReader();
  const chunks: Uint8Array[] = [];
  let result;
  while (!(result = await reader.read()).done) {
    chunks.push(result.value);
  }

  const totalLength = chunks.reduce((acc, val) => acc + val.length, 0);
  const flattenedChunks = new Uint8Array(totalLength);

  let offset = 0;
  for (const chunk of chunks) {
    flattenedChunks.set(chunk, offset);
    offset += chunk.length;
  }

  const decoder = new TextDecoder();
  return decoder.decode(flattenedChunks);
}

// Load the replay from a URL.
async function fetchReplay(replayUrl: string) {
  try {
    const response = await fetch(replayUrl);
    if (!response.ok) {
      throw new Error("Network response was not ok");
    }
    if (response.body === null) {
      throw new Error("Response body is null");
    }
    // Check the Content-Type header
    const contentType = response.headers.get('Content-Type');
    console.log("Content-Type: ", contentType);
    if (contentType === "application/json") {
      let replayData = await response.text();
      loadReplayText(replayData);
    } else if (contentType === "application/x-compress" || contentType === "application/octet-stream") {
      // Compressed JSON.
      const decompressedData = await decompressStream(response.body);
      loadReplayText(decompressedData);
    } else {
      throw new Error("Unsupported content type: " + contentType);
    }
  } catch (error) {
    showModal("error", "Error fetching replay", "Message: " + error);
  }
}

// Read a file from drag and drop.
async function readFile(file: File) {
  try {
    const contentType = file.type;
    console.log("Content-Type: ", contentType);
    if (contentType === "application/json") {
      loadReplayText(await file.text());
    } else if (contentType === "application/x-compress" || contentType === "application/octet-stream") {
      // Compressed JSON.
      console.log("Decompressing file");
      const decompressedData = await decompressStream(file.stream());
      console.log("Decompressed file");
      loadReplayText(decompressedData);
    }
  } catch (error) {
    showModal("error", "Error reading file", "Message: " + error);
  }
}

// Expand a sequence of values
// [[0, value1], [2, value2], ...] -> [value1, value1, value2, ...]
function expandSequence(sequence: any[], numSteps: number): any[] {
  var expanded: any[] = [];
  var i = 0
  var j = 0
  var v: any = null
  for (i = 0; i < numSteps; i++) {
    if (j < sequence.length && sequence[j][0] == i) {
      v = sequence[j][1];
      j++;
    }
    expanded.push(v);
  }
  return expanded;
}

// Load the replay text.
async function loadReplayText(replayData: any) {
  replay = JSON.parse(replayData);
  console.log("replay: ", replay);

  // Go through each grid object and expand its key sequence.
  for (const gridObject of replay.grid_objects) {
    for (const key in gridObject) {
      if (gridObject[key] instanceof Array) {
        gridObject[key] = expandSequence(gridObject[key], replay.max_steps);
      }
    }
  }

  // Set the scrubber max value to the max steps.
  scrubber.max = replay.max_steps.toString();

  closeModal();
  focusFullMap(mapPanel);
  onFrame();
}

// Handle scrubber change events.
function onScrubberChange() {
  step = parseInt(scrubber.value);
  const fillWidth = (step / parseInt(scrubber.max)) * 100;
  scrubber.style.setProperty('--fill-width', `${fillWidth}%`);
  console.log("step: ", step);
  onFrame();
}

// Handle key down events.
function onKeyDown(event: KeyboardEvent) {
  if (event.key == "Escape") {
    selectedGridObject = null;
  }
  // '[' and ']' to scrub forward and backward.
  if (event.key == "[") {
    step = Math.max(step - 1, 0);
    scrubber.value = step.toString();
  }
  if (event.key == "]") {
    step = Math.min(step + 1, replay.max_steps);
    scrubber.value = step.toString();
  }
  // '<' and '>' control the playback speed.
  if (event.key == ",") {
    playbackSpeed = Math.max(playbackSpeed - 1, 1);
    console.log("playbackSpeed: ", playbackSpeed);
  }
  if (event.key == ".") {
    playbackSpeed = Math.min(playbackSpeed + 1, 1000);
    console.log("playbackSpeed: ", playbackSpeed);
  }
  // If space make it press the play button.
  if (event.key == " ") {
    onPlayButtonClick();
  }
  onFrame();
}

// Gets an attribute from a grid object respecting the current step.
function getAttr(obj: any, attr: string, atStep = -1): any {
  if (atStep == -1) {
    // When step is not defined, use global step.
    atStep = step;
  }
  if (obj[attr] === undefined) {
    return 0;
  } else if (obj[attr] instanceof Array) {
    //return findInSeries(obj[attr], atStep);
    return obj[attr][atStep];
  } else {
    // Must be a constant that does not change over time.
    return obj[attr];
  }
}

function getAgentStyle(agentId: number) {
  const n = 4; // number of variations per trait
  return {
    bodyId: Math.floor(agentId * Math.PI) % AGENT_STYLES.body,
    eyesId: Math.floor(agentId * Math.E) % AGENT_STYLES.eyes,
    hornsId: Math.floor(agentId * Math.SQRT2) % AGENT_STYLES.horns,
    hairId: Math.floor(agentId * 2.236) % AGENT_STYLES.hair,  // sqrt(5)
    mouthId: Math.floor(agentId * 2.645) % AGENT_STYLES.mouth  // sqrt(7)
  };
}

// Make the panel focus on the full map, used at the start of the replay.
function focusFullMap(panel: PanelInfo) {
  if (replay === null) {
    return;
  }
  const mapWidth = replay.map_size[0] * 64;
  const mapHeight = replay.map_size[1] * 64;
  const panelWidth = panel.width;
  const panelHeight = panel.height;
  const zoomLevel = Math.min(panelWidth / mapWidth, panelHeight / mapHeight);
  panel.panPos = new Vec2f(
    (panelWidth - mapWidth * zoomLevel) / 2,
    (panelHeight - mapHeight * zoomLevel) / 2
  );
  panel.zoomLevel = zoomLevel;
}

// Make the panel focus on a specific agent.
function focusMapOn(panel: PanelInfo, x: number, y: number) {
  panel.panPos = new Vec2f(
    -x * 64 + panel.width / 2,
    -y * 64 + panel.height / 2
  );
  panel.zoomLevel = 1;
}

// Draw the tiles that make up the floor.
function drawFloor(mapSize: [number, number]) {
  for (let x = 0; x < mapSize[0]; x++) {
    for (let y = 0; y < mapSize[1]; y++) {
      drawer.drawSprite('floor.png', x * 64, y * 64);
    }
  }
}

// Draw the walls, based on the adjacency map, and fill any holes.
function drawWalls(replay: any) {
  // Construct wall adjacency map.
  var wallMap = new Grid(replay.map_size[0], replay.map_size[1]);
  for (const gridObject of replay.grid_objects) {
    const type = gridObject.type;
    const typeName = replay.object_types[type];
    if (typeName !== "wall") {
      continue;
    }
    const x = getAttr(gridObject, "c");
    const y = getAttr(gridObject, "r");
    wallMap.set(x, y, true);
  }

  // Draw the walls following the adjacency map.
  for (const gridObject of replay.grid_objects) {
    const type = gridObject.type;
    const typeName = replay.object_types[type];
    if (typeName !== "wall") {
      continue;
    }
    const x = getAttr(gridObject, "c");
    const y = getAttr(gridObject, "r");
    var suffix = "0";
    var n = false, w = false, e = false, s = false;
    if (wallMap.get(x, y - 1)) {
      n = true;
    }
    if (wallMap.get(x - 1, y)) {
      w = true;
    }
    if (wallMap.get(x, y + 1)) {
      s = true;
    }
    if (wallMap.get(x + 1, y)) {
      e = true;
    }
    if (n || w || e || s) {
      suffix = (n ? "n" : "") + (w ? "w" : "") + (s ? "s" : "") + (e ? "e" : "");
    }
    drawer.drawSprite('wall.' + suffix + '.png', x * 64, y * 64);
  }

  // Draw the wall in-fill following the adjacency map.
  for (const gridObject of replay.grid_objects) {
    const type = gridObject.type;
    const typeName = replay.object_types[type];
    if (typeName !== "wall") {
      continue;
    }
    const x = getAttr(gridObject, "c");
    const y = getAttr(gridObject, "r");
    // If walls to E, S and SE is filled, draw a wall fill.
    var s = false, e = false, se = false;
    if (wallMap.get(x + 1, y)) {
      e = true;
    }
    if (wallMap.get(x, y + 1)) {
      s = true;
    }
    if (wallMap.get(x + 1, y + 1)) {
      se = true;
    }
    if (e && s && se) {
      drawer.drawSprite('wall.fill.png', x * 64 + 32, y * 64 + 32);
    }
  }
}

// Draw all objects on the map (that are not walls).
function drawObjects(replay: any) {
  for (const gridObject of replay.grid_objects) {
    const type = gridObject.type;
    const typeName = replay.object_types[type]
    if (typeName === "wall") {
      // Walls are drawn in a different way.
      continue;
    }
    const x = getAttr(gridObject, "c")
    const y = getAttr(gridObject, "r")

    if (gridObject["agent_id"] !== undefined) {
      // Respect orientation of an object usually an agent.
      const orientation = getAttr(gridObject, "agent:orientation");
      var suffix = "";
      if (orientation == 0) {
        suffix = ".n";
      } else if (orientation == 1) {
        suffix = ".s";
      } else if (orientation == 2) {
        suffix = ".w";
      } else if (orientation == 3) {
        suffix = ".e";
      }

      const agent_id = gridObject["agent_id"];

      const style = getAgentStyle(agent_id);
      drawer.drawSprite(typeName + suffix + ".body." + style.bodyId + ".png", x * 64, y * 64);
      drawer.drawSprite(typeName + suffix + ".hair." + style.hairId + ".png", x * 64, y * 64);
      drawer.drawSprite(typeName + suffix + ".mouth." + style.mouthId + ".png", x * 64, y * 64);
      drawer.drawSprite(typeName + suffix + ".horns." + style.hornsId + ".png", x * 64, y * 64);
      drawer.drawSprite(typeName + suffix + ".eyes." + style.eyesId + ".png", x * 64, y * 64);

    } else {
      // Draw other objects.
      drawer.drawSprite(typeName + ".png", x * 64, y * 64);
    }
  }

  // Draw actions above the objects.
  for (const gridObject of replay.grid_objects) {
    const type = gridObject.type;
    const typeName = replay.object_types[type]
    const x = getAttr(gridObject, "c")
    const y = getAttr(gridObject, "r")

    if (gridObject["action"] !== undefined) {
      // Draw the action:
      const action = getAttr(gridObject, "action");
      const action_success = getAttr(gridObject, "action_success");
      const action_name = replay.action_names[action[0]];
      const orientation = getAttr(gridObject, "agent:orientation");
      if (action_name == "attack") {
        drawer.save()
        drawer.translate(x * 64, y * 64);
        if (orientation == 0) {
          drawer.rotate(Math.PI / 2);
        } else if (orientation == 1) {
          drawer.rotate(-Math.PI / 2);
        } else if (orientation == 2) {
          drawer.rotate(Math.PI);
        } else if (orientation == 3) {
          drawer.rotate(0);
        }
        drawer.drawSprite("attack" + (action[1] + 1) + ".png", 0, 0);
        drawer.restore()
      } else if (action_name == "put_recipe_items") {
        drawer.save()
        drawer.translate(x * 64, y * 64);
        if (orientation == 0) {
          drawer.rotate(Math.PI / 2);
        } else if (orientation == 1) {
          drawer.rotate(-Math.PI / 2);
        } else if (orientation == 2) {
          drawer.rotate(Math.PI);
        } else if (orientation == 3) {
          drawer.rotate(0);
        }
        drawer.drawSprite("put_recipe_items.png", 0, 0);
        drawer.restore()
      } else if (action_name == "get_output") {
        drawer.save()
        drawer.translate(x * 64, y * 64);
        if (orientation == 0) {
          drawer.rotate(Math.PI / 2);
        } else if (orientation == 1) {
          drawer.rotate(-Math.PI / 2);
        } else if (orientation == 2) {
          drawer.rotate(Math.PI);
        } else if (orientation == 3) {
          drawer.rotate(0);
        }
        drawer.drawSprite("get_output.png", 0, 0);
        drawer.restore()
      }
    }
  }

  // Draw the object's inventory.
  for (const gridObject of replay.grid_objects) {
    const type = gridObject.type;
    const typeName = replay.object_types[type]
    const x = getAttr(gridObject, "c")
    const y = getAttr(gridObject, "r")

    // Draw the agent's inventory.
    let inventoryX = 0;
    for (const item of INVENTORY) {
      const num = getAttr(gridObject, "agent:inv:" + item);
      for (let i = 0; i < num; i++) {
        drawer.save()
        drawer.translate(x * 64 + inventoryX * 8 - 32, y * 64 - 32);
        drawer.scale(0.25, 0.25);
        drawer.drawSprite(item + ".png", 0, 0);
        drawer.restore()
        inventoryX++;
      }
    }
  }
}

function drawSelection(selectedObject: any | null, step: number) {
  if (selectedObject === null) {
    return;
  }

  const x = getAttr(selectedObject, "c")
  const y = getAttr(selectedObject, "r")
  drawer.drawSprite("agent_selection.png", x * 64, y * 64);

  // If object has a trajectory, draw the path it took through the map.
  if (selectedObject.c.length > 0 || selectedObject.r.length > 0) {

    // Draw both past and future trajectories.
    for (let i = 1; i < replay.max_steps; i++) {
      const cx0 = getAttr(selectedObject, "c", i - 1);
      const cy0 = getAttr(selectedObject, "r", i - 1);
      const cx1 = getAttr(selectedObject, "c", i);
      const cy1 = getAttr(selectedObject, "r", i);
      if (cx0 !== cx1 || cy0 !== cy1) {
        const a = 1 - Math.abs(i - step) / 200;
        if (a > 0) {
          let color = [0, 0, 0, a];
          if (step >= i) {
            // Past trajectory is black.
            color = [0, 0, 0, a];
          } else {
            // Future trajectory is white.
            color = [a, a, a, a];
          }

          if (cx1 > cx0) { // right
            drawer.drawSolidRect(cx0 * 64, cy0 * 64, 64, 2, color);
          } else if (cx1 < cx0) { // left
            drawer.drawSolidRect(cx1 * 64, cy1 * 64, 64, 2, color);
          } else if (cy1 > cy0) { // down
            drawer.drawSolidRect(cx0 * 64, cy0 * 64, 2, 64, color);
          } else if (cy1 < cy0) {
            drawer.drawSolidRect(cx0 * 64, cy1 * 64, 2, 64, color);
          }
        }
      }
    }
  }
}

function drawMap(panel: PanelInfo) {
  if (replay === null || drawer === null || drawer.ready === false) {
    return;
  }

  if (mouseDown) {
    const localMousePos = panel.transformPoint(mousePos);
    if (localMousePos != null) {
      const gridMousePos = new Vec2f(
        Math.round(localMousePos.x() / 64),
        Math.round(localMousePos.y() / 64)
      );
      const gridObject = replay.grid_objects.find((obj: any) => {
        const x: number = getAttr(obj, "c");
        const y: number = getAttr(obj, "r");
        return x === gridMousePos.x() && y === gridMousePos.y();
      });
      if (gridObject !== undefined) {
        selectedGridObject = gridObject;
        console.log("selectedGridObject: ", selectedGridObject);
      }
    }
  }

  drawer.save();
  drawer.setScissorRect(panel.x, panel.y, panel.width, panel.height);

  drawer.translate(panel.panPos.x(), panel.panPos.y());
  drawer.scale(panel.zoomLevel, panel.zoomLevel);

  drawFloor(replay.map_size);
  drawWalls(replay);
  drawObjects(replay);
  drawSelection(selectedGridObject, step);

  drawer.restore();
}

function drawTrace(panel: PanelInfo) {
  if (replay === null || drawer === null || drawer.ready === false) {
    return;
  }

  //const panelMousePos = new Vec2f(mousePos.x() - panel.x, mousePos.y() - panel.y);
  const localMousePos = panel.transformPoint(mousePos);

  if (panel.inside(mousePos)) {
    if (localMousePos != null) {
      if (mouseDown) {
        const mapX = localMousePos.x();
        if (mapX > 0 && mapX < replay.max_steps * 4 &&
          localMousePos.y() > 0 && localMousePos.y() < replay.num_agents * 64) {
          const agentId = Math.floor(localMousePos.y() / 64);
          for (const gridObject of replay.grid_objects) {
            if (gridObject["agent_id"] == agentId) {
              selectedGridObject = gridObject;
              console.log("selectedGridObject: ", selectedGridObject);
              focusMapOn(mapPanel, getAttr(selectedGridObject, "c"), getAttr(selectedGridObject, "r"));
            }
          }
          step = Math.floor(mapX / 4);
          scrubber.value = step.toString();
        }
      }
    }
  }

  drawer.save();
  drawer.setScissorRect(panel.x, panel.y, panel.width, panel.height);

  const fullSize = new Vec2f(replay.max_steps * 4, replay.num_agents * 64);

  // Draw background
  drawer.drawSolidRect(
    panel.x, panel.y, panel.width, panel.height,
    [0.08, 0.08, 0.08, 1.0] // Dark background
  );

  drawer.translate(panel.x, panel.y);
  drawer.translate(panel.panPos.x(), panel.panPos.y());
  drawer.scale(panel.zoomLevel, panel.zoomLevel);

  // Draw rectangle around the selected agent
  if (selectedGridObject !== null && selectedGridObject.agent_id !== undefined) {
    const agentId = selectedGridObject.agent_id;

    // Draw selection rectangle
    drawer.drawSolidRect(
      0, agentId * 64, fullSize.x(), 64,
      [.3, .3, .3, 1]
    );
  }

  // Draw current step line that goes through all of the traces
  drawer.drawSolidRect(
    step * 4, 0,
    2, fullSize.y(),
    [1.0, 1.0, 1.0, 0.5] // White with 50% opacity
  );

  // Draw agent traces
  for (let i = 0; i < replay.num_agents; i++) {

    // Draw the agent's actions
    for (const gridObject of replay.grid_objects) {
      if (gridObject["agent_id"] == i) {
        for (let j = 0; j < replay.max_steps; j++) {
          const action = getAttr(gridObject, "action", j);
          const action_success = getAttr(gridObject, "action_success", j);

          if (action_success) {
            const actionName = replay.action_names[action[0]] as string;
            const color = ACTION_COLORS[actionName as keyof typeof ACTION_COLORS];
            const importance = ACTION_IMPORTANCE[actionName as keyof typeof ACTION_IMPORTANCE];

            // Convert hex color to RGBA array
            const rgbaColor = hexToRgba(color);
            drawer.drawSolidRect(
              j * 4, i * 64 + 32 - 2 * importance,
              2, 4 * importance,
              rgbaColor
            );
          } else {
            drawer.drawSolidRect(
              j * 4, i * 64 + 32 - 2,
              2, 4,
              [0.12, 0.12, 0.12, 1.0] // Dark gray
            );
          }

          const reward = getAttr(gridObject, "reward", j);
          // If there is reward, draw a sharp bar
          if (reward > 0) {
            const importance = 16;
            drawer.drawSolidRect(
              j * 4 - 1, i * 64 + 32 - 2 * importance,
              4, 4 * importance,
              [0.97, 0.89, 0.47, 1.0] // Gold color approximating HSL(46, 100%, 76.7%)
            );
          }
        }
      }
    }
  }

  drawer.restore();
}

// Helper function to convert hex color to RGBA array
function hexToRgba(hex: string): number[] {
  // Remove the # if present
  hex = hex.replace('#', '');

  // Parse the hex values
  const r = parseInt(hex.substring(0, 2), 16) / 255;
  const g = parseInt(hex.substring(2, 4), 16) / 255;
  const b = parseInt(hex.substring(4, 6), 16) / 255;

  return [r, g, b, 1.0]; // Full opacity
}

// Updates the readout of the selected object or replay info.
function updateReadout() {
  var readout = ""
  if (selectedGridObject !== null) {
    for (const key in selectedGridObject) {
      var value = getAttr(selectedGridObject, key);
      if (key == "type") {
        value = replay.object_types[value];
      }
      readout += key + ": " + value + "\n";
    }
  } else {
    readout += "Step: " + step + "\n";
    readout += "Map size: " + replay.map_size[0] + "x" + replay.map_size[1] + "\n";
    readout += "Num agents: " + replay.num_agents + "\n";
    readout += "Max steps: " + replay.max_steps + "\n";

    var objectTypeCounts = new Map<string, number>();
    for (const gridObject of replay.grid_objects) {
      const type = gridObject.type;
      const typeName = replay.object_types[type];
      objectTypeCounts.set(typeName, (objectTypeCounts.get(typeName) || 0) + 1);
    }
    for (const [key, value] of objectTypeCounts.entries()) {
      readout += key + " count: " + value + "\n";
    }
  }
  if (infoPanel.div !== null) {
    infoPanel.div.innerHTML = readout;
  }
}

// Draw a frame.
function onFrame() {
  if (replay === null || drawer === null || drawer.ready === false) {
    return;
  }

  // Make sure the canvas is the size of the window.
  globalCanvas.width = window.innerWidth;
  globalCanvas.height = window.innerHeight;

  drawer.clear();

  var fullUpdate = true;
  if (mapPanel.inside(mousePos)) {
    if (mapPanel.updatePanAndZoom()) {
      fullUpdate = false;
    }
  }

  if (tracePanel.inside(mousePos)) {
    if (tracePanel.updatePanAndZoom()) {
      fullUpdate = false;
    }
  }

  updateReadout();
  drawer.useMesh("map");
  drawMap(mapPanel);
  drawer.useMesh("trace");
  drawTrace(tracePanel);

  // /Users/me/p/mettagrid/player/data/meta_grid_icon.png
  //drawer.drawSprite('meta_grid_icon.png', 100, 100);
  drawer.drawSolidRect(100, 100, 100, 100, [1, 1, 1, 1]);

  drawer.flush();
  console.log("Flushed drawer.");
}

function preventDefaults(event: Event) {
  event.preventDefault();
  event.stopPropagation();
}

function handleDrop(event: DragEvent) {
  event.preventDefault();
  event.stopPropagation();
  const dt = event.dataTransfer;
  if (dt && dt.files.length) {
    const file = dt.files[0];
    readFile(file);
  }
}

// Function to get URL parameters
function getUrlParameter(name: string): string | null {
  const urlParams = new URLSearchParams(window.location.search);
  return urlParams.get(name);
}

// Show the modal
function showModal(type: string, title: string, message: string) {
  if (modal) {
    modal.style.display = 'block';
    modal.classList.add(type);
    const header = modal.querySelector('h2');
    if (header) {
      header.textContent = title;
    }
    const content = modal.querySelector('p');
    if (content) {
      content.textContent = message;
    }
  }
}

// Close the modal
function closeModal() {
  if (modal) {
    // Remove error class from modal.
    modal.classList.remove('error');
    modal.classList.remove('info');
    modal.style.display = 'none';
  }
}

// Handle play button click
function onPlayButtonClick() {
  isPlaying = !isPlaying;

  if (isPlaying) {
    playButton.classList.add('paused');

    playbackInterval = window.setInterval(() => {
      if (replay === null) return;

      // Advance step and wrap around if reached the end
      step = (step + 1) % replay.max_steps;
      scrubber.value = step.toString();
      onScrubberChange();

    }, 1000 / playbackSpeed);
  } else {
    playButton.classList.remove('paused');
    if (playbackInterval !== null) {
      window.clearInterval(playbackInterval);
      playbackInterval = null;
    }
  }
}

// Initial resize.
onResize();

// Add event listener to resize the canvas when the window is resized.
window.addEventListener('resize', onResize);
window.addEventListener('keydown', onKeyDown);
window.addEventListener('mousedown', onMouseDown);
window.addEventListener('mouseup', onMouseUp);
window.addEventListener('mousemove', onMouseMove);
window.addEventListener('wheel', onScroll);

scrubber.addEventListener('input', onScrubberChange);
playButton.addEventListener('click', onPlayButtonClick);

window.addEventListener('dragenter', preventDefaults, false);
window.addEventListener('dragleave', preventDefaults, false);
window.addEventListener('dragover', preventDefaults, false);
window.addEventListener('drop', handleDrop, false);

window.addEventListener('load', async () => {

  drawer = new Drawer(globalCanvas);

  // Use local atlas texture.
  const atlasImageUrl = 'dist/atlas.png';
  const atlasJsonUrl = 'dist/atlas.json';

  const success = await drawer.init(atlasJsonUrl, atlasImageUrl);
  if (!success) {
    showModal(
      "error",
      "Initialization failed",
      "Please check the console for more information."
    );
    return;
  } else {
    console.log("Drawer initialized successfully.");
  }

  const replayUrl = getUrlParameter('replayUrl');
  if (replayUrl) {
    console.log("Loading replay from URL: ", replayUrl);
    await fetchReplay(replayUrl);
    focusFullMap(mapPanel);
  } else {
    showModal(
      "info",
      "Welcome to MettaScope",
      "Please drop a replay file here to see the replay."
    );
  }
  onFrame();
});
