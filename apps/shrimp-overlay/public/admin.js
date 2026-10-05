const $ = id => document.getElementById(id);
let token = '', settings = {}, count = 0, recent = [], busy = false;
const numeric = ['size', 'speed', 'maxCharacters', 'maxBubbles', 'bubbleSeconds', 'fontSize', 'bottom', 'idleMinutes', 'ambientCharacters', 'bubbleMaxWidth', 'bubbleMaxLines', 'bubblePadding', 'bubbleRadius', 'bubbleBorderWidth', 'bubbleGap', 'bubbleOpacity', 'nameFontSize', 'namePaddingX', 'namePaddingY', 'nameRadius', 'nameBorderWidth', 'nameGap', 'nameMaxWidth', 'nameOpacity'];
function toast(text, error = false) { const el = $('toast'); el.textContent = text; el.className = error ? 'error' : ''; el.hidden = false; clearTimeout(toast.timer); toast.timer = setTimeout(() => { el.hidden = true; }, 4500); }
function showStatus(status) { const el = $('connection-pill'); el.dataset.state = status.state; el.querySelector('span').textContent = status.label; $('status-detail').textContent = status.detail || status.label; }
function ranges() { for (const key of numeric) { const unit = ({ maxCharacters: "마리", maxBubbles: "개", bubbleSeconds: "초", idleMinutes: "분", ambientCharacters: "마리", bubbleMaxLines: "줄", bubbleOpacity: "%", nameOpacity: "%", speed: "" })[key] ?? "px"; document.querySelector(`output[for="${key}"]`).textContent = $(key).value + unit; } }
function toggleMode() { const external = document.querySelector('input[name="mode"]:checked').value === 'external'; $('external-fields').hidden = !external; $('builtin-help').hidden = external; }
function populate(data) {
  settings = data.settings; token = data.token || token;
  for (const key of [...numeric, 'streamerId', 'coreUrl', 'showNames', 'palette', 'fontFamily', 'namePosition', 'fontWeight', 'bubbleBg', 'bubbleTextColor', 'bubbleBorder', 'nameBg', 'nameTextColor', 'nameBorder']) $(key).value = settings[key];
  $('extraMotion').checked = settings.extraMotion;
  document.querySelector(`input[name="mode"][value="${settings.mode}"]`).checked = true;
  $('apiKey').value = ''; $('apiKey').placeholder = settings.hasApiKey ? '키 저장됨 · 변경할 때만 입력' : '설정된 경우에만 입력'; $('clearKey').checked = false;
  $('blockedUsers').value = settings.blockedUsers.join('\n'); $('bannedWords').value = settings.bannedWords.join('\n');
  if (data.overlayUrl) $('overlayUrl').value = data.overlayUrl;
  count = data.total; $('message-count').textContent = count; showStatus(data.status); ranges(); toggleMode();
}
async function api(route, value = {}) {
  const res = await fetch(route, { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Shrimp-Token': token }, body: JSON.stringify(value) });
  const data = await res.json(); if (!res.ok) throw new Error(data.error || '처리하지 못했습니다.'); return data;
}
async function action(fn, success) {
  if (busy) return; busy = true;
  const buttons = [...document.querySelectorAll('button')]; buttons.forEach(b => { b.disabled = true; });
  try { await fn(); if (success) toast(success); } catch (e) { toast(e.message || '연결이 끊겼습니다. 프로그램을 확인해 주세요.', true); }
  finally { busy = false; buttons.forEach(b => { b.disabled = false; }); }
}
function log(chat) {
  recent.unshift(chat); recent = recent.slice(0, 12); renderLog();
}
function renderLog() {
  const box = $('recent-chat'); box.replaceChildren();
  if (!recent.length) { const p = document.createElement('p'); p.className = 'empty'; p.textContent = '아직 채팅이 없어요.'; box.append(p); return; }
  for (const chat of recent) {
    const row = document.createElement('div'); row.className = 'chat-row';
    const name = document.createElement('strong'); name.textContent = chat.nickname;
    const tag = document.createElement('span'); tag.className = 'chat-tag'; tag.textContent = chat.source === 'live' ? 'LIVE' : chat.source === 'demo' ? '미리보기' : '테스트';
    const message = document.createElement('p'); message.textContent = chat.message;
    row.append(name, tag, message); box.append(row);
  }
}
const state = await fetch('/api/state').then(r => { if (!r.ok) throw new Error('프로그램 상태를 읽지 못했습니다.'); return r.json(); }).catch(e => { toast(e.message, true); return null; });
if (state) { populate(state); recent = [...state.recent].reverse().slice(0, 12); renderLog(); }
document.querySelectorAll('input[name="mode"]').forEach(el => el.addEventListener('change', toggleMode));
numeric.forEach(key => $(key).addEventListener('input', ranges));
$('connection-form').addEventListener('submit', e => { e.preventDefault(); action(async () => {
  const value = { streamerId: $('streamerId').value, mode: document.querySelector('input[name="mode"]:checked').value, coreUrl: $('coreUrl').value };
  if ($('apiKey').value || $('clearKey').checked) value.apiKey = $('clearKey').checked ? '' : $('apiKey').value;
  await api('/api/disconnect'); const saved = await api('/api/settings', value); populate(saved); const result = await api('/api/connect'); showStatus(result.status);
}, '연결을 시작했어요. 방송 상태를 확인하고 있습니다.'); });
$('appearance-form').addEventListener('submit', e => { e.preventDefault(); action(async () => {
  const value = Object.fromEntries(numeric.map(key => [key, Number($(key).value)])); value.showNames = $('showNames').value; value.palette = $('palette').value;
  value.fontFamily = $('fontFamily').value; value.extraMotion = $('extraMotion').checked;
  for (const key of ['bubbleBg', 'bubbleTextColor', 'bubbleBorder', 'nameBg', 'nameTextColor', 'nameBorder', 'namePosition', 'fontWeight']) value[key] = $(key).value;
  const result = await api('/api/settings', value); settings = result.settings;
}, '마을 설정을 저장했어요.'); });
$('filter-form').addEventListener('submit', e => { e.preventDefault(); action(async () => {
  const value = { blockedUsers: $('blockedUsers').value.split('\n'), bannedWords: $('bannedWords').value.split('\n') };
  const result = await api('/api/settings', value); settings = result.settings;
}, '표시 설정을 저장했어요.'); });
$('test-form').addEventListener('submit', e => { e.preventDefault(); action(() => api('/api/test', { nickname: $('testNickname').value, message: $('testMessage').value })); });
$('disconnect').addEventListener('click', () => action(() => api('/api/disconnect'), '연결을 중지했어요.'));
$('demo').addEventListener('click', () => action(() => api('/api/demo'), '미리보기 채팅을 재생합니다. 방송 연결은 중지돼요.'));
$('clear').addEventListener('click', () => action(() => api('/api/clear'), '화면을 비웠어요.'));
$('copy').addEventListener('click', async () => { try { await navigator.clipboard.writeText($('overlayUrl').value); toast('오버레이 주소를 복사했어요.'); } catch { $('overlayUrl').select(); toast('주소를 선택했어요. Ctrl+C로 복사해 주세요.'); } });
const events = new EventSource('/events');
events.addEventListener('snapshot', e => { const d = JSON.parse(e.data); count = d.total; $('message-count').textContent = count; showStatus(d.status); recent = [...d.recent].reverse().slice(0, 12); renderLog(); });
events.addEventListener('chat', e => { const chat = JSON.parse(e.data); count++; $('message-count').textContent = count; log(chat); });
events.addEventListener('status', e => showStatus(JSON.parse(e.data)));
events.addEventListener('notice', e => toast(JSON.parse(e.data).message));
events.addEventListener('clear', () => { recent = []; renderLog(); });
events.addEventListener('hide-user', e => { const { userId } = JSON.parse(e.data); recent = recent.filter(c => c.userId !== userId); renderLog(); });
events.onerror = () => showStatus({ state: 'error', label: '프로그램 연결 끊김', detail: '프로그램이 켜져 있는지 확인해 주세요. 자동으로 다시 연결합니다.' });
