import test from'node:test';import assert from'node:assert/strict';import{buildJoinPayload}from'../src/protocol/handshake.js';
const live:any={streamerId:'x',online:true,chatNo:'77',ftk:'FTK',bitrate:6000,selectedViewBps:8000,geoCountryCode:'KR'};const cookie:any={AuthTicket:'TICKET',_au:'UUID'};
test('legacy handshake preserves ticket/pver1 while using VIEWPRESET bitrate',()=>{const p=buildJoinPayload(live,cookie,'legacy-v1-ticket');assert.match(p,/view_bps/);assert.match(p,/8000/);assert.match(p,/TICKET/);assert.match(p,/pver/);assert.match(p,/1/)});
test('browser-v2 fallback mirrors observed pver2/auth_info NULL profile',()=>{const p=buildJoinPayload(live,cookie,'browser-v2-null');assert.match(p,/NULL/);assert.match(p,/pver/);assert.match(p,/2/)});
