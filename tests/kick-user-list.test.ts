import test from 'node:test';
import assert from 'node:assert/strict';
import { decodePacket } from '../src/protocol/decoders.js';
import type { ParsedPacket } from '../src/protocol/packet.js';

const packet=(code:number,parts:string[]):ParsedPacket=>({code,parts,payload:'',raw:'fixture',declaredLength:0,actualLength:0,lengthValid:true});

test('KICK_USERLIST preserves grouped kicked-user evidence without pretending it is a new direct kick',()=>{
  const e=decodePacket('streamer',packet(77,['userA','닉A','2026-08-17T12:00:00.000Z','manager','매니저','flag','userB','닉B','2026-08-17T12:01:00.000Z','manager','매니저','flag']));
  const users=(e.payload as any).kickedUsers;
  assert.equal(e.type,'KICK_USERLIST');
  assert.equal(e.moderation,undefined);
  assert.equal(e.user,undefined);
  assert.equal(users.length,2);
  assert.deepEqual(users[0],{userId:'userA',userNickname:'닉A',time:'2026-08-17T12:00:00.000Z',orderUserId:'manager',orderUserNickname:'매니저',orderUserFlag:'flag'});
});

test('KICK_MSG_STATE remains a setting/status signal, not a personal kick',()=>{
  const e=decodePacket('streamer',packet(90,['123','1']));
  assert.equal(e.type,'KICK_MSG_STATE');
  assert.equal(e.moderation?.action,'kick_message_state');
  assert.equal(e.user,undefined);
});
