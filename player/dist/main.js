var __awaiter = (this && this.__awaiter) || function (thisArg, _arguments, P, generator) {
    function adopt(value) { return value instanceof P ? value : new P(function (resolve) { resolve(value); }); }
    return new (P || (P = Promise))(function (resolve, reject) {
        function fulfilled(value) { try { step(generator.next(value)); } catch (e) { reject(e); } }
        function rejected(value) { try { step(generator["throw"](value)); } catch (e) { reject(e); } }
        function step(result) { result.done ? resolve(result.value) : adopt(result.value).then(fulfilled, rejected); }
        step((generator = generator.apply(thisArg, _arguments || [])).next());
    });
};
import { add, sub, mul } from './vector_math.js';
// Get the html elements we will use.
const scrubber = document.getElementById('main-scrubber');
const selectedGridObjectInfo = document.getElementById('object-info');
// Get the canvas element.
const mapCanvas = document.getElementById('map-canvas');
const mapCtx = mapCanvas.getContext('2d');
const innerMapCanvas = document.createElement('canvas');
const ctx = innerMapCanvas.getContext('2d');
const traceCanvas = document.getElementById('trace-canvas');
const traceCtx = traceCanvas.getContext('2d');
const traceHandle = document.getElementById('trace-handle');
if (ctx !== null && mapCtx !== null) {
    //ctx.imageSmoothingEnabled = true;
    mapCtx.imageSmoothingEnabled = true;
}
const imageCache = new Map();
const imageLoaded = new Map();
const wallMap = new Map();
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
var replay = null;
var step = 0;
var selectedGridObject = null;
// Handle resize events.
function onResize() {
    // Adjust for high DPI displays.
    const dpr = window.devicePixelRatio || 1;
    const mapWidth = window.innerWidth - traceSplit;
    const mapHeight = window.innerHeight;
    // Set the canvas size in pixels.
    mapCanvas.width = mapWidth * dpr;
    mapCanvas.height = mapHeight * dpr;
    // Set the display size in CSS pixels.
    mapCanvas.style.width = mapWidth + 'px';
    mapCanvas.style.height = mapHeight + 'px';
    scrubber.style.width = (mapWidth - 64) + 'px';
    // Scale the context to handle high DPI displays.
    mapCtx === null || mapCtx === void 0 ? void 0 : mapCtx.setTransform(dpr, 0, 0, dpr, 0, 0);
    // Set the trace canvas size in pixels.
    traceCanvas.width = (traceSplit - 10) * dpr;
    traceCanvas.height = mapHeight * dpr;
    // Set the display size in CSS pixels.
    traceCanvas.style.right = '0px';
    traceCanvas.style.top = '0px';
    traceCanvas.style.width = (traceSplit - 10) + 'px';
    traceCanvas.style.height = mapHeight + 'px';
    traceHandle.style.right = (traceSplit - 10) + 'px';
    traceHandle.style.top = '0px';
    traceHandle.style.width = '10px';
    traceHandle.style.height = mapHeight + 'px';
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
function onMouseMove(event) {
    mousePos = new DOMPoint(event.clientX, event.clientY);
    if (traceDragging) {
        console.log("traceDragging");
        traceSplit = window.innerWidth - mousePos.x;
        onResize();
        //onFrame();
    }
    else if (mouseDown) {
        onFrame();
    }
}
// Handle scroll events.
function onScroll(event) {
    scrollDelta = event.deltaY;
    onFrame();
    scrollDelta = 0;
}
// Transform a point from the canvas to the map coordinate system.
function transformPoint(ctx, point) {
    ctx.save();
    ctx.translate(mapPos.x, mapPos.y);
    ctx.scale(mapZoom, mapZoom);
    const matrix = ctx.getTransform().inverse();
    ctx.restore();
    const transformedPoint = matrix.transformPoint(point);
    return transformedPoint;
}
// Load the replay.
function loadReplay(replayUrl) {
    return __awaiter(this, void 0, void 0, function* () {
        // HTTP request to get the replay.
        const response = yield fetch(replayUrl);
        replay = yield response.json();
        console.log("replay: ", replay);
        // Set the scrubber max value to the max steps.
        scrubber.max = replay.max_steps.toString();
    });
}
// Handle scrubber change events.
function onScrubberChange() {
    step = parseInt(scrubber.value);
    console.log("step: ", step);
    onFrame();
}
// Handle key down events.
function onKeyDown(event) {
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
function getAttr(obj, attr, atStep = -1) {
    if (atStep == -1) {
        atStep = step;
    }
    if (obj[attr] === undefined) {
        return 0;
    }
    else if (obj[attr] instanceof Array) {
        var value = 0;
        var i = 0;
        while (i < obj[attr].length && obj[attr][i][0] <= atStep) {
            value = obj[attr][i][1];
            i++;
        }
        return value;
    }
    else {
        // Must be a constant that does not change over time.
        return obj[attr];
    }
}
// Loads and draws the image at the given position.
function drawImage(ctx, imagePath, x, y) {
    if (!imageCache.has(imagePath)) {
        const image = new Image();
        image.src = imagePath;
        image.onload = () => {
            imageLoaded.set(imagePath, true);
            onFrame();
        };
        image.onerror = () => {
            console.error("Failed to load image: " + imagePath);
        };
        imageCache.set(imagePath, image);
    }
    const image = imageCache.get(imagePath);
    if (image !== undefined && imageLoaded.get(imagePath)) {
        ctx.drawImage(image, x, y);
    }
}
// Draw a frame.
function onFrame() {
    if (ctx === null || mapCtx === null || replay === null || traceCtx === null) {
        return;
    }
    console.log("onFrame");
    if (mouseDown) {
        mapPos = add(mapPos, sub(mousePos, lastMousePos));
        lastMousePos = mousePos;
        const mapMousePos = transformPoint(ctx, mousePos);
        const gridMousePos = new DOMPoint(Math.floor(mapMousePos.x / 64), Math.floor(mapMousePos.y / 64));
        const gridObject = replay.grid_objects.find((obj) => {
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
        const oldMousePoint = transformPoint(ctx, mousePos);
        mapZoom = mapZoom + scrollDelta / 1000;
        mapZoom = Math.max(Math.min(mapZoom, 2), 0.1);
        const newMousePoint = transformPoint(ctx, mousePos);
        mapPos = add(mapPos, mul(sub(newMousePoint, oldMousePoint), mapZoom));
    }
    var readout = "";
    if (selectedGridObject !== null) {
        for (const key in selectedGridObject) {
            var value = getAttr(selectedGridObject, key);
            if (key == "type") {
                value = replay.object_types[value];
            }
            readout += key + ": " + value + "\n";
        }
    }
    else {
        readout += "Step: " + step + "\n";
        readout += "Map size: " + replay.map_size[0] + "x" + replay.map_size[1] + "\n";
        readout += "Num agents: " + replay.num_agents + "\n";
        readout += "Max steps: " + replay.max_steps + "\n";
    }
    selectedGridObjectInfo.innerHTML = readout;
    // Set map canvas size to match the map dimensions.
    innerMapCanvas.width = replay.map_size[0] * 64;
    innerMapCanvas.height = replay.map_size[1] * 64;
    // Clear both canvases.
    ctx.clearRect(0, 0, innerMapCanvas.width, innerMapCanvas.height);
    mapCtx.clearRect(0, 0, mapCanvas.width, mapCanvas.height);
    traceCtx.clearRect(0, 0, traceCanvas.width, traceCanvas.height);
    // Fill trace canvas with green.
    traceCtx.fillStyle = "green";
    traceCtx.fillRect(0, 0, traceCanvas.width, traceCanvas.height);
    const mapMousePos = transformPoint(ctx, mousePos);
    // Draw to map canvas
    ctx.save();
    //ctx.translate(mapPos.x, mapPos.y);
    //ctx.scale(mapZoom, mapZoom);
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
        const typeName = replay.object_types[type];
        if (typeName === "wall") {
            // Walls are drawn in a different way.
            continue;
        }
        const x = getAttr(gridObject, "c");
        const y = getAttr(gridObject, "r");
        const orientation = getAttr(gridObject, "agent:orientation");
        ctx.save();
        ctx.translate(x * 64 + 32, y * 64 + 32);
        ctx.rotate(-orientation * Math.PI / 2);
        drawImage(ctx, "data/" + typeName + ".png", -32, -32);
        ctx.restore();
    }
    // Draw rectangle around the selected grid object.
    if (selectedGridObject !== null) {
        const x = getAttr(selectedGridObject, "c");
        const y = getAttr(selectedGridObject, "r");
        ctx.strokeStyle = "white";
        ctx.strokeRect(x * 64, y * 64, 64, 64);
        // If object has a trajectory, draw it.
        if (selectedGridObject.c.length > 0 || selectedGridObject.r.length > 0) {
            ctx.beginPath();
            ctx.strokeStyle = "white";
            ctx.lineWidth = 2;
            for (let i = 0; i < step; i++) {
                const cx = getAttr(selectedGridObject, "c", i);
                const cy = getAttr(selectedGridObject, "r", i);
                //ctx.fillRect(cx * 64 + 32, cy * 64 + 32, 10, 10);
                if (i == 0) {
                    ctx.moveTo(cx * 64 + 32, cy * 64 + 32);
                }
                else {
                    ctx.lineTo(cx * 64 + 32, cy * 64 + 32);
                }
            }
            ctx.stroke();
        }
    }
    ctx.restore();
    // Draw map canvas to global canvas with proper scaling
    mapCtx.save();
    mapCtx.setTransform(mapZoom, 0, 0, mapZoom, mapPos.x, mapPos.y);
    mapCtx.drawImage(innerMapCanvas, 0, 0);
    mapCtx.restore();
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
traceHandle.addEventListener('mousedown', onTraceHandleMouseDown);
window.addEventListener('load', () => __awaiter(void 0, void 0, void 0, function* () {
    yield loadReplay("replay.json");
    onFrame();
}));
//# sourceMappingURL=main.js.map