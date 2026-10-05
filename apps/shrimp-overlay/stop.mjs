const port = Number(process.env.SHRIMP_PORT || 17840);
const url = `http://127.0.0.1:${port}`;
try {
  const state = await fetch(url + '/api/state', { signal: AbortSignal.timeout(1500) }).then(r => r.json());
  if (state.service !== 'soop-shrimp-overlay') throw new Error('다른 프로그램입니다.');
  const response = await fetch(url + '/api/shutdown', { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Shrimp-Token': state.token }, body: '{}' });
  if (!response.ok) throw new Error('종료 요청 실패');
  console.log('새우 채팅마을과 내장 코어를 종료합니다.');
} catch { console.log('실행 중인 새우 채팅마을을 찾지 못했습니다. 실행 창에서 Ctrl+C로 종료할 수도 있습니다.'); }
