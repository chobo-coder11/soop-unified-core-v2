import test from'node:test';import assert from'node:assert/strict';
import{broadcastId,nullableBoolean,nullableNumber,normalizeViewPresets,selectViewBps}from'../src/http/normalize.js';

test('SOOP string booleans are parsed semantically, not by JS truthiness',()=>{
  assert.equal(nullableBoolean('0'),false);assert.equal(nullableBoolean('1'),true);
  assert.equal(nullableBoolean('false'),false);assert.equal(nullableBoolean('true'),true);
  assert.equal(nullableBoolean(''),undefined);assert.equal(nullableBoolean('unknown'),undefined);
});

test('blank numeric wire values stay unknown instead of becoming zero',()=>{
  assert.equal(nullableNumber(''),undefined);assert.equal(nullableNumber('  '),undefined);
  assert.equal(nullableNumber('0'),0);assert.equal(nullableNumber(0),0);assert.equal(nullableNumber('12.5'),12.5);
});

test('broadcast zero is treated as no active broadcast',()=>{assert.equal(broadcastId('0'),undefined);assert.equal(broadcastId('12345'),'12345')});

test('VIEWPRESET is normalized and selected separately from broadcast BPS',()=>{const p=normalizeViewPresets([{name:'original',label_resolution:'1920x1080',bps:'8000'}]);assert.equal(p?.[0].bps,8000);assert.equal(selectViewBps(p,6000),8000)});
test('fallback snapshot canonicalization fixes weak runtime types before consensus',async()=>{const {canonicalizeLiveSnapshot}=await import('../src/http/normalize.js');const x=canonicalizeLiveSnapshot({online:'1',bno:'123',passwordProtected:'0',viewerCount:'0'},'x');assert.equal(x.online,true);assert.equal(x.passwordProtected,false);assert.equal(x.viewerCount,0)});
