import test from 'node:test';
import assert from 'node:assert/strict';
import { Village } from '../public/model.mjs';
import { DEFAULTS, normalizeSettings, publicSettings, filtered } from '../lib/settings.mjs';
const measure = chat => ({ w: 220, h: 62, lines: [chat.message] });
const chat = (id, nickname = id, message = '안녕하세요') => ({ id: `${id}:1`, userId: id, nickname, message, streamerId: 'channel', at: 0 });
test('chatting shrimp stops, keeps identity through nickname changes, then resumes walking', () => {
  const v = new Village(DEFAULTS); v.chat(chat('one'), 1000); v.step(1000, 0, measure);
  const a = v.agents.get('channel:one'), x = a.x;
  v.step(2000, 1, measure); assert.equal(a.x, x); assert.equal(a.talking, true);
  v.chat(chat('one', '새닉네임', '다시 말해요'), 2100); assert.equal(v.agents.size, 1); assert.equal(a.nickname, '새닉네임'); assert.equal(v.bubbles.length, 1);
  assert.equal(v.bubbles[0].chat.message, '다시 말해요');
  v.step(9000, 1, measure); assert.equal(a.talking, false); assert.notEqual(a.x, x);
});
test('crowded bubble rectangles never overlap or leave viewport', () => {
  const v = new Village({ ...DEFAULTS, maxBubbles: 8 }); v.resize(640, 480);
  for (let i = 0; i < 24; i++) v.chat(chat('viewer' + i), 0);
  v.step(0, 0, measure); assert.ok(v.bubbles.length > 0); assert.ok(v.bubbles.length <= 8);
  for (const a of v.bubbles) { assert.ok(a.x >= 0 && a.y >= 0 && a.x + a.w <= 640 && a.y + a.h <= 480);
    for (const b of v.bubbles) if (a !== b) assert.ok(a.x + a.w <= b.x || b.x + b.w <= a.x || a.y + a.h <= b.y || b.y + b.h <= a.y);
  }
});
test('viewer and queue memory stay bounded during chat bursts', () => {
  const v = new Village(DEFAULTS);
  for (let i = 0; i < 5000; i++) v.chat(chat('viewer' + i), i);
  assert.equal(v.agents.size, 24); assert.ok(v.queue.size <= 24); assert.ok(v.bubbles.length <= 5);
  v.step(700000, .05, measure); assert.equal(v.agents.size, 0); assert.equal(v.queue.size, 0);
});
test('settings changes remove blocked viewers and banned messages immediately', () => {
  const v = new Village(DEFAULTS); v.chat(chat('UPPER'), 0); v.step(0, 0, measure);
  v.configure({ blockedUsers: ['upper'] }); assert.equal(v.agents.size, 0); assert.equal(v.bubbles.length, 0);
  v.chat(chat('two', '새우', '금지단어 들어있음'), 100); v.step(100, 0, measure); assert.equal(v.bubbles.length, 1);
  v.configure({ bannedWords: ['금지단어'] }); assert.equal(v.bubbles.length, 0);
});
test('settings reject invalid endpoints, numbers, and streamer IDs; secrets stay private', () => {
  for (const bad of [{ size: 999 }, { speed: 'oops' }, { coreUrl: 'https://host/v1/ws' }, { coreUrl: 'ws://host/v1/ws?key=secret' }, { streamerId: 'https://sooplive.co.kr' }]) assert.throws(() => normalizeSettings(bad));
  const cfg = normalizeSettings({ apiKey: 'secret', coreUrl: 'wss://host/v1/ws', streamerId: 'whale_123' });
  assert.equal(publicSettings(cfg).hasApiKey, true); assert.ok(!JSON.stringify(publicSettings(cfg)).includes('secret'));
  assert.equal(filtered(chat('one', '새우', 'BAD text'), { blockedUsers: [], bannedWords: ['bad'] }), true);
});
