import { add, sub, mul, div, almostEqual } from './vector_math.js';

// Get the html elements we will use.
const scrubber = document.getElementById('main-scrubber') as HTMLInputElement;
const selectedGridObjectInfo = document.getElementById('object-info') as HTMLDivElement;

// Get the canvas element.
const globalCanvas = document.getElementById('global-canvas') as HTMLCanvasElement;
const globalCtx = globalCanvas.getContext('2d');
const mapCanvas = document.createElement('canvas');
const mapCtx = mapCanvas.getContext('2d');
const traceCanvas = document.createElement('canvas');
const traceCtx = traceCanvas.getContext('2d');

if (mapCtx !== null && globalCtx !== null) {
    //mapCtx.imageSmoothingEnabled = true;
    globalCtx.imageSmoothingEnabled = true;
}

const imageCache: Map<string, HTMLImageElement> = new Map();
const imageLoaded: Map<string, boolean> = new Map();
const wallMap: Map<string, boolean> = new Map();

// Interaction state.
var mouseDown = false;
var mousePos = new DOMPoint(0, 0);
var lastMousePos = new DOMPoint(0, 0);
var scrollDelta = 0;
var mapZoom = 1;
var mapPos = new DOMPoint(0, 0);
var traceSplit = 100;
var traceDragging = false;
// Replay data and player state.
var replay: any = null;
var step = 0;
var selectedGridObject: any = null;

// Handle resize events.
function onResize() {
    // Adjust for high DPI displays.
    const dpr = window.devicePixelRatio || 1;

    const mapWidth = window.innerWidth;
    const mapHeight = window.innerHeight;
    // Set the canvas size in pixels.
    globalCanvas.width = mapWidth * dpr;
    globalCanvas.height = mapHeight * dpr;

    // Set the display size in CSS pixels.
    globalCanvas.style.width = mapWidth + 'px';
    globalCanvas.style.height = mapHeight + 'px';

    scrubber.style.width = (mapWidth - 64) + 'px';

    // Scale the context to handle high DPI displays.
    globalCtx?.setTransform(dpr, 0, 0, dpr, 0, 0);

    // Redraw the square after resizing.
    onFrame();
}

// Handle trace handle mouse down events.
function onTraceHandleMouseDown() {
    console.log("onTraceHandleMouseDown");
    traceDragging = true;
}

// Handle mouse down events.
function onMouseDown() {
    lastMousePos = mousePos;
    mouseDown = true;
    onFrame();
}

// Handle mouse up events.
function onMouseUp() {
    mouseDown = false;
    traceDragging = false;
    onFrame();
}

