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
