import test from 'node:test';
import assert from 'node:assert/strict';
import { moveAgent, visualMotion, reactionFor } from '../public/motion.mjs';
const config = { width: 640, size: 108, speed: 28 };
test('walking eases to a stop and advances frames according to distance', () => {
  const a = { x: 320, dir: -1, speed: 1, phase: 0, velocity: -28 };
  moveAgent(a, 0, .05, config, true);
  assert.ok(a.velocity > -28 && a.velocity < 0); assert.ok(a.x < 320); assert.ok(a.phase > 0);
  for (let i = 1; i < 10; i++) moveAgent(a, i * 50, .05, config, true);
  assert.equal(a.velocity, 0); const x = a.x, phase = a.phase;
  moveAgent(a, 500, .05, config, true); assert.equal(a.x, x); assert.equal(a.phase, phase);
  a.velocity = -28; assert.equal(visualMotion(a, 0).mode, 'walk');
  assert.equal(visualMotion({ ...a, phase: Math.PI }, 0).walkFrame, 2);
});
test('shrimp turns only after stopping, stays within its own width, and reacts to chat', () => {
  const a = { x: 55, dir: -1, phase: 0, velocity: -28 };
  for (let i = 0; i < 60; i++) { moveAgent(a, i * 50, .05, config); assert.ok(a.x >= 54 && a.x <= 586); }
  assert.equal(a.dir, 1); assert.ok(a.x > 54);
  assert.equal(reactionFor('안녕!'), 'wave'); assert.equal(reactionFor('ㅋㅋㅋ'), 'laugh'); assert.equal(reactionFor('!점프'), 'jump');
});

test('walking pose transitions are continuous across frame boundaries and cycle wrap', () => {
  const a = { velocity: 28, phase: 0, dir: 1 };
  const before = visualMotion({ ...a, phase: Math.PI / 2 - .00001 }, 0);
  const after = visualMotion({ ...a, phase: Math.PI / 2 + .00001 }, 0);
  assert.equal(before.walkNextFrame, after.walkFrame);
  assert.ok(before.walkMix > .99999 && after.walkMix < .00001);
  assert.ok(Math.abs(before.bob - after.bob) < .0001);
  const wrap = visualMotion({ ...a, phase: Math.PI * 2 - .00001 }, 0);
  assert.equal(wrap.walkNextFrame, 0); assert.ok(wrap.walkMix > .99999);
  assert.equal(visualMotion({ ...a, phase: Math.PI / 4 }, 0).walkMix, .5);
});
test('movement and gait stay consistent at 30fps and 60fps', () => {
  function run(fps) { const a = { x: 320, dir: 1, speed: 1, phase: 0, velocity: 28 }; for (let i=0; i<fps; i++) moveAgent(a, i*1000/fps, 1/fps, config); return a; }
  const a = run(30), b = run(60);
  assert.ok(Math.abs(a.x-b.x) < .0001); assert.ok(Math.abs(a.phase-b.phase) < .0001);
  assert.ok(a.phase / (Math.PI * 2) > 1.4);
});
