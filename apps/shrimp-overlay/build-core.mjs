import { stripTypeScriptTypes } from 'node:module';
import { readFile, writeFile, mkdir, readdir, copyFile } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
const app = path.dirname(fileURLToPath(import.meta.url));
const repo = path.resolve(app, '../..');
const destination = path.join(app, 'vendor/core');
async function compile(dir) {
  for (const entry of await readdir(path.join(repo, dir), { withFileTypes: true })) {
    const relative = path.join(dir, entry.name);
    if (entry.isDirectory()) { await compile(relative); continue; }
    if (!entry.name.endsWith('.ts') || entry.name.endsWith('.d.ts')) continue;
    const output = path.join(destination, relative.replace(/\.ts$/, '.js'));
    let source = await readFile(path.join(repo, relative), 'utf8');
    const wsPath = path.relative(path.dirname(output), path.join(app, 'vendor/ws/wrapper.mjs')).replaceAll('\\', '/');
    source = source.replace(/from\s*(['"])ws\1/g, `from '${wsPath}'`);
    const js = stripTypeScriptTypes(source, { mode: 'transform', sourceUrl: relative });
    await mkdir(path.dirname(output), { recursive: true });
    await writeFile(output, js + (relative.replaceAll('\\', '/') === 'src/index.ts' ? '\nprocess.on("disconnect", () => void shutdown("PARENT_DISCONNECT"));\n' : ''));
  }
}
await compile('src');
await writeFile(path.join(destination, 'package.json'), '{"type":"module","private":true}');
await copyFile(path.join(repo, 'LICENSE'), path.join(destination, 'LICENSE'));
await copyFile(path.join(repo, 'THIRD_PARTY_NOTICES.md'), path.join(destination, 'THIRD_PARTY_NOTICES.md'));
console.log('내장 SOOP 코어 준비 완료');
