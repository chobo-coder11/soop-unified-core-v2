export const POSES = Object.freeze({ idle: 0, walkA: 1, walkB: 2, wave: 3, talk: 4, jump: 5, sleep: 6, laugh: 7 });
export function reactionFor(message) {
  if (/!점프|!점프해|야호|신난다|🎉/.test(message)) return 'jump';
  if (/ㅋ{2,}|ㅎ{2,}|😂|🤣/.test(message)) return 'laugh';
  if (/!인사|안녕|하이|반가|어서오/.test(message)) return 'wave';
  return 'talk';
}
export function idleMotion(a, now, enabled = true) {
  if (!enabled) { a.motion = 'walk'; a.motionUntil = 0; return; }
  if (a.motionUntil > now) return;
  a.motion = 'walk';
  if (!Number.isFinite(a.nextMotionAt)) a.nextMotionAt = now + 3500 + a.seed % 7000;
  if (now < a.nextMotionAt) return;
  a.motionCycle = (a.motionCycle || 0) + 1;
  const choice = (a.seed + a.motionCycle) % 4;
  a.motion = ['wave', 'jump', 'sleep', 'laugh'][choice];
  a.motionStarted = now;
  a.motionUntil = now + [1400, 1000, 2600, 1200][choice];
  a.nextMotionAt = a.motionUntil + 5000 + (a.seed + a.motionCycle * 719) % 8000;
}
export function moveAgent(a, now, dt, { speed, size, width }, paused = false) {
  a.velocity ??= 0;
  const maximum = speed * (a.speed || 1), acceleration = Math.max(50, speed * 8);
  const margin = Math.min(width / 2, size * .5);
  const remaining = a.dir > 0 ? width - margin - a.x : a.x - margin;
  const stoppingDistance = a.velocity * a.velocity / (2 * acceleration) + 1;
  if (!paused && now >= (a.turnUntil || 0) && remaining <= stoppingDistance) a.pendingTurn = true;
  const target = paused || a.pendingTurn || now < (a.turnUntil || 0) ? 0 : a.dir * maximum;
  const old = a.velocity;
  a.velocity += Math.sign(target - a.velocity) * Math.min(Math.abs(target - a.velocity), acceleration * dt);
  const distance = (old + a.velocity) / 2 * dt;
  a.x = Math.max(margin, Math.min(width - margin, a.x + distance));
  // Step phase is tied to distance travelled, so feet do not run while sliding slowly.
  a.phase += Math.abs(distance) / Math.max(12, size * .32) * Math.PI * 2;
  if (a.pendingTurn && Math.abs(a.velocity) < .1) { a.pendingTurn = false; a.dir *= -1; a.turnUntil = now + 240; }
}
export function visualMotion(a, now, enabled = true) {
  const talking = Boolean(a.talking);
  const moving = Math.abs(a.velocity || 0) > .4;
  const mode = talking ? (enabled ? a.reaction || 'talk' : 'talk') : moving ? 'walk' : now < (a.turnUntil || 0) ? 'turn' : a.waiting ? 'idle' : (!enabled ? 'idle' : a.motion || 'idle');
  const since = Math.max(0, now - (talking ? a.reactionAt ?? a.lastChat : a.motionStarted ?? a.born ?? 0));
  const beat = Math.floor(since / 240) % 2;
  let pose = POSES.idle, bob = 0, rotation = 0, sx = 1, sy = 1, effect = '';
  if (mode === 'walk') { pose = Math.floor(a.phase / Math.PI * 2) % 2 ? POSES.walkA : POSES.walkB; bob = 0; rotation = 0; }
  else if (mode === 'talk') { pose = beat ? POSES.talk : POSES.idle; bob = Math.sin(since / 130) * 1.1; sx = 1 + Math.sin(since / 130) * .018; sy = 2 - sx; }
  else if (mode === 'wave') { pose = beat ? POSES.wave : POSES.idle; rotation = Math.sin(since / 140) * .06; effect = 'hello'; }
  else if (mode === 'laugh') { pose = beat ? POSES.laugh : POSES.jump; bob = -Math.abs(Math.sin(since / 120)) * 4; rotation = Math.sin(since / 95) * .05; effect = 'sparkle'; }
  else if (mode === 'jump') { pose = POSES.jump; const t = (since % 850) / 850; bob = -Math.sin(t * Math.PI) * 24; sy = t < .1 || t > .9 ? .92 : 1.03; sx = 2 - sy; effect = 'sparkle'; }
  else if (mode === 'sleep') { pose = POSES.sleep; sy = 1 + Math.sin(since / 480) * .02; effect = 'sleep'; }
  return { mode, pose, walkFrame: Math.floor(a.phase / (Math.PI * 2) * 4) % 4, bob, rotation, sx, sy, effect, faceForward: talking || mode !== 'walk' };
}
