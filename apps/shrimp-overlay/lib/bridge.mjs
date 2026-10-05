import { ogqEmote } from '../public/emotes.mjs';
import { EventEmitter } from 'node:events';
import WebSocket from '../vendor/ws/wrapper.mjs';

export function normalizeChat(envelope, streamerId, now = Date.now()) {
  if (envelope?.type !== 'event' || !envelope.event) return null;
  const e = envelope.event;
  const isOgq = e.type === 'OGQ_EMOTICON';
  if (!['CHAT_MESSAGE','OGQ_EMOTICON'].includes(e.type) || e.streamerId !== streamerId) return null;
  const emoticon = isOgq ? ogqEmote(e.payload) : null;
  const message = typeof e.message === 'string' ? e.message.trim() : '';
  if (!message && !emoticon) return null;
  const sender = e.user || (isOgq ? { id: e.payload?.userInfo, nickname: e.payload?.color } : {});
  const at = Date.parse(e.receivedAt);
  // Replays recover brief interruptions, but must not flood the screen with old conversation.
  if (Number.isFinite(at) && now - at > 20000) return null;
  const userId = typeof sender.id === 'string' ? sender.id.trim() : '';
  const nickname = typeof sender.nickname === 'string' ? sender.nickname.trim() : '';
  if (!userId && !nickname) return null;
  return { id: String(e.id || `${streamerId}:${envelope.seq}`), userId: userId || `nickname:${nickname}`,
    nickname: (nickname || userId).slice(0, 48), message: (message || 'OGQ 이모티콘').slice(0, 300), ...(emoticon ? { emoticon } : {}),
    streamerId, at: now, source: 'live' };
}

