import { existsSync, statSync } from 'node:fs';
import { resolve } from 'node:path';

const requiredFiles = [
  'src/index.ts',
  'src/config.ts',
  'src/core/unified-service.ts',
  'src/core/broadcast-generation.ts',
  'src/core/broadcast-identity.ts',
  'src/core/snapshot-validation.ts',
  'src/core/native-chat.ts',
  'src/core/adaptive-reliability.ts',
  'src/core/protocol-drift.ts',
  'src/core/reconnect-policy.ts',
  'src/core/deduplicator.ts',
  'src/core/session-token.ts',
  'src/protocol/catalog.ts',
  'src/protocol/handshake.ts',
  'src/http/normalize.ts',
  'src/protocol/fixture-replay.ts',
  'src/providers/java-sidecar-provider.ts',
  'src/server/api-server.ts',
  'src/server/auth.ts',
  'src/server/errors.ts',
  'src/server/ws-hub.ts',
  'tests/packet.test.ts',
  'tests/normalize.test.ts',
  'tests/http-normalization.test.ts',
  'tests/broadcast-generation.test.ts',
  'tests/broadcast-identity.test.ts',
  'tests/handshake.test.ts',
  'tests/decoder-127.test.ts',
  'tests/mission-decoder.test.ts',
  'tests/ws-filter-compat.test.ts',
  'tests/snapshot-validation.test.ts',
  'tests/reliability.test.ts',
  'tests/drift.test.ts',
  'tests/reconnect-policy.test.ts',
  'tests/fixture-replay.test.ts',
  'tests/auth-token.test.ts',
  'tests/security-source.test.ts',
  'tests/repository-integrity.test.ts',
  'scripts/smoke.ts',
  'scripts/soak.ts',
  'docs/API.md',
  'docs/ACCURACY.md',
  'docs/ARCHITECTURE.md',
  'docs/BENCHMARK_SOOPAPI.md',
  'VALIDATION.md',
  'VALIDATION_REPORT.txt',
  'java-sidecar/build.gradle',
  'java-sidecar/src/main/java/io/soop/unified/sidecar/SidecarServer.java',
  '.github/workflows/ci.yml',
  '.github/workflows/smoke.yml',
  '.github/workflows/soak.yml',
  'PUSH_TO_GITHUB.bat'
];

const requiredDirs = ['src', 'tests', 'scripts', 'docs', 'java-sidecar', '.github/workflows'];
const missing = [];
for (const dir of requiredDirs) {
  const p = resolve(dir);
  if (!existsSync(p) || !statSync(p).isDirectory()) missing.push(`${dir}/`);
}
for (const file of requiredFiles) {
  const p = resolve(file);
  if (!existsSync(p) || !statSync(p).isFile()) missing.push(file);
}

if (missing.length) {
  console.error('Repository integrity check FAILED. Missing required project paths:');
  for (const item of missing) console.error(` - ${item}`);
  console.error('\nDo not upload only root files. Push the complete repository with git add .');
  process.exit(1);
}
console.log(`Repository integrity check passed (${requiredDirs.length} directories, ${requiredFiles.length} critical files).`);
