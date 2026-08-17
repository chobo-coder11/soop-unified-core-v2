import test from'node:test';import assert from'node:assert/strict';import{RawPacketStore}from'../src/core/raw-store.js';import type{CanonicalEvent}from'../src/types.js';
const ev=(i:number):CanonicalEvent=>({id:String(i),streamerId:'s',code:999,type:'UNKNOWN',description:'u',category:'unknown',supportLevel:'raw-only',source:'native',receivedAt:new Date(Date.now()+i).toISOString(),payload:{},raw:`raw-${i}`});
test('unknown signature registry is bounded',()=>{const s=new RawPacketStore(10,10,10,20);for(let i=0;i<50;i++)s.push(ev(i));assert.ok(s.unknownSummary().length<=20)});
