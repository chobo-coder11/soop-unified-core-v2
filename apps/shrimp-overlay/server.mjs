import http from 'node:http';
import { readFile, writeFile, mkdir, rename, stat } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { randomBytes, randomUUID } from 'node:crypto';
import { fork, spawn } from 'node:child_process';
import { CoreBridge } from './lib/bridge.mjs';
import { DEFAULTS, normalizeSettings, publicSettings, filtered } from './lib/settings.mjs';

const ROOT = path.dirname(fileURLToPath(import.meta.url));
const DATA = process.env.SHRIMP_DATA_DIR ? path.resolve(process.env.SHRIMP_DATA_DIR) : path.join(ROOT, 'data');
const PORT = Number(process.env.SHRIMP_PORT || 17840);
const BUILTIN_PORT = Number(process.env.SHRIMP_CORE_PORT || 17841);
const TOKEN = randomBytes(24).toString('hex');
const bridge = new CoreBridge();
const clients = new Set();
let settings = { ...DEFAULTS }, running = false, demo = null, recent = [], total = 0, builtIn = null, shutting = false;
let saveQueue = Promise.resolve();
await mkdir(DATA, { recursive: true });
try { settings = normalizeSettings(JSON.parse(await readFile(path.join(DATA, 'settings.json'), 'utf8'))); }
catch (error) { if (error.code !== 'ENOENT') console.warn('저장된 설정을 읽을 수 없어 기본값으로 시작합니다.'); }

