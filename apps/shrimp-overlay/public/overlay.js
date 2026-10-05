import { EmoteLayer } from './emotes.mjs';
import { FrameCache, FrameMeter } from './rendering.mjs';
import { Village } from './model.mjs';
import { visualMotion, idleMotion, moveAgent } from './motion.mjs';
const emoteLayer = new EmoteLayer(document.querySelector('#emote-layer'));
const canvas = document.querySelector('#village');
const ctx = canvas.getContext('2d', { alpha: true });
const image = new Image(); image.src = '/assets/shrimp.png';
image.onerror = () => { document.querySelector('#overlay-error').hidden = false; };
const frameBounds = new WeakMap();
function prepareFrames(img) {
  img.addEventListener('load', () => {
    const c = document.createElement('canvas'); c.width = img.naturalWidth; c.height = img.naturalHeight;
    const g = c.getContext('2d'); g.drawImage(img, 0, 0); const pixels = g.getImageData(0, 0, c.width, c.height).data;
    const frames = [];
    for (let i = 0; i < 8; i++) {
      const x0 = Math.round(i % 4 * c.width / 4), y0 = Math.round(Math.floor(i / 4) * c.height / 2);
      const x1 = Math.round((i % 4 + 1) * c.width / 4), y1 = Math.round((Math.floor(i / 4) + 1) * c.height / 2);
      let left = x1, right = x0, top = y1, bottom = y0;
      for (let y = y0; y < y1; y++) for (let x = x0; x < x1; x++) if (pixels[(y * c.width + x) * 4 + 3] > 32) { left = Math.min(left,x); right = Math.max(right,x+1); top = Math.min(top,y); bottom = Math.max(bottom,y+1); }
      frames.push({ x: left, y: top, w: Math.max(1,right-left), h: Math.max(1,bottom-top) });
    }
    frameBounds.set(img, frames);
  });
}
const textureCache = new FrameCache();
const blendSurface = document.createElement('canvas');
let blendContext = blendSurface.getContext('2d');
function frameTexture(img, index, size, hue) {
  const frame = frameBounds.get(img)?.[index]; if (!frame) return null;
  const dpr = Math.min(window.devicePixelRatio || 1, 1.5), pixels = Math.ceil(size * dpr);
  const key = `${img === walkAtlas ? 'walk' : 'pose'}:${index}:${pixels}:${hue}`;
  const existing = textureCache.get(key); if (existing) return existing;
  const tile = document.createElement('canvas'); tile.width = pixels; tile.height = pixels;
  const g = tile.getContext('2d');
  const scale = Math.min(pixels / frame.w, pixels * .9 / frame.h), w = frame.w * scale, h = frame.h * scale;
  g.filter = hue ? `hue-rotate(${hue}deg)` : 'none';
  g.drawImage(img, frame.x, frame.y, frame.w, frame.h, (pixels - w) / 2, pixels - h, w, h);
  return textureCache.put(key, tile, pixels * pixels * 4);
}
function drawFrame(img, index, size, h, hue, nextIndex = index, mix = 0) {
  const first = frameTexture(img, index, size, hue); if (!first) return;
  if (mix <= 0 || index === nextIndex) { ctx.drawImage(first, -size / 2, h / 2 - size, size, size); return; }
  const next = frameTexture(img, nextIndex, size, hue); if (!next) return;
  if (blendSurface.width !== first.width) { blendSurface.width = first.width; blendSurface.height = first.height; blendContext = blendSurface.getContext('2d'); }
  const g = blendContext; g.clearRect(0,0,blendSurface.width,blendSurface.height);
  // Weighted premultiplied-alpha addition on a transparent offscreen surface.
  // Ordinary source-over blending would make the character flicker translucent.
  g.globalCompositeOperation = 'source-over'; g.globalAlpha = 1 - mix; g.drawImage(first,0,0);
  g.globalCompositeOperation = 'lighter'; g.globalAlpha = mix; g.drawImage(next,0,0);
  g.globalAlpha = 1; g.globalCompositeOperation = 'source-over';
  ctx.drawImage(blendSurface, -size / 2, h / 2 - size, size, size);
}
const atlas = new Image(); prepareFrames(atlas); atlas.src = '/assets/shrimp-poses.png';
const walkAtlas = new Image(); prepareFrames(walkAtlas); walkAtlas.src = '/assets/shrimp-walk.png';
Promise.all([document.fonts.load('20px Jua'), document.fonts.load('20px Gaegu')]).then(() => {
  for (const b of village.bubbles) village.queue.set(b.key, { ...b.chat, queuedAt: performance.now() });
  village.bubbles = [];
}).catch(() => {});
const ambientAgents = [];
const defaults = { size: 108, speed: 28, maxCharacters: 24, maxBubbles: 5, ambientCharacters: 6, bubbleSeconds: 5, idleMinutes: 5, bottom: 20, fontSize: 19, showNames: 'speaking', palette: 'pastel' };
const village = new Village(defaults);
const frameMeter = new FrameMeter();
let lastDiagnostics = -Infinity, previewPaused = false, lastPaintTop = 0;
addEventListener('message', event => { if (preview && event.source === parent && event.origin === location.origin && event.data?.type === 'shrimp-preview-visibility') { previewPaused = !event.data.visible; previous = performance.now(); frameMeter.reset(); } });
let status = 'idle', preview = new URLSearchParams(location.search).has('preview'), loaded = false, previous = performance.now();
const connection = new EventSource('/events');
connection.addEventListener('snapshot', e => {
  const data = JSON.parse(e.data); village.configure(data.settings); status = data.status.state;
  village.clear(); for (const chat of data.recent) village.chat(chat, performance.now()); loaded = true;
});
connection.addEventListener('settings', e => { textureCache.clear(); village.configure(JSON.parse(e.data)); });
connection.addEventListener('filter', e => village.configure(JSON.parse(e.data)));
connection.addEventListener('chat', e => { village.chat(JSON.parse(e.data), performance.now()); });
connection.addEventListener('clear', () => village.clear());
connection.addEventListener('hide-user', e => village.hideUser(JSON.parse(e.data).userId));
connection.addEventListener('status', e => { status = JSON.parse(e.data).state; });
connection.onerror = () => { status = 'disconnected'; };
function resize() {
  const dpr = Math.min(window.devicePixelRatio || 1, 2);
  canvas.width = Math.round(innerWidth * dpr); canvas.height = Math.round(innerHeight * dpr);
  canvas.style.width = innerWidth + 'px'; canvas.style.height = innerHeight + 'px';
  lastPaintTop = 0; textureCache.clear();
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0); village.resize(innerWidth, innerHeight);
}
addEventListener('resize', resize); resize();
function font(size, weight = village.settings.fontWeight === 'bold' ? 700 : 400) { return village.settings.fontFamily !== 'system' ? `400 ${size}px ${village.settings.fontFamily === "gaegu" ? "Gaegu" : "Jua"}, "Malgun Gothic", "Segoe UI Emoji", "Apple Color Emoji", sans-serif` : `${weight} ${size}px "Malgun Gothic", "Apple SD Gothic Neo", "Segoe UI Emoji", "Apple Color Emoji", sans-serif`; }
function wrap(text, maxWidth, maxLines) {
  const lines = []; let line = '';
  for (const ch of text.replace(/\r/g, '')) {
    if (ch === '\n' || ctx.measureText(line + ch).width > maxWidth) {
      lines.push(line); line = ch === '\n' ? '' : ch;
      if (lines.length >= maxLines) {
        let last = lines[maxLines - 1]; while (ctx.measureText(last + '…').width > maxWidth) last = last.slice(0, -1);
        lines[maxLines - 1] = last + '…'; return lines;
      }
    } else line += ch;
  }
  if (line || !lines.length) lines.push(line); return lines;
}
function measure(chat, maximum) {
  if (chat.emoticon) {
    const asset = emoteLayer.asset(chat.emoticon);
    if (!asset.ready) return { pending: true };
    const pad = village.settings.bubblePadding ?? 16, size = Math.min(village.settings.emoteSize || 88, maximum - pad * 2);
    return { w: Math.max(120, size + pad * 2), h: size + pad * 2, lines: [] };
  }
  ctx.font = font(village.settings.fontSize);
  const lines = wrap(chat.message, maximum - (village.settings.bubblePadding ?? 16) * 2, village.settings.bubbleMaxLines || 4);
  const w = Math.max(Math.min(120, maximum), Math.min(maximum, Math.max(...lines.map(l => ctx.measureText(l).width)) + (village.settings.bubblePadding ?? 16) * 2));
  return { lines, w, h: lines.length * (village.settings.fontSize + 7) + (village.settings.bubblePadding ?? 16) * 2 };
}
function roundRect(x, y, w, h, r) { ctx.beginPath(); ctx.roundRect(x, y, w, h, r); }
function sprite(a, now, ambient = false) {
  if (!image.complete || !image.naturalWidth) return;
  const s = village.settings.size;
  const useAtlas = atlas.complete && atlas.naturalWidth > 0;
  const h = useAtlas ? s : s * image.naturalHeight / image.naturalWidth;
  const motion = visualMotion(a, now, village.settings.extraMotion !== false);
  const base = village.characterBase() + motion.bob;
  ctx.save(); ctx.translate(a.x, base - h / 2);
  const useWalk = motion.mode === 'walk' && walkAtlas.complete && walkAtlas.naturalWidth > 0;
  if (!useWalk && !motion.faceForward) ctx.scale(a.dir > 0 ? -1 : 1, 1);
  ctx.rotate(motion.rotation); ctx.scale(motion.sx, motion.sy);
  const hue = village.settings.palette === 'pastel' ? [0, 330, 18, 160, 285, 45][a.seed % 6] : 0;
  ctx.filter = 'none';
  ctx.globalAlpha = ambient ? (preview ? .8 : 1) : Math.min(1, (now - a.born) / 450);
  if (useWalk) {
    const row = a.dir > 0 ? 0 : 4;
    drawFrame(walkAtlas, motion.walkFrame + row, s, h, hue, motion.walkNextFrame + row, motion.walkMix);
  } else if (useAtlas) {
    // The second walking pose faces the other way in the atlas; normalize it.
    if (motion.pose === 2) ctx.scale(-1, 1);
    drawFrame(atlas, motion.pose, s, h, hue, motion.nextPose, motion.poseMix);
  } else ctx.drawImage(image, -s / 2, -h / 2, s, h);
  ctx.restore();
  if (motion.effect && village.settings.extraMotion !== false) {
    ctx.save(); ctx.font = font(14); ctx.textAlign = 'center'; ctx.fillStyle = '#f1c29b';
    if (motion.effect === 'sleep') { ctx.fillStyle = '#c6cee9'; ctx.fillText('z Z', a.x + s * .31, base - h * .72 - Math.sin(now / 400) * 3); }
    else if (motion.effect === 'sparkle') { ctx.fillText('✦', a.x + s * .36, base - h * .75 + motion.bob); ctx.fillText('✧', a.x - s * .32, base - h * .55 + motion.bob); }
    else if (motion.effect === 'question') { ctx.fillText('?', a.x + s * .3, base - h * .83); }
    else if (motion.effect === 'hello') { ctx.strokeStyle = '#efc0ae'; ctx.lineWidth = 2; ctx.beginPath(); ctx.arc(a.x + s * .34, base - h * .68, 8, -.8, .8); ctx.stroke(); }
    ctx.restore();
  }
  const names = village.settings.showNames;
  if (!ambient && (names === 'always' || (names === 'speaking' && a.talking))) {
    const c = village.settings, fs = c.nameFontSize || 18, px = c.namePaddingX ?? 12, py = c.namePaddingY ?? 5;
    ctx.save(); ctx.globalAlpha = (c.nameOpacity ?? 100) / 100;
    ctx.font = font(fs); const name = wrap(a.nickname, Math.max(20, Math.min(c.nameMaxWidth || 200, village.width - 8) - px * 2), 1)[0];
    const w = Math.min(village.width - 8, ctx.measureText(name).width + px * 2), nh = fs + py * 2;
    const nx = Math.max(4, Math.min(village.width - w - 4, a.x - w / 2));
    const ny = c.namePosition === 'above' ? base - s * .9 - (c.nameGap ?? 2) - nh : base + (c.nameGap ?? 2);
    ctx.fillStyle = c.nameBg || '#fff3e9'; roundRect(nx, ny, w, nh, Math.min(c.nameRadius ?? 12, nh / 2)); ctx.fill();
    if (c.nameBorderWidth) { ctx.strokeStyle = c.nameBorder; ctx.lineWidth = c.nameBorderWidth; ctx.stroke(); }
    ctx.fillStyle = c.nameTextColor || '#815b58'; ctx.textAlign = 'center'; ctx.textBaseline = 'middle'; ctx.fillText(name, nx + w / 2, ny + nh / 2);
    ctx.restore();
  }
}
function drawBubble(b, now) {
  const a = village.agents.get(b.key); if (!a) return;
  b = { ...b, y: b.y + visualMotion(a, now, village.settings.extraMotion !== false).bob };
  ctx.save(); ctx.globalAlpha = Math.min(1, (now - b.started) / 140, (b.until - now) / 200);
  ctx.font = font(village.settings.fontSize);
  const c = village.settings, padding = c.bubblePadding ?? 16;
  ctx.globalAlpha *= (c.bubbleOpacity ?? 100) / 100;
  const lines = wrap(b.chat.message, b.w - padding * 2, Math.min(c.bubbleMaxLines || 4, Math.max(1, Math.floor((b.h - padding * 2) / (c.fontSize + 7)))));
  const radius = Math.min(c.bubbleRadius ?? 20, b.h / 2, b.w / 2);
  const anchor = Math.max(b.x + radius + 8, Math.min(b.x + b.w - radius - 8, a.x));
  ctx.shadowColor = 'rgba(30,14,27,.14)'; ctx.shadowBlur = 8; ctx.shadowOffsetY = 3;
  ctx.fillStyle = c.bubbleBg || '#fff9f4'; roundRect(b.x, b.y, b.w, b.h, radius); ctx.fill();
  ctx.shadowBlur = 0; ctx.shadowOffsetY = 0; ctx.lineWidth = c.bubbleBorderWidth ?? 2; ctx.strokeStyle = c.bubbleBorder || '#efc4b5';
  if (ctx.lineWidth) ctx.stroke();
  const tipY = b.y + b.h + Math.min(10, c.bubbleGap ?? 10);
  ctx.beginPath(); ctx.moveTo(anchor - 7, b.y + b.h - 1); ctx.lineTo(a.x, tipY); ctx.lineTo(anchor + 7, b.y + b.h - 1); ctx.fill();
  if (c.bubbleBorderWidth) { ctx.beginPath(); ctx.moveTo(anchor - 7, b.y + b.h); ctx.lineTo(a.x, tipY); ctx.lineTo(anchor + 7, b.y + b.h); ctx.stroke(); }
  ctx.fillStyle = c.bubbleTextColor || '#59434d'; ctx.textAlign = 'left'; ctx.textBaseline = 'top';
  if (b.chat.emoticon) {
    const size = Math.min(c.emoteSize || 88, b.w - padding * 2);
    const displayed = emoteLayer.draw(b.key, b.chat.emoticon, { x: b.x + (b.w - size) / 2, y: b.y + padding, size, opacity: ctx.globalAlpha });
    if (!displayed) { ctx.textAlign = 'center'; ctx.textBaseline = 'middle'; ctx.font = font(Math.min(16, c.fontSize)); ctx.fillText('이모티콘 로드 실패', b.x + b.w / 2, b.y + b.h / 2, b.w - padding * 2); }
  } else lines.forEach((line, i) => ctx.fillText(line, b.x + padding, b.y + padding + i * (c.fontSize + 7)));
  ctx.restore();
}
function render(now) {
  if (preview && (previewPaused || document.hidden)) { previous = now; frameMeter.reset(); requestAnimationFrame(render); return; }
  const drawStarted = performance.now();
  const dt = Math.min(.05, Math.max(0, (now - previous) / 1000)); previous = now;
  village.step(now, dt, measure);
  const paintTop = Math.max(0, Math.min(village.characterBase() - village.settings.size - 64, ...village.bubbles.map(b => b.y - 48)));
  const clearTop = Math.min(lastPaintTop, paintTop);
  ctx.clearRect(0, clearTop, village.width, village.height - clearTop);
  lastPaintTop = paintTop;
  const ambientCount = loaded ? Math.max(0, Math.min(village.settings.ambientCharacters, village.settings.maxCharacters) - village.agents.size) : 0;
  for (let i = 0; i < ambientCount; i++) {
    const margin = village.settings.size / 2, span = Math.max(1, village.width - margin * 2);
    const a = ambientAgents[i] ||= { x: margin + (i + .5) * span / 12, dir: i % 2 ? -1 : 1, phase: i, seed: i * 719, born: now };
    idleMotion(a, now, village.settings.extraMotion !== false);
    a.speed = .7 + i * .04;
    moveAgent(a, now, dt, { speed: village.settings.speed, size: village.settings.size, width: village.width }, a.motion !== 'walk');
    sprite(a, now, true);
  }
  for (const a of village.agents.values()) sprite(a, now);
  for (const b of village.bubbles) drawBubble(b, now);
  emoteLayer.retain(new Set(village.bubbles.filter(b => b.chat.emoticon).map(b => b.key)));
  // Read-only diagnostics used for testing; no chat DOM injection or HTML rendering.
  frameMeter.sample(now, performance.now() - drawStarted);
  if (now - lastDiagnostics >= 500) {
  lastDiagnostics = now;
  const performanceStats = frameMeter.snapshot();
  window.overlayStats = { characters: village.agents.size, ambientCharacters: ambientCount, bubbles: village.bubbles.length, queued: village.queue.size, dropped: village.dropped, status, ...performanceStats, textureCacheBytes: textureCache.bytes,
    agents: [...village.agents.values()].map(a => ({ userId: a.userId, nickname: a.nickname, x: a.x, talking: a.talking })),
    boxes: village.bubbles.map(b => ({ x: b.x, y: b.y, w: b.w, h: b.h, nickname: b.chat.nickname, message: b.chat.message })) };
  if (preview) parent.postMessage({ type: 'shrimp-performance', ...performanceStats }, location.origin);
  }
  requestAnimationFrame(render);
}
requestAnimationFrame(render);
