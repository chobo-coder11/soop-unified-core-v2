import test from 'node:test';
import assert from 'node:assert/strict';
import { CHARACTERS, renderResolution, textureResolution } from '../public/characters.mjs';
import { DEFAULTS, normalizeSettings } from '../lib/settings.mjs';
import { IDLE_ACTIONS, ACTION_MS, idleMotion, visualMotion } from '../public/motion.mjs';
test('every selectable character and performance control validates with bounded texture sizes',()=>{
 assert.equal(CHARACTERS.length,13); assert.equal(new Set(CHARACTERS.map(c=>c.id)).size,13);
 for(const c of CHARACTERS) assert.equal(normalizeSettings({character:c.id}).character,c.id);
 assert.throws(()=>normalizeSettings({character:'missing'}));
 assert.equal(normalizeSettings({characterBrightness:140}).characterBrightness,140);
 assert.throws(()=>normalizeSettings({characterBrightness:200})); assert.equal(DEFAULTS.characterBrightness,114);
 assert.equal(renderResolution('economy',3),1); assert.equal(textureResolution(240,'economy',3),160);
 assert.ok(textureResolution(240,'high',3)<=384);
});
test('all characters produce finite motions and frequency changes the walking interval',()=>{
 for(const c of CHARACTERS) for(const action of [...IDLE_ACTIONS,'walk']) for(const now of [0,350,ACTION_MS[action]||2000]) {
  const m=visualMotion({velocity:action==='walk'?28:0,phase:1,seed:0,motion:action,motionStarted:0},now,true,c.id);
  for(const key of ['bob','rotation','sx','sy','poseMix','walkMix']) assert.ok(Number.isFinite(m[key]),`${c.id}/${action}/${key}`);
 }
 const a={seed:1,nextMotionAt:0},b={...a};idleMotion(a,0,true,'duck',2);idleMotion(b,0,true,'duck',20);
 assert.ok(b.nextMotionAt>a.nextMotionAt);assert.equal(a.motion,b.motion);
});

test('all 13 mouth layers are bounded and animate independently of the body',async()=>{
 const { MOUTHS,mouthMix,mouthGeometry }=await import('../public/mouth.mjs');
 for(const c of CHARACTERS){assert.ok(MOUTHS[c.id]);const g=mouthGeometry(c,{naturalWidth:1200,naturalHeight:c.rows*300},{x:30,y:30,w:260,h:260},160);for(const rect of [g.source,g.target]){for(const v of Object.values(rect))assert.ok(Number.isFinite(v));assert.ok(rect.w>0&&rect.h>0);}assert.ok(g.target.w<160*.25);}
 const values=Array.from({length:100},(_,i)=>mouthMix(i*17,0,3));assert.ok(values.some(v=>v>.5));assert.ok(values.some(v=>v===0));assert.ok(values.every(v=>v>=0&&v<=1));assert.equal(mouthMix(300,0,0,false),0);
});