function broadcast(type, data) {
  const payload = `event: ${type}\ndata: ${JSON.stringify(data)}\n\n`;
  for (const res of clients) { if (res.writableLength > 262144) { res.destroy(); clients.delete(res); } else res.write(payload); }
}
function snapshot(admin = false) {
  return { service: 'soop-shrimp-overlay', version: '1.0.0', settings: publicSettings(settings), status: bridge.status, running, demo: Boolean(demo),
    total, recent: recent.filter(x => Date.now() - x.at < 20000), ...(admin ? { token: TOKEN, overlayUrl: `http://127.0.0.1:${PORT}/overlay` } : {}) };
}
function clearScene() { recent = []; broadcast('clear', {}); }
function ingest(chat) {
  if (filtered(chat, settings)) return;
  total++; recent.push(chat); if (recent.length > 100) recent.shift();
  broadcast('chat', chat);
}
bridge.on('chat', ingest);
bridge.on('status', status => broadcast('status', status));
bridge.on('notice', message => broadcast('notice', { message }));
bridge.on('moderation', e => {
  const action = e.moderation?.action;
  if (!['mute', 'kick', 'blind_kick', 'kick_and_cancel'].includes(action) || !e.user?.id) return;
  recent = recent.filter(x => x.userId !== e.user.id); broadcast('hide-user', { userId: e.user.id });
});
function stopDemo() { clearInterval(demo); demo = null; }
function stop() { stopDemo(); running = false; bridge.stop(); clearScene(); broadcast('mode', { demo: false, running }); }
function save() {
  const content = JSON.stringify(settings, null, 2);
  saveQueue = saveQueue.catch(() => {}).then(async () => {
    const target = path.join(DATA, 'settings.json'); await writeFile(target + '.tmp', content, { mode: 0o600 }); await rename(target + '.tmp', target);
  }); return saveQueue;
}
async function ensureCore() {
  if (builtIn && builtIn.exitCode === null && !builtIn.killed) return;
  // Do not assume another application on the chosen port is our own core.
  const net = await import('node:net');
  await new Promise((resolve, reject) => {
    const probe = net.createServer(); probe.once('error', () => reject(new Error(`내장 코어 포트 ${BUILTIN_PORT}가 사용 중입니다. 외부 코어 모드를 사용하거나 기존 프로그램을 종료해 주세요.`)));
    probe.listen(BUILTIN_PORT, '127.0.0.1', () => probe.close(resolve));
  });
  const entry = path.join(ROOT, 'vendor/core/src/index.js');
  try { await stat(entry); } catch { throw new Error('내장 코어가 없습니다. 배포 ZIP을 사용하거나 외부 코어 모드를 선택해 주세요.'); }
  builtIn = fork(entry, [], { cwd: ROOT, stdio: ['ignore', 'inherit', 'inherit', 'ipc'], env: {
    ...process.env, HOST: '127.0.0.1', PORT: String(BUILTIN_PORT), SOOP_API_KEY: '', SOOP_ENABLE_WRITE_API: 'false',
    SOOP_ENABLE_JAVA_SIDECAR: 'false', SOOP_ENABLE_REINDEER_PROVIDER: 'false', SOOP_ENABLE_REINDEER_EVENTS: 'false', SOOP_ENABLE_SOOPJS_PROVIDER: 'false'
  } });
  const child = builtIn;
  child.on('exit', () => { if (builtIn === child) builtIn = null; if (running && settings.mode === 'builtin' && !shutting) bridge.setStatus('error', '내장 코어가 종료됐습니다', '연결 버튼으로 다시 시작해 주세요.'); });
  child.on('error', () => { if (builtIn === child) builtIn = null; });
  for (let i = 0; i < 30; i++) {
    if (child.exitCode !== null) throw new Error('내장 코어 실행에 실패했습니다. 터미널 내용을 확인해 주세요.');
    try { const r = await fetch(`http://127.0.0.1:${BUILTIN_PORT}/livez`, { signal: AbortSignal.timeout(400) }); if (r.ok) return; } catch {}
    await new Promise(resolve => setTimeout(resolve, 100));
  }
  child.kill(); throw new Error('내장 코어 시작 시간이 초과됐습니다.');
}
async function connect() {
  if (!settings.streamerId) throw new Error('먼저 SOOP 방송 ID를 입력해 주세요.');
  stopDemo(); bridge.stop(false); running = false; clearScene();
  bridge.setStatus('connecting', settings.mode === 'builtin' ? '내장 코어 준비 중' : '외부 코어 연결 준비 중');
  try { if (settings.mode === 'builtin') await ensureCore(); }
  catch (error) { bridge.setStatus('error', '코어를 시작하지 못했습니다', error.message); broadcast('mode', { running: false, demo: false }); throw error; }
  running = true;
  bridge.start({ ...settings, coreUrl: settings.mode === 'builtin' ? `ws://127.0.0.1:${BUILTIN_PORT}/v1/ws` : settings.coreUrl,
    apiKey: settings.mode === 'builtin' ? '' : settings.apiKey });
  broadcast('mode', { running, demo: false });
}
function demoChat(index) {
  const names = ['부울경', '새우반장', '말랑새우', '고래상사팬', '핑크새우', '산책중', '오늘도출근', '새우친구'];
  const texts = ['안녕하세요! 오늘도 출근했어요 🦐', '내 새우가 말한다 ㅋㅋㅋ', '방송 잘 보고 있어요!', '다 같이 새우 산책 가자', '이렇게 멈추고 채팅하는 거예요', '말풍선 끝나면 다시 걸어요', '고래상사 화이팅!', '작고 말랑한 새우 등장'];
  const n = index % names.length;
  ingest({ id: randomUUID(), userId: `demo-${n}`, nickname: names[n], message: texts[n], at: Date.now(), source: 'demo', streamerId: 'demo' });
}
function json(res, code, data) { res.writeHead(code, { 'Content-Type': 'application/json; charset=utf-8', 'Cache-Control': 'no-store' }); res.end(JSON.stringify(data)); }
async function body(req) {
  let length = 0, chunks = [];
  for await (const chunk of req) { length += chunk.length; if (length > 16384) throw new Error('요청이 너무 큽니다.'); chunks.push(chunk); }
  try { return JSON.parse(Buffer.concat(chunks).toString() || '{}'); } catch { throw new Error('요청 형식이 올바르지 않습니다.'); }
}
let mutationQueue = Promise.resolve();
async function mutate(route, value) {
  if (route === '/api/settings') {
    const next = normalizeSettings(value, settings);
    const connectionChanged = ['mode', 'coreUrl', 'apiKey', 'streamerId'].some(key => next[key] !== settings[key]);
    settings = next; await save(); broadcast('settings', publicSettings(settings));
    recent = recent.filter(x => !filtered(x, settings));
    broadcast('filter', { blockedUsers: settings.blockedUsers, bannedWords: settings.bannedWords });
    if (running && connectionChanged) await connect();
  } else if (route === '/api/connect') await connect();
  else if (route === '/api/disconnect') stop();
  else if (route === '/api/demo') {
    stop(); bridge.setStatus('demo', '미리보기 재생 중 · 실제 방송 채팅 아님');
    let i = 0; demoChat(i++); demo = setInterval(() => demoChat(i++), 1800); broadcast('mode', { demo: true, running: false });
  } else if (route === '/api/test') {
    const nickname = String(value.nickname || '테스트새우').trim().slice(0, 48);
    const message = String(value.message || '').trim().slice(0, 300);
    if (!nickname || !message) throw new Error('닉네임과 테스트 채팅을 입력해 주세요.');
    ingest({ id: randomUUID(), userId: `test:${nickname}`, nickname, message, at: Date.now(), source: 'test', streamerId: 'test' });
  } else if (route === '/api/clear') clearScene();
  else if (route === '/api/shutdown') setTimeout(() => void shutdown(), 100);
  else throw new Error('없는 기능입니다.');
  return { ok: true, ...snapshot(true) };
}
const allowedHosts = new Set([`127.0.0.1:${PORT}`, `localhost:${PORT}`, `[::1]:${PORT}`]);
const staticRoutes = new Map([
  ['/', 'public/index.html'], ['/overlay', 'public/overlay.html'], ['/overlay.js', 'public/overlay.js'], ['/model.mjs', 'public/model.mjs'],
  ['/admin.js', 'public/admin.js'], ['/style.css', 'public/style.css'], ['/assets/shrimp.png', 'public/assets/shrimp.png']
]);
const mime = { '.html': 'text/html; charset=utf-8', '.js': 'text/javascript; charset=utf-8', '.mjs': 'text/javascript; charset=utf-8', '.css': 'text/css; charset=utf-8', '.png': 'image/png' };
const server = http.createServer(async (req, res) => {
  if (!allowedHosts.has(req.headers.host)) return json(res, 403, { error: '허용되지 않은 호스트입니다.' });
  const route = new URL(req.url, `http://127.0.0.1:${PORT}`).pathname;
  res.setHeader('X-Content-Type-Options', 'nosniff');
  res.setHeader('Referrer-Policy', 'no-referrer');
  res.setHeader('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self'; connect-src 'self'; frame-src 'self'; frame-ancestors 'self'; object-src 'none'; base-uri 'none'");
  if (req.method === 'GET' && route === '/api/state') return json(res, 200, snapshot(true));
  if (req.method === 'GET' && route === '/events') {
    if (clients.size >= 20) return json(res, 503, { error: '화면 연결 수가 너무 많습니다.' });
    res.writeHead(200, { 'Content-Type': 'text/event-stream', 'Cache-Control': 'no-cache', Connection: 'keep-alive' });
    res.write(`event: snapshot\ndata: ${JSON.stringify(snapshot())}\n\n`); clients.add(res);
    req.on('close', () => clients.delete(res)); return;
  }
  if (req.method === 'POST' && route.startsWith('/api/')) {
    const origin = req.headers.origin;
    if (req.headers['x-shrimp-token'] !== TOKEN || (origin && ![`http://127.0.0.1:${PORT}`, `http://localhost:${PORT}`, `http://[::1]:${PORT}`].includes(origin))) return json(res, 403, { error: '관리 화면에서 다시 시도해 주세요.' });
    try {
      const value = await body(req);
      const operation = mutationQueue.catch(() => {}).then(() => mutate(route, value)); mutationQueue = operation;
      return json(res, 200, await operation);
    } catch (error) { return json(res, 400, { error: error.message }); }
  }
  const file = staticRoutes.get(route);
  if (req.method !== 'GET' || !file) return json(res, 404, { error: '페이지를 찾을 수 없습니다.' });
  try { const data = await readFile(path.join(ROOT, file)); res.writeHead(200, { 'Content-Type': mime[path.extname(file)], 'Cache-Control': 'no-cache' }); res.end(data); }
  catch { json(res, 500, { error: '프로그램 파일을 읽을 수 없습니다. 압축을 완전히 풀어 주세요.' }); }
});
server.on('error', error => { console.error(`실행 실패: ${error.message}. 포트 ${PORT} 사용 여부를 확인해 주세요.`); process.exit(1); });
server.listen(PORT, '127.0.0.1', () => {
  console.log(`\n새우 채팅마을 v1.0.0\n관리 화면: http://127.0.0.1:${PORT}\n방송 오버레이: http://127.0.0.1:${PORT}/overlay\n종료: Ctrl+C 또는 stop.bat\n`);
  if (process.argv.includes('--open')) {
    const url = `http://127.0.0.1:${PORT}`;
    if (process.platform === 'win32') spawn('cmd', ['/c', 'start', '', url], { windowsHide: true, stdio: 'ignore' });
    else if (process.platform === 'darwin') spawn('open', [url], { stdio: 'ignore' });
  }
});
const keepalive = setInterval(() => { for (const res of clients) res.write(': heartbeat\n\n'); }, 15000);
async function shutdown() {
  if (shutting) return; shutting = true; stop(); clearInterval(keepalive);
  for (const res of clients) res.end(); clients.clear();
  if (builtIn) { const child = builtIn; child.kill(); setTimeout(() => { if (child.exitCode === null) child.kill('SIGKILL'); }, 1500).unref(); }
  server.close(() => process.exit(0)); setTimeout(() => process.exit(0), 2500).unref();
}
process.on('SIGINT', () => void shutdown()); process.on('SIGTERM', () => void shutdown());
process.on('message', message => { if (message === 'shutdown') void shutdown(); });
