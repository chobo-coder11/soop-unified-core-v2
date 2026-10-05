import test from 'node:test';import assert from 'node:assert/strict';import {readFile} from 'node:fs/promises';
test('appearance controls remain unique, grouped, explained and advanced groups are collapsed',async()=>{
 const html=await readFile(new URL('../public/index.html',import.meta.url),'utf8'),script=await readFile(new URL('../public/admin.js',import.meta.url),'utf8');
 const ids=[...html.matchAll(/\bid="([^"]+)"/g)].map(m=>m[1]);assert.equal(ids.length,new Set(ids).size);
 for(const match of script.matchAll(/\$\('([^']+)'\)/g))assert.ok(ids.includes(match[1]),match[1]);
 const form=html.slice(html.indexOf('<form id="appearance-form">'),html.indexOf('</form>',html.indexOf('<form id="appearance-form">')));
 assert.equal([...form.matchAll(/data-preset=/g)].length,3);assert.equal([...form.matchAll(/<details class="setting-group"/g)].length,4);assert.ok(!form.includes('<details open'));
 for(const id of ['mouthMotion','chatReactions','extraMotion','save-appearance','reset-appearance','appearance-state'])assert.ok(ids.includes(id));
 assert.ok(form.includes('0이면 말풍선 테두리를 없애요.'));assert.ok(form.includes('저장해야 방송에 적용돼요.'));
});
