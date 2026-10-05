// Reusable bounded LRU. Values can own GPU-backed canvases; dropping the reference
// permits the browser to release them. Never cache an unbounded stream of phases.
export class FrameCache {
  constructor(limit = 32 * 1024 * 1024) { this.limit = limit; this.bytes = 0; this.entries = new Map(); }
  get(key) { const entry = this.entries.get(key); if (!entry) return; this.entries.delete(key); this.entries.set(key, entry); return entry.value; }
  put(key, value, bytes) {
    if (this.entries.has(key)) { this.bytes -= this.entries.get(key).bytes; this.entries.delete(key); }
    if (bytes > this.limit) return value;
    while (this.bytes + bytes > this.limit && this.entries.size) { const oldest = this.entries.keys().next().value; this.bytes -= this.entries.get(oldest).bytes; this.entries.delete(oldest); }
    this.entries.set(key, { value, bytes }); this.bytes += bytes; return value;
  }
  clear() { this.entries.clear(); this.bytes = 0; }
}
export class FrameMeter {
  constructor() { this.intervals = []; this.draws = []; this.last = 0; }
  sample(now, cost) {
    if (this.last && now > this.last && now - this.last < 1000) { this.intervals.push(now - this.last); this.draws.push(cost); if (this.intervals.length > 120) { this.intervals.shift(); this.draws.shift(); } }
    this.last = now;
  }
  reset() { this.last = 0; this.intervals.length = 0; this.draws.length = 0; }
  snapshot() {
    const n = this.intervals.length; if (!n) return { fps: 0, drawMs: 0, frameP95Ms: 0 };
    const sorted = [...this.intervals].sort((a,b) => a-b);
    return { fps: Math.round(1000 * n / this.intervals.reduce((a,b) => a+b,0)), drawMs: Math.round(this.draws.reduce((a,b) => a+b,0) / n * 100) / 100, frameP95Ms: Math.round(sorted[Math.ceil(n * .95)-1] * 100) / 100 };
  }
}
