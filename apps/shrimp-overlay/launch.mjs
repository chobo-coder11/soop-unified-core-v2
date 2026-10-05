import { spawnSync, spawn } from 'node:child_process';
import { stat } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
const [major, minor] = process.versions.node.split('.').map(Number);
if (major < 22 || (major === 22 && minor < 13)) { console.error('Node.js 22.13 이상이 필요합니다. Node.js 24를 설치해 주세요.'); process.exit(1); }
const root = path.dirname(fileURLToPath(import.meta.url));
const port = Number(process.env.SHRIMP_PORT || 17840);
const url = `http://127.0.0.1:${port}`;
try {
  const response = await fetch(url + '/api/state', { signal: AbortSignal.timeout(700) });
  const state = await response.json();
  if (state.service === 'soop-shrimp-overlay') {
    console.log('새우 채팅마을이 이미 실행 중입니다. 관리 화면을 엽니다.');
    if (process.platform === 'win32') spawn('cmd', ['/c', 'start', '', url], { detached: true, stdio: 'ignore', windowsHide: true }).unref();
    process.exit(0);
  }
} catch {}
try { await stat(path.join(root, 'vendor/core/src/index.js')); }
catch {
  console.log('GitHub 소스에서 내장 코어를 준비합니다.');
  const result = spawnSync(process.execPath, [path.join(root, 'build-core.mjs')], { cwd: root, stdio: 'inherit' });
  if (result.status !== 0) { console.error('내장 코어 준비 실패. 배포 ZIP 또는 코어 저장소 전체를 사용해 주세요.'); process.exit(1); }
}
process.argv.push('--open'); await import('./server.mjs');