// Handle mouse move events.
function onMouseMove(event: MouseEvent) {
    mousePos = new DOMPoint(event.clientX, event.clientY);
    if (traceDragging) {
        console.log("traceDragging");
        traceSplit = window.innerWidth - mousePos.x;
        onResize();
        //onFrame();
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

// Transform a point from the canvas to the map coordinate system.
function transformPoint(ctx: CanvasRenderingContext2D, point: DOMPoint): DOMPoint {
    ctx.save();
    ctx.translate(mapPos.x, mapPos.y);
    ctx.scale(mapZoom, mapZoom);
    const matrix = ctx.getTransform().inverse();
    ctx.restore();
    const transformedPoint = matrix.transformPoint(point);
    return transformedPoint;
}

// Load the replay.
async function loadReplay(replayUrl: string) {
    // HTTP request to get the replay.
    const response = await fetch(replayUrl);
    replay = await response.json();
    console.log("replay: ", replay);
    // Set the scrubber max value to the max steps.
    scrubber.max = replay.max_steps.toString();
}

// Handle scrubber change events.
function onScrubberChange() {
    step = parseInt(scrubber.value);
    console.log("step: ", step);
    onFrame();
}

// Handle key down events.
function onKeyDown(event: KeyboardEvent) {
    if (event.key == "Escape") {
        selectedGridObject = null;
        onFrame();
    }
    // Left and right arrows to scrub forward and backward.
    if (event.key == "ArrowLeft") {
        step = Math.max(step - 1, 0);
        scrubber.value = step.toString();
        onFrame();
    }
    if (event.key == "ArrowRight") {
        step = Math.min(step + 1, replay.max_steps);
        scrubber.value = step.toString();
        onFrame();
    }
}

// Gets an attribute from a grid object respecting the current step.
function getAttr(obj: any, attr: string, atStep = -1): number {
    if (atStep == -1) {
        atStep = step;
    }
    if (obj[attr] === undefined) {
        return 0;
    } else if (obj[attr] instanceof Array) {
        var value: number = 0;
        var i = 0
        while (i < obj[attr].length && obj[attr][i][0] <= atStep) {
            value = obj[attr][i][1];
            i ++;
        }
        return value;
    } else {
        // Must be a constant that does not change over time.
        return obj[attr];
    }
}

// Loads and draws the image at the given position.
function drawImage(
    ctx: CanvasRenderingContext2D,
    imagePath: string,
    x: number,
    y: number
) {
    if (!imageCache.has(imagePath)) {
        const image = new Image();
        image.src = imagePath;
        image.onload = () => {
            imageLoaded.set(imagePath, true);
            onFrame();
        }
        image.onerror = () => {
            console.error("Failed to load image: " + imagePath);
        }
        imageCache.set(imagePath, image);
    }
    const image = imageCache.get(imagePath);
    if (image !== undefined && imageLoaded.get(imagePath)) {
        ctx.drawImage(image, x, y);
    }
}

function drawMap() {
    if (mapCtx === null || replay === null) {
        return;
    }

    // Set map canvas size to match the map dimensions.
    mapCanvas.width = replay.map_size[0] * 64;
    mapCanvas.height = replay.map_size[1] * 64;

    mapCtx.clearRect(0, 0, mapCanvas.width, mapCanvas.height);

    // Draw to map canvas
    mapCtx.save();

    // Draw the floor.
    for (let x = 0; x < replay.map_size[0]; x++) {
        for (let y = 0; y < replay.map_size[1]; y++) {
            drawImage(mapCtx, "data/floor.png", x * 64, y * 64);
        }
    }

    // Construct wall adjacency map.
    for (const gridObject of replay.grid_objects) {
        const type = gridObject.type;
        const typeName = replay.object_types[type];
        if (typeName !== "wall") {
            continue;
        }
        const x = getAttr(gridObject, "c");
        const y = getAttr(gridObject, "r");
        wallMap.set(x + "," + y, true);
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
        if (wallMap.get(x + "," + (y - 1))) {
            n = true;
        }
        if (wallMap.get((x - 1) + "," + y)) {
            w = true;
        }
        if (wallMap.get(x + "," + (y + 1))) {
            s = true;
        }
        if (wallMap.get((x + 1) + "," + y)) {
            e = true;
        }
        if (n || w || e || s) {
            suffix = (n ? "n" : "") + (w ? "w" : "") + (s ? "s" : "") + (e ? "e" : "");
        }
        drawImage(mapCtx, "data/wall." + suffix + ".png", x * 64, y * 64);
    }

    for (const gridObject of replay.grid_objects) {
        const type = gridObject.type;
        const typeName = replay.object_types[type]
        if (typeName === "wall") {
            // Walls are drawn in a different way.
            continue;
        }
        const x = getAttr(gridObject, "c")
        const y = getAttr(gridObject, "r")
        const orientation = getAttr(gridObject, "agent:orientation")
        mapCtx.save();
        mapCtx.translate(x * 64 + 32, y * 64 + 32);
        mapCtx.rotate(-orientation * Math.PI / 2);
        drawImage(mapCtx, "data/" + typeName + ".png", -32, -32);
        mapCtx.restore();
    }

     // Draw rectangle around the selected grid object.
    if (selectedGridObject !== null) {
        const x = getAttr(selectedGridObject, "c")
        const y = getAttr(selectedGridObject, "r")
        mapCtx.strokeStyle = "white";
        mapCtx.strokeRect(x * 64, y * 64, 64, 64);

        // If object has a trajectory, draw it.
        if (selectedGridObject.c.length > 0 || selectedGridObject.r.length > 0) {
            mapCtx.beginPath();
            mapCtx.strokeStyle = "white";
            mapCtx.lineWidth = 2;
            for (let i = 0; i < step; i++) {
                const cx = getAttr(selectedGridObject, "c", i);
                const cy = getAttr(selectedGridObject, "r", i);
                //mapCtx.fillRect(cx * 64 + 32, cy * 64 + 32, 10, 10);
                if (i == 0) {
                    mapCtx.moveTo(cx * 64 + 32, cy * 64 + 32);
                } else {
                    mapCtx.lineTo(cx * 64 + 32, cy * 64 + 32);
                }
            }
            mapCtx.stroke();
        }
    }

    mapCtx.restore();
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

function drawTrace() {
    if (traceCtx === null || replay === null) {
        return;
    }


    traceCanvas.width = replay.max_steps * 4 + 64;
    traceCanvas.height = replay.num_agents * 64 + 100;

    traceCtx.clearRect(0, 0, traceCanvas.width, traceCanvas.height);

    // Draw trace canvas to global canvas with proper scaling
    traceCtx.fillStyle = "rgba(20, 20, 20, 1)";
    traceCtx.fillRect(0, 0, traceCanvas.width, traceCanvas.height);

    for (let i = 0; i < replay.num_agents; i++) {
        // Draw the agents id:
        traceCtx.fillStyle = "white";
        traceCtx.font = "16px Arial";
        traceCtx.fillText(i.toString(), 10, 20 + i * 64);

        // Draw the agent's actions:
        for (let j = 0; j < replay.agent_actions[i].length; j++) {
            const action_success = replay.agent_action_success[i][j];
            if (action_success) {
                const action = replay.agent_actions[i][j] as number[];
                const actionName = replay.action_names[action[1]] as string;
                const color = ACTION_COLORS[actionName as keyof typeof ACTION_COLORS];
                const importance = ACTION_IMPORTANCE[actionName as keyof typeof ACTION_IMPORTANCE];
                traceCtx.fillStyle = color;
                traceCtx.fillRect(32 + j * 4, 20 + i * 64 - 2 * importance, 2, 4 * importance);
            } else {
                traceCtx.fillStyle = "rgba(30, 30, 30, 1)";
                traceCtx.fillRect(32 + j * 4, 20 + i * 64 - 2, 2, 4);
            }

        }
    }

}

// Draw a frame.
function onFrame() {
    if (mapCtx === null || globalCtx === null || replay === null || traceCtx === null) {
        return;
    }

    console.log("onFrame");

    if (mouseDown) {
        mapPos = add(mapPos, sub(mousePos, lastMousePos));
        lastMousePos = mousePos;

        const mapMousePos = transformPoint(mapCtx, mousePos);
        const gridMousePos = new DOMPoint(
            Math.floor(mapMousePos.x / 64),
            Math.floor(mapMousePos.y / 64)
        );
        const gridObject = replay.grid_objects.find((obj: any) => {
            const x = getAttr(obj, "c");
            const y = getAttr(obj, "r");
            return x === gridMousePos.x && y === gridMousePos.y;
        });
        if (gridObject !== undefined) {
            selectedGridObject = gridObject;
            console.log("selectedGridObject: ", selectedGridObject);
        }
    }
    if (scrollDelta !== 0) {
        const oldMousePoint = transformPoint(mapCtx, mousePos);
        mapZoom = mapZoom + scrollDelta / 1000;
        mapZoom = Math.max(Math.min(mapZoom, 2), 0.1);
        const newMousePoint = transformPoint(mapCtx, mousePos);
        mapPos = add(mapPos, mul(sub(newMousePoint, oldMousePoint), mapZoom));
    }

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
    }
    selectedGridObjectInfo.innerHTML = readout;

    // Clear both canvases.
    globalCtx.clearRect(0, 0, globalCanvas.width, globalCanvas.height);

    drawMap();
    drawTrace();

    globalCtx.save();
    globalCtx.translate(mapPos.x, mapPos.y);
    globalCtx.scale(mapZoom, mapZoom);

    // Draw map canvas to global canvas to prevent aliasing artifacts.
    globalCtx.drawImage(mapCanvas, 0, 0);
    globalCtx.drawImage(traceCanvas, mapCanvas.width + 100, 0);
    globalCtx.restore();
}

// Initial resize.
onResize();

// Add event listener to resize the canvas when the window is resized.
window.addEventListener('resize', onResize);
window.addEventListener('keydown', onKeyDown);
globalCanvas.addEventListener('mousedown', onMouseDown);
globalCanvas.addEventListener('mouseup', onMouseUp);
globalCanvas.addEventListener('mousemove', onMouseMove);
globalCanvas.addEventListener('wheel', onScroll);

scrubber.addEventListener('input', onScrubberChange);

window.addEventListener('load', async () => {
    await loadReplay("replay.json");
    onFrame();
});
