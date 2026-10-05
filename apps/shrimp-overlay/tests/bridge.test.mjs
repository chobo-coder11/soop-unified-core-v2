import test from 'node:test';
import assert from 'node:assert/strict';
import http from 'node:http';
import { setTimeout as delay } from 'node:timers/promises';
import { WebSocketServer } from '../vendor/ws/wrapper.mjs';
import { CoreBridge, normalizeChat } from '../lib/bridge.mjs';
const event = (seq, id = `event-${seq}`, receivedAt = new Date().toISOString()) => ({ type: 'event', seq, event: { id, streamerId: 'channel', type: 'CHAT_MESSAGE', category: 'chat', user: { id: 'viewer', nickname: '부울경' }, message: '새우 채팅', receivedAt } });
async function waitFor(fn, limit = 2000) { const until = Date.now() + limit; while (Date.now() < until) { if (fn()) return; await delay(10); } throw new Error('condition timeout'); }
test('canonical chat shape and stale/private/other-channel filtering', () => {
  assert.equal(normalizeChat(event(1), 'channel').nickname, '부울경');
  assert.equal(normalizeChat(event(1), 'other'), null);
  assert.equal(normalizeChat(event(1, 'old', new Date(Date.now() - 30000).toISOString()), 'channel'), null);
  const whisper = event(2); whisper.event.type = 'WHISPER'; assert.equal(normalizeChat(whisper, 'channel'), null);
});
test('protocol-4 auth, dedupe, seq jumps, explicit gap replay, reconnect and stop', async () => {
  const commands = []; let connections = 0, active;
  const server = http.createServer((req, res) => { res.setHeader('content-type', 'application/json'); res.end(JSON.stringify({ streams: [{ streamerId: 'channel', state: 'entered' }] })); });
  const wss = new WebSocketServer({ server, path: '/v1/ws' });
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  wss.on('connection', (ws, req) => {
    assert.equal(req.headers['x-api-key'], 'test-secret'); connections++; active = ws;
    ws.send(JSON.stringify({ type: 'hello', protocol: 4, currentSeq: connections === 1 ? 20 : 29 }));
    ws.on('message', raw => {
      const m = JSON.parse(raw); commands.push(m);
      if (m.action === 'subscribe') {
        ws.send(JSON.stringify({ type: 'subscribed', currentSeq: connections === 1 ? 20 : 29 }));
        if (connections === 1) { ws.send(JSON.stringify(event(22))); ws.send(JSON.stringify(event(22))); ws.send(JSON.stringify(event(29))); ws.send(JSON.stringify({ type: 'gap', fromSeq: 23, toSeq: 28 })); }
      } else if (m.action === 'resume') { ws.send(JSON.stringify(event(25))); ws.send(JSON.stringify(event(29))); }
      else if (m.action === 'ping') ws.send(JSON.stringify({ type: 'pong' }));
    });
  });
  const bridge = new CoreBridge({ retryBase: 30, retryMax: 60, pollMs: 100, heartbeatMs: 100 }); const chats = [];
  bridge.on('chat', e => chats.push(e));
  try {
    bridge.start({ coreUrl: `ws://127.0.0.1:${server.address().port}/v1/ws`, streamerId: 'channel', apiKey: 'test-secret' });
    await waitFor(() => chats.length === 3);
    assert.deepEqual(chats.map(c => c.id), ['event-22', 'event-29', 'event-25']);
    assert.ok(commands.some(m => m.action === 'resume' && m.fromSeq === 22));
    assert.equal(commands.filter(m => m.action === 'resume').length, 1, 'numeric seq jumps alone must not trigger resume');
    active.close(); await waitFor(() => connections === 2); await waitFor(() => commands.some(m => m.action === 'resume' && m.fromSeq === 29));
    assert.equal(chats.length, 3, 'replayed event identity must not appear twice');
    bridge.stop(); const before = connections; await delay(100); assert.equal(connections, before);
  } finally { bridge.stop(); for (const ws of wss.clients) ws.terminate(); await new Promise(r => wss.close(r)); await new Promise(r => server.close(r)); }
});
