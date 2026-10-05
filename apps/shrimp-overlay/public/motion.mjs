export const POSES = Object.freeze({ idle: 0, walkA: 1, walkB: 2, wave: 3, talk: 4, jump: 5, sleep: 6, laugh: 7 });
export function reactionFor(message) {
  if (/!점프|!점프해|야호|신난다|🎉/.test(message)) return 'jump';
  if (/ㅋ{2,}|ㅎ{2,}|😂|🤣/.test(message)) return 'laugh';
  if (/!인사|안녕|하이|반가|어서오/.test(message)) return 'wave';
  return 'talk';
}
export const IDLE_ACTIONS = Object.freeze(['wave','jump','sleep','laugh','lookaround','stretch','hop','curious']);
export const ACTION_MS = Object.freeze({ wave:1500,jump:1000,sleep:2600,laugh:1400,lookaround:2400,stretch:1800,hop:1100,curious:1800 });
const smooth = t => { t = Math.max(0, Math.min(1,t)); return t*t*(3-2*t); };
export function idleMotion(a, now, enabled = true) {
  if (!enabled) { a.motion = 'walk'; a.motionUntil = 0; return; }
  if (a.motionUntil > now) return;
  a.motion = 'walk';
  if (!Number.isFinite(a.nextMotionAt)) a.nextMotionAt = now + 3500 + a.seed % 7000;
  if (now < a.nextMotionAt) return;
  a.motionCycle = (a.motionCycle || 0) + 1;
  const choice = (a.seed + a.motionCycle) % IDLE_ACTIONS.length;
  a.motion = IDLE_ACTIONS[choice];
  a.motionPending = true;
  a.motionStarted = now;
  a.motionUntil = now + ACTION_MS[a.motion];
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
  a.phase += Math.abs(distance) / Math.max(12, size * .17) * Math.PI * 2;
  if (paused && a.motionPending && Math.abs(a.velocity) < .4) {
    a.motionPending = false; const delay = now - a.motionStarted;
    a.motionStarted = now; a.motionUntil = now + (ACTION_MS[a.motion] || 1000); a.nextMotionAt += delay;
  }
  if (a.pendingTurn && Math.abs(a.velocity) < .1) { a.pendingTurn = false; a.dir *= -1; a.turnUntil = now + 240; }
}
export function visualMotion(a, now, enabled = true) {
  const talking = Boolean(a.talking), moving = Math.abs(a.velocity || 0) > .4;
  let mode = talking ? (enabled ? a.reaction || 'talk' : 'talk') : moving ? 'walk' : now < (a.turnUntil || 0) ? 'turn' : a.waiting ? 'idle' : (!enabled ? 'idle' : a.motion || 'idle');
  let since = Math.max(0, now - (talking ? a.reactionAt ?? a.lastChat : a.motionStarted ?? a.born ?? 0));
  // One reaction per message, then gentle talking; never loop five jumps for a five-second bubble.
  if (talking && mode !== 'talk' && since >= (ACTION_MS[mode] || 1500)) { since -= ACTION_MS[mode] || 1500; mode = 'talk'; }
  const duration = ACTION_MS[mode] || 1500, progress = Math.min(1,since/duration);
  const envelope = smooth(since/220) * smooth((duration-since)/260);
  let pose = POSES.idle, nextPose = POSES.idle, poseMix = 0, bob = 0, rotation = 0, sx = 1, sy = 1, effect = '';
  if (mode === 'walk') {
    pose = Math.floor(a.phase / Math.PI * 2) % 2 ? POSES.walkA : POSES.walkB; nextPose = pose;
    const strength = Math.min(1, Math.abs(a.velocity || 0) / 20);
    bob = -Math.abs(Math.sin(a.phase)) * 1.3 * strength; rotation = Math.sin(a.phase) * .012 * strength;
  } else if (mode === 'talk') {
    nextPose = POSES.talk; poseMix = (.5 + .5 * Math.sin(since/190)) * .65 * smooth(since/220);
    bob = Math.sin(since/240) * .65; sx = 1 + Math.sin(since/240) * .009; sy = 2-sx;
  } else if (mode === 'wave') {
    nextPose = POSES.wave; poseMix = envelope * (.7 + .3*Math.sin(since/160)); rotation = Math.sin(since/180)*.025*envelope; effect='hello';
  } else if (mode === 'laugh') {
    nextPose = POSES.laugh; poseMix = envelope * (.75 + .25*Math.sin(since/150)); bob=-Math.abs(Math.sin(since/180))*2.5*envelope; effect='sparkle';
  } else if (mode === 'jump' || mode === 'hop') {
    const lift = Math.sin(progress*Math.PI); nextPose=POSES.jump;poseMix=smooth(lift)*.9;
    bob = -lift * (mode === 'jump' ? 24 : 10); sy=1 + lift*.035 - (1-lift)*.025*envelope; sx=2-sy;
    if (mode === 'jump') effect='sparkle';
  } else if (mode === 'sleep') {
    nextPose=POSES.sleep;poseMix=envelope; sy=1+Math.sin(since/600)*.012*envelope;effect='sleep';
  } else if (mode === 'lookaround') {
    rotation = Math.sin(progress*Math.PI*2)*.04*envelope; sx=1-Math.abs(Math.sin(progress*Math.PI*2))*.025*envelope;
  } else if (mode === 'stretch') {
    const stretch = Math.sin(progress*Math.PI)*envelope; sx=1-stretch*.055;sy=1+stretch*.075;bob=-stretch*2;
  } else if (mode === 'curious') {
    rotation = Math.sin(progress*Math.PI)*.085*envelope; bob=-Math.sin(progress*Math.PI)*1.2; effect='question';
  }
  const framePhase = ((a.phase / (Math.PI * 2) * 4) % 4 + 4) % 4;
  const walkFrame = Math.floor(framePhase), fraction = framePhase-walkFrame;
  return { mode, pose, nextPose, poseMix, walkFrame, walkNextFrame:(walkFrame+1)%4, walkMix:smooth(fraction), bob, rotation, sx, sy, effect, faceForward:talking || mode !== 'walk' };
}
