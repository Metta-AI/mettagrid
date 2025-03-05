// test_vector2d.ts
import { Vector2D, Matrix2D, almostEqual } from './vector_math.js';
// Assert that a condition is true and throw an error if it is not, with an
// optional message.
function assert(condition, message = "Assertion failed") {
    if (!condition) {
        throw new Error(message);
    }
}
// Test the Vector2D class.
const v1 = new Vector2D(1, 2);
const v2 = new Vector2D(3, 4);
assert(v1.add(v2).x === 4);
assert(v1.add(v2).y === 6);
assert(v1.subtract(v2).x === -2);
assert(v1.subtract(v2).y === -2);
assert(v1.multiply(2).x === 2);
assert(v1.multiply(2).y === 4);
assert(v1.divide(2).x === 0.5);
assert(v1.divide(2).y === 1);
assert(v1.length() === Math.sqrt(1 * 1 + 2 * 2));
assert(almostEqual(v1.length(), 2.23606797749979));
assert(almostEqual(v1.normalize().length(), 1));
assert(v1.toString() === "|1.000 2.000|");
// Test the Matrix2D class.
const m1 = new Matrix2D(1, 2, 3, 4, 5, 6);
const m2 = new Matrix2D(7, 8, 9, 10, 11, 12);
const c1 = m1.multiply(m2);
assert(c1.a === 25);
assert(c1.b === 28);
assert(c1.c === 57);
assert(c1.d === 64);
assert(c1.x === 100);
assert(c1.y === 112);
assert(c1.toString() === "|25.000 28.000 0|\n|57.000 64.000 0|\n|100.000 112.000 1|");
const m3 = Matrix2D.translation(1, 2);
assert(m3.x === 1);
assert(m3.y === 2);
const m4 = Matrix2D.rotation(Math.PI / 2);
assert(m4.toString() === "|0.000 1.000 0|\n|-1.000 0.000 0|\n|0.000 0.000 1|");
assert(almostEqual(m4.a, 0));
assert(almostEqual(m4.b, 1));
assert(almostEqual(m4.c, -1));
assert(almostEqual(m4.d, 0));
assert(almostEqual(m4.x, 0));
assert(almostEqual(m4.y, 0));
const m5 = Matrix2D.scaling(2, 3);
assert(almostEqual(m5.a, 2));
assert(almostEqual(m5.b, 0));
assert(almostEqual(m5.c, 0));
assert(almostEqual(m5.d, 3));
assert(almostEqual(m5.x, 0));
assert(almostEqual(m5.y, 0));
const point = { x: 1, y: 2 };
const m7 = Matrix2D.translation(1, 2);
const transformed = m7.apply(point.x, point.y);
assert(almostEqual(transformed.x, 2));
assert(almostEqual(transformed.y, 4));
//# sourceMappingURL=test_vector_math.js.map