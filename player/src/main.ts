
import { add, sub, mul, div, almostEqual } from './vector_math.js';

// Get the canvas element.
const canvas = document.getElementById('myCanvas') as HTMLCanvasElement;
const ctx = canvas.getContext('2d');
if (ctx !== null) {
    ctx.imageSmoothingEnabled = true;
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


// Replay data and player state.
var replay: any = null;
var step = 0;

// Handle resize events.
function onResize() {
    // Adjust for high DPI displays
    const dpr = window.devicePixelRatio || 1;
    canvas.width = window.innerWidth * dpr;
    canvas.height = window.innerHeight * dpr;
    ctx?.scale(dpr, dpr);

    // Redraw the square after resizing.
    onFrame();
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
    onFrame();
}

// Handle mouse move events.
function onMouseMove(event: MouseEvent) {
    mousePos = new DOMPoint(event.clientX, event.clientY);
    onFrame();
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
}

// Handle scrubber change events.
function onScrubberChange() {
    const scrubber = document.getElementById('main-scrubber') as HTMLInputElement;
    step = parseInt(scrubber.value);
    console.log("step: ", step);
    onFrame();
}

// Gets an attribute from a grid object respecting the current step.
function getAttr(obj: any, attr: string): number {
    if (obj[attr] === undefined) {
        return 0;
    } else if (obj[attr] instanceof Array) {
        var value: number = 0;
        var i = 0
        while (i < obj[attr].length && obj[attr][i][0] <= step) {
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

// Draw a frame.
function onFrame() {
    if (ctx === null) {
        return;
    }

    if (mouseDown) {
        mapPos = add(mapPos, sub(mousePos, lastMousePos));
        lastMousePos = mousePos;
    }
    if (scrollDelta !== 0) {
        const oldMousePoint = transformPoint(ctx, mousePos);
        mapZoom = mapZoom + scrollDelta / 1000;
        mapZoom = Math.max(Math.min(mapZoom, 2), 0.1);
        const newMousePoint = transformPoint(ctx, mousePos);
        mapPos = add(mapPos, mul(sub(newMousePoint, oldMousePoint), mapZoom));
    }

    // Clear the canvas.
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    const mapMousePos = transformPoint(ctx, mousePos);

    ctx.save();

    ctx.translate(mapPos.x, mapPos.y);
    ctx.scale(mapZoom, mapZoom);

    // Draw all of the grid objects.
    if (replay !== null) {

        // Draw the floor.
        for (let x = 0; x < replay.map_size[0]; x++) {
            for (let y = 0; y < replay.map_size[1]; y++) {
                drawImage(ctx, "data/floor.png", x * 64, y * 64);
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
            drawImage(ctx, "data/wall." + suffix + ".png", x * 64, y * 64);
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
            ctx.save();
            ctx.translate(x * 64 + 32, y * 64 + 32);
            ctx.rotate(-orientation * Math.PI / 2);
            drawImage(ctx, "data/" + typeName + ".png", -32, -32);
            ctx.restore();
        }
    }

    ctx.restore();
}

// Initial resize.
onResize();

// Add event listener to resize the canvas when the window is resized.
window.addEventListener('resize', onResize);
canvas.addEventListener('mousedown', onMouseDown);
canvas.addEventListener('mouseup', onMouseUp);
canvas.addEventListener('mousemove', onMouseMove);
canvas.addEventListener('wheel', onScroll);

const scrubber = document.getElementById('main-scrubber') as HTMLInputElement;
scrubber.addEventListener('input', onScrubberChange);

window.addEventListener('load', async () => {
    await loadReplay("replay.json");
});
