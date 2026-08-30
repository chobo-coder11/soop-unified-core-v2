import test from'node:test';import assert from'node:assert/strict';import{buildPacket,parsePacket}from'../src/protocol/packet.js';import{decodePacket}from'../src/protocol/decoders.js';import{eventMatchesFilter}from'../src/server/ws-hub.js';

const mission=(type:'CHALLENGE_GIFT'|'GIFT')=>decodePacket('bach023',parsePacket(buildPacket(121,JSON.stringify({type,user_id:'u',user_nick:'n',gift_count:1}))));

test('specialized mission events still match legacy MISSION subscriptions',()=>{
 assert.equal(eventMatchesFilter(new Set(['MISSION']),mission('CHALLENGE_GIFT')),true);
 assert.equal(eventMatchesFilter(new Set(['MISSION']),mission('GIFT')),true);
});

test('specialized mission events match canonical type, opcode and donation category filters',()=>{
 const battle=mission('GIFT');
 assert.equal(eventMatchesFilter(new Set(['BATTLE_MISSION_GIFTED']),battle),true);
 assert.equal(eventMatchesFilter(new Set(['121']),battle),true);
 assert.equal(eventMatchesFilter(new Set(['donation']),battle),true);
 assert.equal(eventMatchesFilter(new Set(['CHAT_MESSAGE']),battle),false);
});
