import { idleMotion, reactionFor, moveAgent } from './motion.mjs';
export function hash(value) { let n = 2166136261; for (const ch of value) n = Math.imul(n ^ ch.charCodeAt(0), 16777619); return n >>> 0; }
export class Village {
  constructor(settings) { this.settings = settings; this.agents = new Map(); this.queue = new Map(); this.bubbles = []; this.dropped = 0; this.width = 1920; this.height = 1080; }
  configure(settings) {
    for (const b of this.bubbles) this.queue.set(b.key, { ...b.chat, queuedAt: b.started });
    this.bubbles = [];
    this.settings = { ...this.settings, ...settings };
    for (const chat of this.queue.values()) if (this.isFiltered(chat)) this.queue.delete(this.key(chat));
    for (const agent of this.agents.values()) if ((this.settings.blockedUsers || []).some(x => x.toLowerCase() === agent.userId.toLowerCase())) this.hideUser(agent.userId);
    this.bubbles = this.bubbles.filter(b => !this.isFiltered(b.chat));
    while (this.agents.size > this.settings.maxCharacters) this.evict();
    this.bubbles = this.bubbles.slice(0, this.settings.maxBubbles);
  }
  resize(width, height) { this.width = width; this.height = height; for (const a of this.agents.values()) a.x = Math.max(15, Math.min(width - 15, a.x)); this.bubbles = []; }
  key(chat) { return `${chat.streamerId}:${chat.userId}`; }
  isFiltered(chat) { return (this.settings.blockedUsers || []).some(x => x.toLowerCase() === chat.userId.toLowerCase()) || (this.settings.bannedWords || []).some(x => chat.message.toLowerCase().includes(x.toLowerCase())); }
  chat(chat, now) {
    if (this.isFiltered(chat)) return;
    const key = this.key(chat);
    let a = this.agents.get(key);
    if (!a) {
      if (this.agents.size >= this.settings.maxCharacters) this.evict();
      const seed = hash(key);
      const margin = this.settings.size / 2;
      a = { key, userId: chat.userId, nickname: chat.nickname, x: margin + (seed % 10000) / 10000 * Math.max(0, this.width - margin * 2),
        dir: seed % 2 ? 1 : -1, seed, phase: seed % 628 / 100, speed: .75 + (seed % 50) / 100,
        lastChat: now, idleUntil: now + 200, born: now, source: chat.source };
      this.agents.set(key, a);
    }
    a.nickname = chat.nickname; a.lastChat = now;
    a.reaction = reactionFor(chat.message); a.reactionAt = now;
    const active = this.bubbles.find(b => b.key === key);
    if (active) {
      // Each viewer owns one bubble; cap extension so continuous typing cannot monopolize a slot.
      active.layoutDirty = Boolean(active.chat.emoticon) !== Boolean(chat.emoticon);
      active.chat = chat; active.until = Math.min(active.started + this.settings.bubbleSeconds * 2000, now + this.settings.bubbleSeconds * 1000);
    } else { this.queue.set(key, { ...chat, queuedAt: now }); }
    while (this.queue.size > 160) { this.queue.delete(this.queue.keys().next().value); this.dropped++; }
  }
  evict() {
    const talking = new Set(this.bubbles.map(b => b.key));
    const sorted = [...this.agents.values()].sort((a, b) => Number(talking.has(a.key)) - Number(talking.has(b.key)) || a.lastChat - b.lastChat);
    if (sorted[0]) { const key = sorted[0].key; this.agents.delete(key); this.queue.delete(key); this.bubbles = this.bubbles.filter(b => b.key !== key); }
  }
  hideUser(userId) {
    for (const [key, a] of this.agents) if (a.userId === userId) { this.agents.delete(key); this.queue.delete(key); this.bubbles = this.bubbles.filter(b => b.key !== key); }
  }
  clear() { this.agents.clear(); this.queue.clear(); this.bubbles = []; }
  step(now, dt, measure) {
    for (const b of this.bubbles) if (b.layoutDirty) this.queue.set(b.key, { ...b.chat, queuedAt: now });
    this.bubbles = this.bubbles.filter(b => !b.layoutDirty && b.until > now && this.agents.has(b.key));
    for (const [key, chat] of this.queue) if (now - chat.queuedAt > 12000 || !this.agents.has(key)) { this.queue.delete(key); this.dropped++; }
    for (const a of this.agents.values()) {
      if (now - a.lastChat > this.settings.idleMinutes * 60000) { this.agents.delete(a.key); this.queue.delete(a.key); continue; }
      const wasTalking = a.talking;
      a.talking = this.bubbles.some(b => b.key === a.key);
      a.waiting = this.queue.has(a.key);
      if (wasTalking && !a.talking) { a.motion = 'walk'; a.motionUntil = 0; a.nextMotionAt = now + 5000 + a.seed % 4000; }
      if (!a.talking && !a.waiting && now >= a.idleUntil) idleMotion(a, now, this.settings.extraMotion !== false);
      moveAgent(a, now, dt, { speed: this.settings.speed, size: this.settings.size, width: this.width }, a.talking || a.waiting || now < a.idleUntil || a.motion !== 'walk');
    }
    for (const [key, chat] of this.queue) {
      if (this.bubbles.length >= this.settings.maxBubbles) break;
      const a = this.agents.get(key); if (!a || Math.abs(a.velocity || 0) > .4) continue;
      const measured = measure(chat, Math.min(this.settings.bubbleMaxWidth || 360, this.width - 24));
      if (measured.pending) continue;
      const rect = this.findSpace(a.x, measured);
      if (!rect) continue;
      this.bubbles.push({ key, chat, ...rect, lines: measured.lines, until: now + this.settings.bubbleSeconds * 1000, started: now });
      this.queue.delete(key); a.talking = true; a.reactionAt = now;
    }
  }
  characterBase() {
    const c = this.settings;
    const reserve = c.showNames !== 'never' && c.namePosition !== 'above' ? (c.nameFontSize || 18) + (c.namePaddingY ?? 5) * 2 + (c.nameGap ?? 2) + 4 : 18;
    return this.height - c.bottom - Math.max(18, reserve);
  }
  findSpace(x, measured) {
    const w = Math.min(measured.w, this.width - 16), h = measured.h;
    const bx = Math.max(8, Math.min(this.width - w - 8, x - w / 2));
    const nameHeight = this.settings.namePosition === 'above' && this.settings.showNames !== 'never' ? (this.settings.nameFontSize || 18) + 2 * (this.settings.namePaddingY ?? 5) + (this.settings.nameGap ?? 2) : 0;
    const baseline = this.characterBase() - this.settings.size * .9 - (this.settings.bubbleGap ?? 10) - nameHeight;
    for (let lane = 0; lane < 1; lane++) {
      const y = baseline - h - lane * (h + 14);
      if (y < 8) continue;
      const collision = this.bubbles.some(b => bx < b.x + b.w + 10 && bx + w + 10 > b.x && y < b.y + b.h + 10 && y + h + 10 > b.y);
      if (!collision) return { x: bx, y, w, h, lane };
    }
    return null;
  }
}
