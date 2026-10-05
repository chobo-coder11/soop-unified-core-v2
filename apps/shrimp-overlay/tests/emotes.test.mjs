import test from 'node:test';
import assert from 'node:assert/strict';
import { ogqEmote, safeEmoteUrl, EmoteLayer } from '../public/emotes.mjs';
import { normalizeChat } from '../lib/bridge.mjs';
import { decodePacket } from '../vendor/core/src/protocol/decoders.js';
import { buildPacket, parsePacket } from '../vendor/core/src/protocol/packet.js';
import { Village } from '../public/model.mjs';
import { DEFAULTS } from '../lib/settings.mjs';
const emote = ogqEmote({ groupId: '646e3b2843650', subId: '1' });
const event = { type: 'event', seq: 1, event: { id: 'ogq-1', streamerId: 'channel', type: 'OGQ_EMOTICON', message: '', receivedAt: new Date().toISOString(), payload: { groupId: '646e3b2843650', subId: '1', userInfo: 'viewer', color: '부울경' } } };
test('OGQ event survives normalization without text and retains sender identity', () => {
  const c = normalizeChat(event, 'channel');
  assert.equal(c.userId, 'viewer'); assert.equal(c.nickname, '부울경'); assert.equal(c.emoticon.kind, 'ogq');
  assert.ok(c.emoticon.sources[0].endsWith('/1.webp')); assert.ok(c.emoticon.sources[1].endsWith('/1.png'));
  const updatedCore = structuredClone(event); updatedCore.event.user = { id: 'native-viewer', nickname: '새우' };
  assert.equal(normalizeChat(updatedCore, 'channel').userId, 'native-viewer');
  assert.equal(normalizeChat(event, 'other'), null);
});
test('native OGQ decoder supplies sender ID and nickname without losing legacy payload', () => {
  const parts = ['123','', '646e3b2843650', '1', '1', 'viewer', '부울경', '0', '0'];
  const raw = buildPacket(109, '\x0c' + parts.join('\x0c'));
  const e = decodePacket('channel',parsePacket(raw));
  assert.deepEqual(e.user,{ id: 'viewer', nickname: '부울경' }); assert.equal(e.payload.userInfo,'viewer'); assert.equal(e.type,'OGQ_EMOTICON');
  assert.equal(normalizeChat({ type:'event',seq:1,event:e },'channel').emoticon.groupId,'646e3b2843650');
});
test('OGQ image URLs are restricted to known asset origins and safe item paths', () => {
  for (const url of ['http://127.0.0.1/x','https://evil.com/sticker/646e3b2843650/1.webp','javascript:alert(1)','https://ogqmarket.img.sooplive.com@evil.com/x','https://ogqmarket.img.sooplive.com/sticker/646e3b2843650/1.webp?key=private']) assert.equal(safeEmoteUrl(url),null);
  assert.equal(ogqEmote({ groupId:'../etc',subId:'1' }),null);
  assert.equal(ogqEmote({ groupId:'646e3b2843650',subId:'<img>' }),null);
  assert.ok(safeEmoteUrl(emote.sources[0]));
});
class FakeImage {
  constructor() { this.style = {}; this.writes = 0; this.removed = false; }
  set src(value) { this._src = value; this.writes++; }
  get src() { return this._src; }
  remove() { this.removed = true; }
}
test('animated image node and src stay stable throughout hundreds of render frames', () => {
  const images = [], root = { children:[], append(node) { this.children.push(node); } };
  const layer = new EmoteLayer(root, { makeImage:()=> { const i=new FakeImage(); images.push(i); return i; } });
  const asset = layer.asset(emote); images[0].onload(); assert.equal(asset.ready,true);
  for (let i=0;i<600;i++) assert.equal(layer.draw('viewer',emote,{x:100,y:50+i*.01,size:88,opacity:1}),true);
  assert.equal(root.children.length,1); assert.equal(root.children[0].writes,1);
  layer.retain(new Set()); assert.equal(root.children[0].removed,true); assert.equal(layer.nodes.size,0);
});
test('missing animated resource falls back to static PNG and reports final failure', () => {
  const images = []; const layer = new EmoteLayer({ append(){} }, { makeImage:()=> { const i=new FakeImage();images.push(i);return i; } });
  const a = layer.asset(emote); assert.ok(images[0].src.endsWith('.webp'));
  images[0].onerror(); assert.ok(images[0].src.endsWith('.png')); images[0].onload(); assert.ok(a.src.endsWith('.png'));
  const b = layer.asset(ogqEmote({groupId:'646e3b2843650',subId:'2'})); images[1].onerror();images[1].onerror();assert.equal(b.failed,true);assert.equal(b.ready,true);
});
test('image load waits in the queue and text-to-OGQ updates reserve new bubble geometry', () => {
  const v = new Village(DEFAULTS), c = normalizeChat(event,'channel');
  v.chat(c,100);v.step(100,0,()=>({pending:true})); assert.equal(v.bubbles.length,0);assert.equal(v.queue.size,1);
  v.step(200,0,()=>({w:120,h:120,lines:[]}));assert.equal(v.bubbles[0].h,120);
  v.chat({...c,message:'글자',emoticon:undefined},300);v.step(300,0,()=>({w:180,h:60,lines:['글자']}));assert.equal(v.bubbles[0].h,60);
});
