import { CHARACTERS } from '../public/characters.mjs';
export const DEFAULTS = Object.freeze({
  mode: 'builtin', coreUrl: 'ws://127.0.0.1:17841/v1/ws', apiKey: '', streamerId: '',
  character: 'shrimp', renderQuality: 'balanced', motionFrequency: 8, characterBrightness:114, emoteSize: 88, size: 108, speed: 28, maxCharacters: 24, maxBubbles: 5, ambientCharacters: 6,
  bubbleSeconds: 5, idleMinutes: 5, bottom: 20, fontSize: 19,
  bubbleMaxWidth: 360, bubbleMaxLines: 4, bubblePadding: 16, bubbleRadius: 20, bubbleBorderWidth: 2, bubbleGap: 10, bubbleOpacity: 100, nameFontSize: 18, namePaddingX: 12, namePaddingY: 5, nameRadius: 12, nameBorderWidth: 1, nameGap: 2, nameMaxWidth: 200, nameOpacity: 100,
  bubbleBg: '#fff9f4', bubbleTextColor: '#59434d', bubbleBorder: '#efc4b5', nameBg: '#fff3e9', nameTextColor: '#815b58', nameBorder: '#ecc4b3', namePosition: 'below', fontWeight: 'normal',
  showNames: 'speaking', palette: 'pastel', fontFamily: 'jua', extraMotion: true, blockedUsers: [], bannedWords: []
});
const ranges = { characterBrightness:[80,140], motionFrequency: [2,20], emoteSize: [32, 160], bubbleMaxWidth: [120, 600], bubbleMaxLines: [1, 6], bubblePadding: [8, 32], bubbleRadius: [0, 40], bubbleBorderWidth: [0, 6], bubbleGap: [4, 40], bubbleOpacity: [20, 100], nameFontSize: [10, 36], namePaddingX: [0, 24], namePaddingY: [0, 16], nameRadius: [0, 30], nameBorderWidth: [0, 6], nameGap: [0, 32], nameMaxWidth: [60, 400], nameOpacity: [20, 100], size: [56, 240], speed: [8, 90], maxCharacters: [4, 48], maxBubbles: [1, 8], ambientCharacters: [0, 12],
  bubbleSeconds: [2, 12], idleMinutes: [1, 60], bottom: [0, 240], fontSize: [12, 42] };
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
  if ('renderQuality' in input) { if (!['balanced','economy','high'].includes(input.renderQuality)) throw new Error('성능 설정을 확인해 주세요.'); result.renderQuality = input.renderQuality; }
  if ('character' in input) { if (!CHARACTERS.some(c => c.id === input.character)) throw new Error('캐릭터 종류를 확인해 주세요.'); result.character = input.character; }
  if ('palette' in input) { if (!['pastel', 'peach'].includes(input.palette)) throw new Error('색상 설정을 확인해 주세요.'); result.palette = input.palette; }
  if ('fontFamily' in input) { if (!['jua', 'gaegu', 'system'].includes(input.fontFamily)) throw new Error('글씨체를 확인해 주세요.'); result.fontFamily = input.fontFamily; }
  for (const key of ['bubbleBg', 'bubbleTextColor', 'bubbleBorder', 'nameBg', 'nameTextColor', 'nameBorder']) { if (key in input) { if (!/^#[0-9a-f]{6}$/i.test(input[key])) throw new Error('색상은 #RRGGBB 형식이어야 합니다.'); result[key] = input[key]; } }
  if ('namePosition' in input) { if (!['below', 'above'].includes(input.namePosition)) throw new Error('이름표 위치를 확인해 주세요.'); result.namePosition = input.namePosition; }
  if ('fontWeight' in input) { if (!['normal','bold'].includes(input.fontWeight)) throw new Error('글자 두께를 확인해 주세요.'); result.fontWeight = input.fontWeight; }
  if ('extraMotion' in input) { if (typeof input.extraMotion !== 'boolean') throw new Error('모션 설정을 확인해 주세요.'); result.extraMotion = input.extraMotion; }
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
