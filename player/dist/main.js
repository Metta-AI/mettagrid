var __awaiter = (this && this.__awaiter) || function (thisArg, _arguments, P, generator) {
    function adopt(value) { return value instanceof P ? value : new P(function (resolve) { resolve(value); }); }
    return new (P || (P = Promise))(function (resolve, reject) {
        function fulfilled(value) { try { step(generator.next(value)); } catch (e) { reject(e); } }
        function rejected(value) { try { step(generator["throw"](value)); } catch (e) { reject(e); } }
        function step(result) { result.done ? resolve(result.value) : adopt(result.value).then(fulfilled, rejected); }
        step((generator = generator.apply(thisArg, _arguments || [])).next());
    });
};
import { add, sub, mul, length } from './vector_math.js';
import { Grid } from './grid.js';
export class PanelInfo {
    constructor(name) {
        this.x = 0;
        this.y = 0;
        this.width = 0;
        this.height = 0;
        this.name = "";
        this.panPos = new DOMPoint(0, 0);
        this.zoomLevel = 1;
        this.name = name;
        this.canvas = document.createElement('canvas');
        this.canvas.setAttribute('id', name + '-canvas');
        this.ctx = this.canvas.getContext('2d');
        this.div = null;
    }
    // Check if a point is inside the panel.
    inside(point) {
        return point.x >= this.x && point.x < this.x + this.width &&
            point.y >= this.y && point.y < this.y + this.height;
    }
    // Draw the panel to the global canvas.
    drawPanel(globalCtx) {
        globalCtx.save();
        globalCtx.beginPath();
        globalCtx.rect(this.x, this.y, this.width, this.height);
        globalCtx.clip();
        globalCtx.translate(this.panPos.x, this.panPos.y);
        globalCtx.scale(this.zoomLevel, this.zoomLevel);
        // Draw map canvas to global canvas
        globalCtx.drawImage(this.canvas, this.x, this.y);
        globalCtx.restore();
    }
    // Transform a point from the canvas to the map coordinate system.
    transformPoint(point) {
        if (this.ctx === null) {
            return null;
        }
        if (!this.inside(point)) {
            return null;
        }
        this.ctx.save();
        this.ctx.translate(this.panPos.x, this.panPos.y);
        this.ctx.scale(this.zoomLevel, this.zoomLevel);
        this.ctx.translate(this.x, this.y);
        const matrix = this.ctx.getTransform().inverse();
        this.ctx.restore();
        return matrix.transformPoint(point);
    }
    // Update the pan and zoom level based on the mouse position and scroll delta.
    updatePanAndZoom() {
        if (mouseDown && length(sub(mousePos, lastMousePos)) > 1) {
            this.panPos = add(this.panPos, sub(mousePos, lastMousePos));
            lastMousePos = mousePos;
            return true;
        }
        if (scrollDelta !== 0) {
            const oldMousePoint = this.transformPoint(mousePos);
            this.zoomLevel = this.zoomLevel + scrollDelta / 1000;
            this.zoomLevel = Math.max(Math.min(this.zoomLevel, 2), 0.1);
            const newMousePoint = this.transformPoint(mousePos);
            if (oldMousePoint != null && newMousePoint != null) {
                this.panPos = add(this.panPos, mul(sub(newMousePoint, oldMousePoint), this.zoomLevel));
            }
            return true;
        }
        return false;
    }
}
// Get the html elements we will use.
const scrubber = document.getElementById('main-scrubber');
// Get the canvas element.
const globalCanvas = document.getElementById('global-canvas');
const globalCtx = globalCanvas.getContext('2d');
const mapPanel = new PanelInfo("map");
const tracePanel = new PanelInfo("trace");
const infoPanel = new PanelInfo("info");
if (mapPanel.ctx !== null && globalCtx !== null && tracePanel.ctx !== null) {
    mapPanel.ctx.imageSmoothingEnabled = true;
    globalCtx.imageSmoothingEnabled = true;
    tracePanel.ctx.imageSmoothingEnabled = true;
}
const imageCache = new Map();
const imageLoaded = new Map();
// Interaction state.
let mouseDown = false;
let mousePos = new DOMPoint(0, 0);
let lastMousePos = new DOMPoint(0, 0);
let scrollDelta = 0;
// var mapZoom = 1;
// var mapPos = new DOMPoint(0, 0);
let traceSplit = 0.50;
let traceDragging = false;
let infoSplit = 0.25;
let infoDragging = false;
// Replay data and player state.
let replay = null;
let step = 0;
let selectedGridObject = null;
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
    globalCtx === null || globalCtx === void 0 ? void 0 : globalCtx.setTransform(dpr, 0, 0, dpr, 0, 0);
    mapPanel.x = 0;
    mapPanel.y = 0;
    mapPanel.width = mapWidth * traceSplit;
    mapPanel.height = mapHeight - 60;
    tracePanel.x = mapWidth * traceSplit;
    tracePanel.y = mapHeight * infoSplit - 60;
    tracePanel.width = mapWidth * (1 - traceSplit);
    tracePanel.height = mapHeight * (1 - infoSplit);
    infoPanel.x = mapWidth * traceSplit;
    infoPanel.y = 0;
    infoPanel.width = mapWidth * (1 - traceSplit);
    infoPanel.height = mapHeight * infoSplit;
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
    if (Math.abs(mousePos.x - mapPanel.width) < 10) {
        traceDragging = true;
        console.log("Started trace dragging");
    }
    else if (mousePos.x > mapPanel.width && Math.abs(mousePos.y - infoPanel.height) < 10) {
        infoDragging = true;
        console.log("Started info dragging");
    }
    else {
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
function onMouseMove(event) {
    mousePos = new DOMPoint(event.clientX, event.clientY);
    // If mouse is close to a panels edge change cursor to edge changer.
    document.body.style.cursor = "default";
    if (Math.abs(mousePos.x - mapPanel.width) < 10) {
        document.body.style.cursor = "ew-resize";
    }
    if (mousePos.x > mapPanel.width && Math.abs(mousePos.y - infoPanel.height) < 10) {
        document.body.style.cursor = "ns-resize";
    }
    if (traceDragging) {
        console.log("traceDragging...");
        traceSplit = mousePos.x / window.innerWidth;
        onResize();
    }
    else if (infoDragging) {
        console.log("infoDragging...");
        infoSplit = mousePos.y / window.innerHeight;
        onResize();
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
// Expand a sequence of values
// [[0, value1], [2, value2], ...] -> [value1, value1, value2, ...]
function expandSequence(sequence, numSteps) {
    var expanded = [];
    var i = 0;
    var j = 0;
    var v = null;
    for (i = 0; i < numSteps; i++) {
        if (j < sequence.length && sequence[j][0] == i) {
            v = sequence[j][1];
            j++;
        }
        expanded.push(v);
    }
    return expanded;
}
// Load the replay.
function loadReplay(replayUrl) {
    return __awaiter(this, void 0, void 0, function* () {
        // HTTP request to get the replay.
        const response = yield fetch(replayUrl);
        replay = yield response.json();
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
        // When step is not defined, use global step.
        atStep = step;
    }
    if (obj[attr] === undefined) {
        return 0;
    }
    else if (obj[attr] instanceof Array) {
        //return findInSeries(obj[attr], atStep);
        return obj[attr][atStep];
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
const AGENT_STYLES = {
    "body": 4,
    "eyes": 4,
    "horns": 4,
    "hair": 4,
    "mouth": 4,
};
function getAgentStyle(agentId) {
    const n = 4; // number of variations per trait
    return {
        bodyId: Math.floor(agentId * Math.PI) % AGENT_STYLES.body,
        eyesId: Math.floor(agentId * Math.E) % AGENT_STYLES.eyes,
        hornsId: Math.floor(agentId * Math.SQRT2) % AGENT_STYLES.horns,
        hairId: Math.floor(agentId * 2.236) % AGENT_STYLES.hair, // sqrt(5)
        mouthId: Math.floor(agentId * 2.645) % AGENT_STYLES.mouth // sqrt(7)
    };
}
// Make the panel focus on the full map, used at the start of the replay.
function focusFullMap(panel) {
    const mapWidth = replay.map_size[0] * 64;
    const mapHeight = replay.map_size[1] * 64;
    const panelWidth = panel.width;
    const panelHeight = panel.height;
    const zoomLevel = Math.min(panelWidth / mapWidth, panelHeight / mapHeight);
    panel.panPos = new DOMPoint((panelWidth - mapWidth * zoomLevel) / 2, (panelHeight - mapHeight * zoomLevel) / 2);
    panel.zoomLevel = zoomLevel;
}
function focusMapOn(panel, x, y) {
    panel.panPos = new DOMPoint(-x * 64 + panel.width / 2, -y * 64 + panel.height / 2);
    panel.zoomLevel = 1;
}
function drawMap(panel) {
    if (panel.ctx === null || replay === null) {
        return;
    }
    if (mouseDown) {
        const localMousePos = panel.transformPoint(mousePos);
        if (localMousePos != null) {
            const gridMousePos = new DOMPoint(Math.floor(localMousePos.x / 64), Math.floor(localMousePos.y / 64));
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
    }
    // Set map canvas size to match the map dimensions.
    panel.canvas.width = replay.map_size[0] * 64;
    panel.canvas.height = replay.map_size[1] * 64;
    panel.ctx.clearRect(0, 0, panel.canvas.width, panel.canvas.height);
    // Draw to map canvas
    panel.ctx.save();
    // Draw the floor.
    for (let x = 0; x < replay.map_size[0]; x++) {
        for (let y = 0; y < replay.map_size[1]; y++) {
            drawImage(panel.ctx, "data/floor.png", x * 64, y * 64);
        }
    }
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
        drawImage(panel.ctx, "data/wall." + suffix + ".png", x * 64, y * 64);
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
            drawImage(panel.ctx, "data/wall.fill.png", x * 64 + 32, y * 64 + 32);
        }
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
        if (gridObject["agent_id"] !== undefined) {
            const orientation = getAttr(gridObject, "agent:orientation");
            var suffix = "";
            if (orientation == 0) {
                suffix = ".n";
            }
            else if (orientation == 1) {
                suffix = ".s";
            }
            else if (orientation == 2) {
                suffix = ".w";
            }
            else if (orientation == 3) {
                suffix = ".e";
            }
            const agent_id = gridObject["agent_id"];
            const style = getAgentStyle(agent_id);
            drawImage(panel.ctx, "data/" + typeName + suffix + ".body." + style.bodyId + ".png", x * 64, y * 64);
            drawImage(panel.ctx, "data/" + typeName + suffix + ".hair." + style.hairId + ".png", x * 64, y * 64);
            drawImage(panel.ctx, "data/" + typeName + suffix + ".mouth." + style.mouthId + ".png", x * 64, y * 64);
            drawImage(panel.ctx, "data/" + typeName + suffix + ".horns." + style.hornsId + ".png", x * 64, y * 64);
            drawImage(panel.ctx, "data/" + typeName + suffix + ".eyes." + style.eyesId + ".png", x * 64, y * 64);
        }
        else {
            drawImage(panel.ctx, "data/" + typeName + ".png", x * 64, y * 64);
        }
    }
    // Draw rectangle around the selected grid object.
    if (selectedGridObject !== null) {
        const x = getAttr(selectedGridObject, "c");
        const y = getAttr(selectedGridObject, "r");
        panel.ctx.strokeStyle = "white";
        panel.ctx.strokeRect(x * 64, y * 64, 64, 64);
        // If object has a trajectory, draw it.
        if (selectedGridObject.c.length > 0 || selectedGridObject.r.length > 0) {
            panel.ctx.beginPath();
            panel.ctx.strokeStyle = "white";
            panel.ctx.lineWidth = 2;
            for (let i = 0; i < step; i++) {
                const cx = getAttr(selectedGridObject, "c", i);
                const cy = getAttr(selectedGridObject, "r", i);
                if (i == 0) {
                    panel.ctx.moveTo(cx * 64 + 32, cy * 64 + 32);
                }
                else {
                    panel.ctx.lineTo(cx * 64 + 32, cy * 64 + 32);
                }
            }
            panel.ctx.stroke();
            // // Draw foot prints.
            // for (let i = 0; i < step; i++) {
            //     const x = getAttr(selectedGridObject, "c", i);
            //     const y = getAttr(selectedGridObject, "r", i);
            //     const orientation = getAttr(selectedGridObject, "agent:orientation", i);
            //     panel.ctx.save()
            //     panel.ctx.translate(x * 64 + 32, y * 64 + 32);
            //     panel.ctx.scale(0.25, 0.25);
            //     var angle = 0
            //     if (orientation == 0) {
            //         angle = 0;
            //     } else if (orientation == 1) {
            //         angle = Math.PI / 2;
            //     } else if (orientation == 2) {
            //         angle = -Math.PI;
            //     } else if (orientation == 3) {
            //         angle = -3 * Math.PI / 2;
            //     }
            //     panel.ctx.rotate(angle);
            //     drawImage(panel.ctx, "data/footprint.png", -32, -32);
            //     panel.ctx.restore()
            // }
        }
    }
    panel.ctx.restore();
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
};
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
};
function drawTrace(panel) {
    if (panel.ctx === null || replay === null || mapPanel.ctx === null) {
        return;
    }
    const localMousePos = panel.transformPoint(mousePos);
    if (localMousePos != null) {
        if (mouseDown) {
            const mapX = localMousePos.x - 32;
            if (mapX > 0 && mapX < replay.max_steps * 4 &&
                localMousePos.y > 0 && localMousePos.y < replay.num_agents * 64) {
                const agentId = Math.floor(localMousePos.y / 64);
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
    panel.canvas.width = replay.max_steps * 4 + 64;
    panel.canvas.height = replay.num_agents * 64 + 100;
    panel.ctx.clearRect(0, 0, panel.canvas.width, panel.canvas.height);
    // Draw trace canvas to global canvas with proper scaling
    panel.ctx.fillStyle = "rgba(20, 20, 20, 1)";
    panel.ctx.fillRect(0, 0, panel.canvas.width, panel.canvas.height);
    // Draw current step line that goes through all of the traces:
    panel.ctx.fillStyle = "rgba(255, 255, 255, 0.5)";
    panel.ctx.fillRect(32 + step * 4, 0, 2, panel.canvas.height);
    panel.ctx.fillStyle = "white";
    for (let i = 0; i < replay.num_agents; i++) {
        // Draw the agents id:
        panel.ctx.fillStyle = "white";
        panel.ctx.font = "16px Arial";
        panel.ctx.fillText(i.toString(), 10, 45 + i * 64);
        // Draw the agent's actions:
        for (const gridObject of replay.grid_objects) {
            if (gridObject["agent_id"] == i) {
                for (let j = 0; j < replay.max_steps; j++) {
                    const action = getAttr(gridObject, "action", j);
                    const action_success = getAttr(gridObject, "action_success", j);
                    if (action_success) {
                        const actionName = replay.action_names[action[0]];
                        const color = ACTION_COLORS[actionName];
                        const importance = ACTION_IMPORTANCE[actionName];
                        panel.ctx.fillStyle = color;
                        panel.ctx.fillRect(32 + j * 4, 40 + i * 64 - 2 * importance, 2, 4 * importance);
                    }
                    else {
                        panel.ctx.fillStyle = "rgba(30, 30, 30, 1)";
                        panel.ctx.fillRect(32 + j * 4, 40 + i * 64 - 2, 2, 4);
                    }
                    const reward = getAttr(gridObject, "reward", j);
                    const total_reward = getAttr(gridObject, "total_reward", j);
                    // If there is reward draw a sharp bar.
                    if (reward > 0) {
                        const importance = 10;
                        panel.ctx.fillStyle = "hsl(46, 100.00%, 76.70%)";
                        panel.ctx.fillRect(32 + j * 4, 40 + i * 64 - 2 * importance, 2, 4 * importance);
                    }
                }
            }
        }
    }
    // Draw rectangle around the selected agent.
    if (selectedGridObject !== null && selectedGridObject.agent_id !== undefined) {
        const agentId = selectedGridObject.agent_id;
        panel.ctx.strokeStyle = "white";
        panel.ctx.strokeRect(0, 40 + agentId * 64 - 32, tracePanel.canvas.width - 1, 64);
        // Draw the action name above the selected action trace bar.
        const action = getAttr(selectedGridObject, "action", step);
        if (action != null) {
            const actionName = replay.action_names[action[0]];
            panel.ctx.fillStyle = "white";
            panel.ctx.font = "16px Arial";
            panel.ctx.fillText(actionName + " " + action[1], 32 + step * 4, 20 + agentId * 64);
        }
    }
}
// Updates the readout of the selected object or replay info.
function updateReadout() {
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
        var objectTypeCounts = new Map();
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
    if (globalCtx === null || replay === null || mapPanel.ctx === null || tracePanel.ctx === null) {
        return;
    }
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
    if (fullUpdate) {
        updateReadout();
        drawMap(mapPanel);
        drawTrace(tracePanel);
    }
    // Clear both canvases.
    globalCtx.clearRect(0, 0, globalCanvas.width, globalCanvas.height);
    mapPanel.drawPanel(globalCtx);
    tracePanel.drawPanel(globalCtx);
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
window.addEventListener('load', () => __awaiter(void 0, void 0, void 0, function* () {
    yield loadReplay("replay.json");
    focusFullMap(mapPanel);
    onFrame();
}));
//# sourceMappingURL=main.js.map