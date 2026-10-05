import { Village } from './model.mjs';
const canvas = document.querySelector('#village');
const ctx = canvas.getContext('2d', { alpha: true });
const image = new Image(); image.src = '/assets/shrimp.png';
image.onerror = () => { document.querySelector('#overlay-error').hidden = false; };
const defaults = { size: 108, speed: 28, maxCharacters: 24, maxBubbles: 5, ambientCharacters: 6, bubbleSeconds: 5, idleMinutes: 5, bottom: 20, fontSize: 19, showNames: 'speaking', palette: 'pastel' };
const village = new Village(defaults);
let status = 'idle', preview = new URLSearchParams(location.search).has('preview'), loaded = false, previous = performance.now();
const connection = new EventSource('/events');
connection.addEventListener('snapshot', e => {
  const data = JSON.parse(e.data); village.configure(data.settings); status = data.status.state;
  village.clear(); for (const chat of data.recent) village.chat(chat, performance.now()); loaded = true;
});
connection.addEventListener('settings', e => { village.configure(JSON.parse(e.data)); });
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
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0); village.resize(innerWidth, innerHeight);
}
addEventListener('resize', resize); resize();
function font(size, weight = 600) { return `${weight} ${size}px "Malgun Gothic", "Apple SD Gothic Neo", sans-serif`; }
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
  ctx.font = font(village.settings.fontSize);
  const lines = wrap(chat.message, maximum - 28, 3);
  const w = Math.max(Math.min(120, maximum), Math.min(maximum, Math.max(...lines.map(l => ctx.measureText(l).width)) + 28));
  return { lines, w, h: lines.length * (village.settings.fontSize + 7) + 26 };
}
function roundRect(x, y, w, h, r) { ctx.beginPath(); ctx.roundRect(x, y, w, h, r); }
function sprite(a, now, ambient = false) {
  if (!image.complete || !image.naturalWidth) return;
  const s = village.settings.size, h = s * image.naturalHeight / image.naturalWidth;
  const walk = !a.talking && !a.waiting && now >= (a.idleUntil || 0);
  const bob = walk ? Math.sin(a.phase) * 3 : a.talking ? Math.sin(now / 170) * 1.1 : Math.sin(now / 700 + a.phase) * .8;
  const base = village.height - village.settings.bottom - 18;
  ctx.save(); ctx.translate(a.x, base - h / 2 + bob);
  if (!a.talking) ctx.scale(a.dir < 0 ? -1 : 1, 1);
  if (walk) ctx.rotate(Math.sin(a.phase) * .045);
  if (a.talking) ctx.scale(1 + Math.sin(now / 170) * .014, 1 - Math.sin(now / 170) * .014);
  const hue = village.settings.palette === 'pastel' ? [0, 330, 18, 160, 285, 45][a.seed % 6] : 0;
  ctx.filter = `hue-rotate(${hue}deg)`;
  ctx.globalAlpha = ambient ? (preview ? .8 : 1) : Math.min(1, (now - a.born) / 450);
  ctx.drawImage(image, -s / 2, -h / 2, s, h); ctx.restore();
  const names = village.settings.showNames;
  if (!ambient && (names === 'always' || (names === 'speaking' && a.talking))) {
    ctx.font = font(13, 700); const name = wrap(a.nickname, 152, 1)[0];
    const w = ctx.measureText(name).width + 18;
    const nx = Math.max(4, Math.min(village.width - w - 4, a.x - w / 2));
    ctx.fillStyle = 'rgba(36,27,36,.85)'; roundRect(nx, base + 2, w, 23, 11); ctx.fill();
    ctx.fillStyle = '#fff9f6'; ctx.textAlign = 'center'; ctx.textBaseline = 'middle'; ctx.fillText(name, nx + w / 2, base + 14);
  }
}
function drawBubble(b, now) {
  const a = village.agents.get(b.key); if (!a) return;
  ctx.save(); ctx.globalAlpha = Math.min(1, (now - b.started) / 140, (b.until - now) / 200);
  ctx.font = font(village.settings.fontSize);
  // Recompute wrapped lines after same-viewer message updates, retaining allocated size.
  const lines = wrap(b.chat.message, b.w - 28, Math.max(1, Math.floor((b.h - 26) / (village.settings.fontSize + 7))));
  const anchor = Math.max(b.x + 16, Math.min(b.x + b.w - 16, a.x));
  const endY = village.height - village.settings.bottom - village.settings.size * .77 - 18;
  ctx.strokeStyle = 'rgba(242,173,151,.9)'; ctx.lineWidth = 2;
  ctx.beginPath(); ctx.moveTo(anchor, b.y + b.h); ctx.lineTo(a.x, endY); ctx.stroke();
  ctx.shadowColor = 'rgba(30,14,27,.16)'; ctx.shadowBlur = 14; ctx.shadowOffsetY = 4;
  ctx.fillStyle = '#fff9f4'; roundRect(b.x, b.y, b.w, b.h, 17); ctx.fill();
  ctx.shadowBlur = 0; ctx.shadowOffsetY = 0; ctx.lineWidth = 1.5; ctx.strokeStyle = '#f0c4b7'; ctx.stroke();
  ctx.fillStyle = '#3d2d36'; ctx.textAlign = 'left'; ctx.textBaseline = 'top';
  lines.forEach((line, i) => ctx.fillText(line, b.x + 14, b.y + 13 + i * (village.settings.fontSize + 7)));
  ctx.restore();
}
function render(now) {
  const dt = Math.min(.05, Math.max(0, (now - previous) / 1000)); previous = now;
  ctx.clearRect(0, 0, village.width, village.height);
  village.step(now, dt, measure);
  const ambientCount = loaded ? Math.max(0, Math.min(village.settings.ambientCharacters, village.settings.maxCharacters) - village.agents.size) : 0;
  for (let i = 0; i < ambientCount; i++) {
    const margin = village.settings.size / 2, span = Math.max(1, village.width - margin * 2);
    const t = (now / 1000 * village.settings.speed * (.7 + i * .07) + i * span / 6) % (span * 2);
    sprite({ x: margin + (t <= span ? t : span * 2 - t), phase: now / 150 + i, dir: t <= span ? 1 : -1, seed: i, born: 0 }, now, true);
  }
  for (const a of village.agents.values()) sprite(a, now);
  for (const b of village.bubbles) drawBubble(b, now);
  // Read-only diagnostics used for testing; no chat DOM injection or HTML rendering.
  window.overlayStats = { characters: village.agents.size, ambientCharacters: ambientCount, bubbles: village.bubbles.length, queued: village.queue.size, dropped: village.dropped, status,
    agents: [...village.agents.values()].map(a => ({ userId: a.userId, nickname: a.nickname, x: a.x, talking: a.talking })),
    boxes: village.bubbles.map(b => ({ x: b.x, y: b.y, w: b.w, h: b.h, nickname: b.chat.nickname, message: b.chat.message })) };
  requestAnimationFrame(render);
}
requestAnimationFrame(render);