export class CoreBridge extends EventEmitter {
  constructor({ retryBase = 1000, retryMax = 15000, pollMs = 5000, heartbeatMs = 20000 } = {}) {
    super(); this.options = { retryBase, retryMax, pollMs, heartbeatMs };
    this.status = { state: 'idle', label: '방송 ID를 입력해 주세요', detail: '' };
    this.seen = new Map(); this.cursor = null; this.generation = 0;
  }
  setStatus(state, label, detail = '') { this.status = { state, label, detail, at: Date.now() }; this.emit('status', this.status); }
  start(settings) {
    this.stop(false); this.settings = settings; this.stopped = false; this.attempt = 0;
    this.cursor = null; this.seen.clear(); this.connect(this.generation);
  }
  stop(notify = true) {
    this.stopped = true; this.generation = (this.generation || 0) + 1;
    clearTimeout(this.retry); clearInterval(this.heartbeat); clearInterval(this.poll);
    this.retry = this.heartbeat = this.poll = null;
    this.probeAbort?.abort(); this.probeAbort = null;
    const socket = this.socket; this.socket = null;
    if (socket) { socket.removeAllListeners(); socket.on('error', () => {}); socket.terminate(); }
    if (notify) this.setStatus('idle', '연결 중지');
  }
  connect(generation) {
    if (this.stopped || generation !== this.generation) return;
    this.setStatus('connecting', '코어 연결 중');
    const headers = this.settings.apiKey ? { 'X-API-Key': this.settings.apiKey } : {};
    const ws = new WebSocket(this.settings.coreUrl, { headers, handshakeTimeout: 5000, maxPayload: 262144, perMessageDeflate: false });
    this.socket = ws; let valid = () => !this.stopped && generation === this.generation && this.socket === ws;
    ws.on('error', () => { if (valid()) this.setStatus('retrying', '코어에 연결할 수 없어 다시 시도합니다', '코어 실행 여부, 주소, API 키를 확인해 주세요.'); });
    ws.on('unexpected-response', (_req, res) => {
      res.resume();
      if (!valid()) return;
      if ([401, 403].includes(res.statusCode)) { this.stop(false); this.setStatus('error', '코어 인증 실패', 'API 키를 확인한 뒤 연결 버튼을 눌러 주세요.'); }
      else ws.terminate();
    });
    ws.on('message', data => {
      if (!valid()) return;
      this.lastPacketAt = Date.now();
      let m; try { m = JSON.parse(data.toString()); } catch { return; }
      this.onMessage(m, ws);
    });
    ws.on('close', () => {
      if (!valid()) return;
      this.socket = null; clearInterval(this.heartbeat); clearInterval(this.poll); this.probeAbort?.abort();
      const delay = Math.min(this.options.retryMax, this.options.retryBase * 2 ** Math.min(this.attempt++, 5));
      this.setStatus('retrying', '연결이 끊겨 다시 연결합니다', `${Math.ceil(delay / 1000)}초 후 재시도`);
      this.retry = setTimeout(() => this.connect(generation), delay);
    });
  }
  send(ws, value) { if (ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify(value)); }
  onMessage(m, ws) {
    if (m.type === 'hello') {
      if (m.protocol !== 4) { this.stop(false); this.setStatus('error', '지원하지 않는 코어 프로토콜', 'SOOP Unified Core v2.6 / WS protocol 4를 사용해 주세요.'); return; }
      if (this.cursor !== null && m.currentSeq < this.cursor) { this.cursor = null; this.seen.clear(); }
      this.send(ws, { action: 'subscribe', streamers: [this.settings.streamerId], events: ['CHAT_MESSAGE', 'OGQ_EMOTICON', 'connection', 'moderation'] });
    } else if (m.type === 'subscribed') {
      this.attempt = 0;
      if (this.cursor !== null) this.send(ws, { action: 'resume', fromSeq: this.cursor });
      else this.cursor = m.currentSeq ?? 0;
      this.setStatus('waiting', '코어 구독 완료 · 방송 확인 중');
      clearInterval(this.heartbeat); clearInterval(this.poll);
      this.lastPacketAt = Date.now();
      this.heartbeat = setInterval(() => {
        if (Date.now() - this.lastPacketAt > this.options.heartbeatMs * 3) ws.terminate();
        else this.send(ws, { action: 'ping' });
      }, this.options.heartbeatMs);
      this.poll = setInterval(() => void this.probe(ws), this.options.pollMs);
      void this.probe(ws);
    } else if (m.type === 'gap') {
      this.emit('notice', '잠시 누락된 채팅을 복구하고 있습니다.');
      this.send(ws, { action: 'resume', fromSeq: Math.max(0, Number(m.fromSeq) - 1) });
    } else if (m.type === 'resume_unavailable') {
      this.cursor = m.currentSeq; this.emit('notice', '이전 채팅 복구 범위를 벗어났습니다. 새 채팅부터 표시합니다.');
    } else if (m.type === 'error') {
      this.stop(false); this.setStatus('error', '코어 구독 오류', String(m.error || '설정을 확인해 주세요.').slice(0, 120));
    } else if (m.type === 'event') {
      // Global sequence numbers can legitimately jump. Dedupe by event identity,
      // not <= cursor, so older events replayed after a gap are still accepted.
      if (Number.isSafeInteger(m.seq)) this.cursor = Math.max(this.cursor ?? 0, m.seq);
      const e = m.event;
      if (e?.streamerId !== this.settings.streamerId) return;
      if (e.category === 'moderation') { this.emit('moderation', e); return; }
      if (e.type === 'DISCONNECTED') { this.setStatus('waiting', '방송 채팅 재연결 중'); return; }
      const chat = normalizeChat(m, this.settings.streamerId);
      if (!chat || this.seen.has(chat.id)) return;
      this.seen.set(chat.id, Date.now());
      if (this.seen.size > 5000) this.seen.delete(this.seen.keys().next().value);
      this.setStatus('live', '실시간 채팅 수신 중'); this.emit('chat', chat);
    }
  }
  async probe(ws) {
    if (this.probeAbort || this.socket !== ws || ws.readyState !== WebSocket.OPEN) return;
    const abort = new AbortController(); this.probeAbort = abort;
    const timer = setTimeout(() => abort.abort(), 3000);
    try {
      const url = new URL(this.settings.coreUrl); url.protocol = url.protocol === 'wss:' ? 'https:' : 'http:'; url.pathname = '/v1/streams';
      const r = await fetch(url, { headers: this.settings.apiKey ? { 'X-API-Key': this.settings.apiKey } : {}, signal: abort.signal });
      if (!r.ok) return;
      const data = await r.json(); const stream = data.streams?.find(x => x.streamerId === this.settings.streamerId);
      if (this.socket !== ws || this.stopped) return;
      if (stream?.state === 'entered') this.setStatus('live', '방송 채팅 연결됨');
      else if (stream?.state === 'offline-wait') this.setStatus('waiting', '방송이 시작되기를 기다리는 중');
      else if (['blocked', 'protocol-error'].includes(stream?.state)) this.setStatus('error', '방송 채팅 연결 실패', '코어 진단 화면에서 방송 상태를 확인해 주세요.');
      else this.setStatus('waiting', '방송 채팅 연결 중');
    } catch { /* Keep the verified socket status if diagnostics is temporarily unavailable. */ }
    finally { clearTimeout(timer); if (this.probeAbort === abort) this.probeAbort = null; }
  }
}
