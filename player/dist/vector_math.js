// Add an add method to DOMPoint.
function add(a, b) {
    return new DOMPoint(a.x + b.x, a.y + b.y, a.z + b.z, a.w + b.w);
}
;
// Add a sub method to DOMPoint.
function sub(a, b) {
    return new DOMPoint(a.x - b.x, a.y - b.y, a.z - b.z, a.w - b.w);
}
;
// Add a mul method to DOMPoint.
function mul(a, b) {
    return new DOMPoint(a.x * b, a.y * b, a.z * b, a.w * b);
}
;
// Add a div method to DOMPoint.
function div(a, b) {
    return new DOMPoint(a.x / b, a.y / b, a.z / b, a.w / b);
}
;
// Check if two numbers are almost equal. Very useful for testing.
function almostEqual(a, b) {
    return Math.abs(a - b) < 1e-3;
}
function length(a) {
    return Math.sqrt(a.x * a.x + a.y * a.y + a.z * a.z + a.w * a.w);
}
export { add, sub, mul, div, almostEqual, length };
//# sourceMappingURL=vector_math.js.map