import test from 'node:test';
import assert from 'node:assert/strict';
import { FrameCache, FrameMeter } from '../public/rendering.mjs';
test('frame cache reuses textures and stays bounded with LRU eviction', () => {
  const c = new FrameCache(100), a = {}, b = {};
  c.put('a',a,40); c.put('b',b,40); assert.equal(c.get('a'),a);
  c.put('c',{},40); assert.equal(c.get('b'),undefined); assert.equal(c.bytes,80);
  c.put('a',{},60); assert.equal(c.bytes,100);
  c.put('oversized',{},200); assert.equal(c.get('oversized'),undefined);
  c.clear(); assert.equal(c.bytes,0); assert.equal(c.entries.size,0);
});
test('frame meter distinguishes slow refresh from expensive drawing and resets after suspension', () => {
  const m = new FrameMeter();
  for (let i=0; i<140; i++) m.sample(100 + i * 1000/60, 2);
  assert.equal(m.snapshot().fps,60); assert.equal(m.snapshot().drawMs,2); assert.ok(m.intervals.length <= 120);
  m.reset(); for (let i=0; i<60; i++) m.sample(100 + i * 1000/30, 1);
  assert.equal(m.snapshot().fps,30); assert.equal(m.snapshot().drawMs,1);
  m.reset(); assert.equal(m.snapshot().fps,0);
});
