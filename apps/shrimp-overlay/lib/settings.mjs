export const DEFAULTS = Object.freeze({
  mode: 'builtin', coreUrl: 'ws://127.0.0.1:17841/v1/ws', apiKey: '', streamerId: '',
  size: 108, speed: 28, maxCharacters: 24, maxBubbles: 5, ambientCharacters: 6,
  bubbleSeconds: 5, idleMinutes: 5, bottom: 20, fontSize: 19,
  showNames: 'speaking', palette: 'pastel', blockedUsers: [], bannedWords: []
});
const ranges = { size: [56, 180], speed: [8, 90], maxCharacters: [4, 48], maxBubbles: [1, 8], ambientCharacters: [0, 12],
  bubbleSeconds: [2, 12], idleMinutes: [1, 60], bottom: [0, 240], fontSize: [14, 32] };
export function normalizeSettings(input, previous = DEFAULTS) {
  if (!input || typeof input !== 'object' || Array.isArray(input)) throw new Error('설정 형식이 올바르지 않습니다.');
  const result = { ...DEFAULTS, ...previous };
  for (const [key, [min, max]] of Object.entries(ranges)) {
    if (!(key in input)) continue;
    const value = Number(input[key]);
    if (!Number.isFinite(value) || value < min || value > max) throw new Error(`${key}: ${min}~${max} 범위로 입력해 주세요.`);
    result[key] = Math.round(value);
  }
  if ('mode' in input) { if (!['builtin', 'external'].includes(input.mode)) throw new Error('연결 모드를 확인해 주세요.'); result.mode = input.mode; }
  if ('coreUrl' in input) {
    const url = new URL(String(input.coreUrl));
    if (!['ws:', 'wss:'].includes(url.protocol) || url.username || url.password || url.search || url.hash || url.pathname !== '/v1/ws') throw new Error('코어 주소는 ws://또는 wss://로 시작하고 /v1/ws로 끝나야 합니다.');
    result.coreUrl = url.toString();
  }
  if ('streamerId' in input) {
    const id = String(input.streamerId).trim();
    if (id && !/^[A-Za-z0-9_-]{1,64}$/.test(id)) throw new Error('방송 ID를 입력해 주세요. 닉네임이나 전체 URL은 사용할 수 없습니다.');
    result.streamerId = id;
  }
  if ('apiKey' in input) { if (typeof input.apiKey !== 'string' || input.apiKey.length > 1024) throw new Error('API 키 형식을 확인해 주세요.'); result.apiKey = input.apiKey; }
  if ('showNames' in input) { if (!['speaking', 'always', 'never'].includes(input.showNames)) throw new Error('이름표 설정을 확인해 주세요.'); result.showNames = input.showNames; }
  if ('palette' in input) { if (!['pastel', 'peach'].includes(input.palette)) throw new Error('색상 설정을 확인해 주세요.'); result.palette = input.palette; }
  for (const key of ['blockedUsers', 'bannedWords']) {
    if (!(key in input)) continue;
    if (!Array.isArray(input[key]) || input[key].length > 200) throw new Error('숨김 목록은 최대 200개까지 가능합니다.');
    result[key] = [...new Set(input[key].map(x => String(x).trim().slice(0, 100)).filter(Boolean))];
  }
  return result;
}
export function publicSettings(settings) { const { apiKey, ...rest } = settings; return { ...rest, hasApiKey: Boolean(apiKey) }; }
export function filtered(chat, settings) {
  return settings.blockedUsers.some(x => x.toLowerCase() === chat.userId.toLowerCase()) ||
    settings.bannedWords.some(x => chat.message.toLowerCase().includes(x.toLowerCase()));
}
