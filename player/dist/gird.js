export class Grid {
    constructor(width, height) {
        this.width = width;
        this.height = height;
        this.data = new Uint8Array(width * height);
    }
    // Fast index calculation - no string creation or hash lookups
    set(x, y, value) {
        this.data[y * this.width + x] = value ? 1 : 0;
    }
    get(x, y) {
        return this.data[y * this.width + x] === 1;
    }
    clear() {
        this.data.fill(0);
    }
}
//# sourceMappingURL=gird.js.map