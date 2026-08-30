import test from'node:test';import assert from'node:assert/strict';import{buildPacket,parsePacket}from'../src/protocol/packet.js';import{decodePacket}from'../src/protocol/decoders.js';

const decode=(payload:Record<string,unknown>)=>decodePacket('bach023',parsePacket(buildPacket(121,JSON.stringify(payload))));

test('opcode 121 CHALLENGE_GIFT is normalized as challenge mission donation even without field delimiters',()=>{
 const e=decode({type:'CHALLENGE_GIFT',chno:1105,is_relay:false,key:1657627,title:'디아블로 미션',user_id:'rookie3333',user_nick:'부울경',gift_count:9});
 assert.equal(e.code,121);assert.equal(e.type,'CHALLENGE_MISSION_GIFTED');assert.equal(e.category,'donation');assert.equal(e.supportLevel,'conditional');
 assert.deepEqual(e.user,{id:'rookie3333',nickname:'부울경'});assert.equal(e.donation?.kind,'challenge_mission');assert.equal(e.donation?.amount,9);
 assert.equal((e.payload.mission as any).rawType,'CHALLENGE_GIFT');assert.equal((e.payload.mission as any).chno,1105);assert.equal((e.payload.mission as any).key,1657627);
});

test('opcode 121 GIFT is normalized as battle mission donation from observed SOOP wire semantics',()=>{
 const e=decode({type:'GIFT',chno:484,is_relay:false,key:71873,title:'종수 리듬천국 미션',user_id:'rookie3333',user_nick:'부울경',gift_count:7});
 assert.equal(e.type,'BATTLE_MISSION_GIFTED');assert.equal(e.category,'donation');assert.deepEqual(e.user,{id:'rookie3333',nickname:'부울경'});assert.equal(e.donation?.kind,'battle_mission');assert.equal(e.donation?.amount,7);assert.equal((e.payload.mission as any).rawType,'GIFT');
});

test('opcode 121 accepts camelCase aliases without weakening mission type classification',()=>{
 const e=decode({type:'CHALLENGE_GIFT',userId:'user1',userNickname:'닉네임',count:3});
 assert.deepEqual(e.user,{id:'user1',nickname:'닉네임'});assert.equal(e.donation?.amount,3);
});

test('unknown opcode 121 mission subtype is preserved and never guessed as a donation',()=>{
 const e=decode({type:'MISSION_STARTED',key:99,title:'unknown lifecycle event'});
 assert.equal(e.type,'MISSION');assert.equal(e.category,'notification');assert.equal(e.donation,undefined);assert.equal(e.supportLevel,'conditional');assert.equal((e.payload.mission as any).rawType,'MISSION_STARTED');
});

test('malformed opcode 121 payload remains raw-only rather than becoming a false donation',()=>{
 const packet=parsePacket(buildPacket(121,'not-json'));const e=decodePacket('bach023',packet);
 assert.equal(e.type,'MISSION');assert.equal(e.category,'notification');assert.equal(e.donation,undefined);assert.equal(e.supportLevel,'raw-only');assert.equal((e.payload.mission as any).parseStatus,'invalid');
});

test('opcode 125 settlement JSON is parsed from delimiter-free payload',()=>{
 const packet=parsePacket(buildPacket(125,JSON.stringify({chno:484,fanOrder:1,list:[],uuid:'x'})));const e=decodePacket('bach023',packet);
 assert.equal((e.payload.data as any).chno,484);assert.equal((e.payload.data as any).uuid,'x');assert.equal(e.supportLevel,'conditional');
});
