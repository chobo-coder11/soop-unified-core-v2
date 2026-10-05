import test from 'node:test';import assert from 'node:assert/strict';
import { Village } from '../public/model.mjs';import { DEFAULTS,normalizeSettings } from '../lib/settings.mjs';
import { ReplayGuard,graphemes,borderWidth,placeName } from '../public/layout.mjs';
import { PRESETS } from '../public/presets.mjs';import { speechPattern,mouthMix } from '../public/mouth.mjs';
import { EmoteLayer,ogqEmote } from '../public/emotes.mjs';
const chat=(id,message='안녕')=>({id:id+message,userId:id,nickname:id,message,streamerId:'room'});
const measure=c=>({w:Math.max(120,c.message.length*12),h:c.message.length>10?100:60,lines:[c.message]});
test('text replacement remeasures without restarting the bubble or colour-only changes',()=>{
 const v=new Village(DEFAULTS);v.chat(chat('a','짧음'),100);v.step(100,0,measure);const started=v.bubbles[0].started;
 v.chat(chat('a','길고 길고 길고 길고 길고 긴 문장'),300);v.step(300,0,measure);
 assert.equal(v.bubbles[0].h,100);assert.equal(v.bubbles[0].started,started);
 const bubble=v.bubbles[0];v.configure({characterBrightness:120,bubbleBg:'#ffffff'});assert.equal(v.bubbles[0],bubble);assert.equal(bubble.layoutDirty,false);
 v.configure({fontSize:24});assert.equal(v.bubbles[0].layoutDirty,true);v.step(400,0,measure);assert.equal(v.bubbles[0].started,started);
});
test('new OGQ waits for readiness while its previous content remains visible',()=>{
 const v=new Village(DEFAULTS),old={...chat('a'),emoticon:ogqEmote({groupId:'646e3b2843650',subId:'1'})},next={...old,id:'next',emoticon:ogqEmote({groupId:'646e3b2843650',subId:'2'})};
 v.chat(old,100);v.step(100,0,measure);v.chat(next,200);v.step(200,0,()=>({pending:true}));assert.equal(v.bubbles[0].chat.emoticon.subId,'1');
 v.step(1000,0,measure);assert.equal(v.bubbles[0].chat.emoticon.subId,'2');assert.ok(v.bubbles[0].until>=6000);assert.equal(v.bubbles[0].started,100);
});
test('full village keeps speaking viewers until their bubble ends and bounds newcomers',()=>{
 const v=new Village({...DEFAULTS,maxCharacters:4,maxBubbles:4,size:56});v.resize(3000,1000);
 for(let i=0;i<4;i++)v.chat(chat('a'+i),100);v.step(100,0,()=>({w:80,h:60,lines:[]}));assert.equal(v.bubbles.length,4);
 for(let i=0;i<200;i++)v.chat(chat('new'+i),200);assert.equal(v.agents.size,4);assert.equal(v.bubbles.length,4);assert.ok(v.entrants.size<=160);
 v.step(6000,0,measure);assert.ok([...v.agents.keys()].some(k=>k.includes('new')));assert.ok(v.agents.size<=4);
});
test('replay guard preserves recently seen messages but admits new IDs and sessions',()=>{
 const g=new ReplayGuard(),c=chat('a');assert.equal(g.accept(c,0),true);assert.equal(g.accept(c,1000),false);assert.equal(g.accept({...c,id:'new'},1000),true);assert.equal(g.accept(c,31000),true);g.clear();assert.equal(g.accept(c,31000),true);
});
test('zero border, grapheme wrapping and name collision decisions stay explicit',()=>{
 assert.equal(borderWidth(0),0);assert.equal(borderWidth(2),2);
 assert.deepEqual(graphemes('가👨‍👩‍👧‍👦👍🏽'),['가','👨‍👩‍👧‍👦','👍🏽']);
 const rect={x:10,y:10,w:100,h:20};assert.equal(placeName(rect,[rect]),null);assert.equal(placeName({...rect,x:120},[rect]).x,120);
});
test('mouth, chat reactions and idle actions are independent and speech ends or pauses',()=>{
 const s=normalizeSettings({mouthMotion:true,chatReactions:false,extraMotion:false});assert.equal(s.mouthMotion,true);assert.equal(s.chatReactions,false);assert.equal(s.extraMotion,false);
 const pattern=speechPattern('안녕! 다음 문장');assert.equal(mouthMix(500,0,3,true,{duration:0,pauses:[]}),0);assert.equal(mouthMix(300,0,3,true,pattern),0);assert.equal(mouthMix(10000,0,3,true,pattern),0);
 for(const p of Object.values(PRESETS)){assert.doesNotThrow(()=>normalizeSettings(p.values));assert.ok(!('streamerId' in p.values));assert.ok(!('blockedUsers' in p.values));}
});
test('failed OGQ retries after cooldown and stops after a bounded attempt count',()=>{
 let now=0;const images=[];class Img{set src(v){this._src=v;}get src(){return this._src;}}
 const l=new EmoteLayer({append(){}},{now:()=>now,retryMs:100,makeImage:()=>{const i=new Img();images.push(i);return i;}}),e=ogqEmote({groupId:'646e3b2843650',subId:'1'});
 let a=l.asset(e);images[0].onerror();images[0].onerror();assert.equal(a.failed,true);assert.equal(l.asset(e),a);
 now=101;a=l.asset(e);assert.equal(images.length,2);images[1].onerror();images[1].onerror();now=302;a=l.asset(e);images[2].onerror();images[2].onerror();now=10000;assert.equal(l.asset(e),a);assert.equal(images.length,3);
});
