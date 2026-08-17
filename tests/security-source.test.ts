import test from'node:test';import assert from'node:assert/strict';import{readFileSync,readdirSync,statSync}from'node:fs';import{join}from'node:path';
const files=(dir:string):string[]=>readdirSync(dir).flatMap(n=>{const p=join(dir,n);return statSync(p).isDirectory()?files(p):[p]});
test('source has no hard-coded TLS verification disable',()=>{for(const p of files('src'))assert.equal(/rejectUnauthorized\s*:\s*false/.test(readFileSync(p,'utf8')),false,`unsafe TLS default in ${p}`)});
test('auth session listing exposes reference rather than bearer token',()=>{const s=readFileSync('src/core/auth-sessions.ts','utf8');const list=s.slice(s.indexOf('list(){'),s.indexOf('private async cleanup'));assert.match(list,/sessionRef/);assert.doesNotMatch(list,/sessionId/)});
test('write session storage is hash-only',()=>{const s=readFileSync('src/core/auth-sessions.ts','utf8');assert.match(s,/tokenHash/);assert.doesNotMatch(s,/interface Session \{[^}]*sessionId/s)});
