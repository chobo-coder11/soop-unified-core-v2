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

test('idle variety waits for deceleration and chat reaction plays once', async () => {
  const { idleMotion, IDLE_ACTIONS, ACTION_MS } = await import('../public/motion.mjs');
  const a = { seed:0,x:320,dir:1,velocity:28,phase:0,nextMotionAt:0 };
  idleMotion(a,100,true); assert.equal(a.motionPending,true);
  for (let i=0;i<10;i++) moveAgent(a,100+i*50,.05,config,true);
  assert.equal(a.motionPending,false); assert.ok(a.motionStarted > 100);
  assert.equal(a.motionUntil-a.motionStarted,ACTION_MS[a.motion]);
  const seen = new Set();
  for (let i=0;i<IDLE_ACTIONS.length*2;i++) { a.nextMotionAt=0;a.motionUntil=0;idleMotion(a,10000+i*3000,true);seen.add(a.motion); }
  assert.deepEqual([...seen].sort(),[...IDLE_ACTIONS].sort());
  assert.equal(visualMotion({ ...a,talking:true,reaction:'jump',reactionAt:0 },5000).mode,'talk');
  for (const action of IDLE_ACTIONS) {
    const start=visualMotion({ ...a,velocity:0,motion:action,motionStarted:0 },0);
    const end=visualMotion({ ...a,velocity:0,motion:action,motionStarted:0 },ACTION_MS[action]);
    assert.ok(Math.abs(start.bob) < .00001 && Math.abs(end.bob) < .00001);
    assert.equal(start.rotation,0);assert.ok(Math.abs(end.rotation) < .00001);
    assert.equal(start.sx,1);assert.equal(end.sx,1);
  }
});
