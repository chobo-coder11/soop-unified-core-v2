import test from 'node:test';
import assert from 'node:assert/strict';
import http from 'node:http';
import net from 'node:net';
import os from 'node:os';
import path from 'node:path';
import { mkdtemp, rm, readFile } from 'node:fs/promises';
import { spawn } from 'node:child_process';
import { setTimeout as delay } from 'node:timers/promises';
import { WebSocketServer } from '../vendor/ws/wrapper.mjs';
const root = new URL('../', import.meta.url);
async function freePort() { const s = net.createServer(); await new Promise(r => s.listen(0, '127.0.0.1', r)); const p = s.address().port; await new Promise(r => s.close(r)); return p; }
async function waitFor(fn) { const until = Date.now() + 4000; while (Date.now() < until) { if (await fn()) return; await delay(20); } throw new Error('condition timeout'); }
test('real server forwards authenticated core chat over SSE; saves settings, filters, clears and shuts down', async () => {
  const dir = await mkdtemp(path.join(os.tmpdir(), 'shrimp-test-'));
  const port = await freePort(); let proc, socket, output = '';
  const core = http.createServer((_req, res) => { res.setHeader('content-type', 'application/json'); res.end(JSON.stringify({ streams: [{ streamerId: 'channel', state: 'entered' }] })); });
  const wss = new WebSocketServer({ server: core, path: '/v1/ws' });
  await new Promise(r => core.listen(0, '127.0.0.1', r));
  wss.on('connection', (ws, req) => {
    assert.equal(req.headers['x-api-key'], 'private-key'); socket = ws;
    ws.send(JSON.stringify({ type: 'hello', protocol: 4, currentSeq: 0 }));
    ws.on('message', raw => { const m = JSON.parse(raw); if (m.action === 'subscribe') ws.send(JSON.stringify({ type: 'subscribed', currentSeq: 0 })); });
  });
  const url = `http://127.0.0.1:${port}`;
  const start = () => {
    proc = spawn(process.execPath, ['server.mjs'], { cwd: root, env: { ...process.env, SHRIMP_PORT: String(port), SHRIMP_DATA_DIR: dir }, stdio: ['ignore', 'pipe', 'pipe'] });
    proc.stdout.on('data', x => { output += x; }); proc.stderr.on('data', x => { output += x; });
  };
  let streamAbort, reader;
  try {
    start(); await waitFor(async () => { try { return (await fetch(url + '/api/state')).ok; } catch { return false; } });
    let state = await fetch(url + '/api/state').then(r => r.json());
    assert.equal(state.service, 'soop-shrimp-overlay');
    const post = (route, body = {}) => fetch(url + route, { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Shrimp-Token': state.token }, body: JSON.stringify(body) });
    assert.equal((await fetch(url + '/api/test', { method: 'POST', body: '{}' })).status, 403);
    assert.equal((await post('/api/settings', { mode: 'external', coreUrl: `ws://127.0.0.1:${core.address().port}/v1/ws`, apiKey: 'private-key', streamerId: 'channel', bannedWords: ['hide-me'] })).status, 200);
    assert.equal((await post('/api/connect')).status, 200); await waitFor(() => socket);
    streamAbort = new AbortController();
    const response = await fetch(url + '/events', { signal: streamAbort.signal }); reader = response.body.getReader();
    let received = '';
    const stream = (async () => { try { for (;;) { const { done, value } = await reader.read(); if (done) break; received += new TextDecoder().decode(value); } } catch {} })();
    await waitFor(() => received.includes('event: snapshot'));
    assert.ok(!received.includes('private-key'));
    const emit = (seq, message) => socket.send(JSON.stringify({ type: 'event', seq, event: { id: `chat-${seq}`, streamerId: 'channel', type: 'CHAT_MESSAGE', category: 'chat', user: { id: 'viewer', nickname: '부울경' }, message, receivedAt: new Date().toISOString() } }));
    emit(10, '새우말풍선'); await waitFor(() => received.includes('새우말풍선'));
    emit(11, 'hide-me'); await delay(60); assert.ok(!received.includes('"message":"hide-me"'));
    socket.send(JSON.stringify({ type: 'event', seq: 12, event: { streamerId: 'channel', type: 'USER_KICKED', category: 'moderation', user: { id: 'viewer' }, moderation: { action: 'kick' } } }));
    await waitFor(() => received.includes('event: hide-user'));
    const clean = await fetch(url + '/api/state').then(r => r.text()); assert.ok(!clean.includes('private-key'));
    assert.equal((await post('/api/clear')).status, 200); await waitFor(() => received.includes('event: clear'));
    streamAbort.abort(); await stream;
    const saved = JSON.parse(await readFile(path.join(dir, 'settings.json'), 'utf8')); assert.equal(saved.streamerId, 'channel');
    assert.equal((await post('/api/shutdown')).status, 200); await waitFor(() => proc.exitCode !== null);
    start(); await waitFor(async () => { try { return (await fetch(url + '/api/state')).ok; } catch { return false; } });
    state = await fetch(url + '/api/state').then(r => r.json()); assert.equal(state.settings.streamerId, 'channel'); assert.equal(state.settings.hasApiKey, true); assert.equal(state.running, false);
    await post('/api/shutdown'); await waitFor(() => proc.exitCode !== null);
  } catch (e) { e.message += '\n' + output; throw e; }
  finally { streamAbort?.abort(); proc?.kill(); for (const ws of wss.clients) ws.terminate(); await new Promise(r => wss.close(r)); await new Promise(r => core.close(r)); await rm(dir, { recursive: true, force: true }); }
});
