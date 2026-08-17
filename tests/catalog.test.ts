import test from'node:test';import assert from'node:assert/strict';import{EVENT_CATALOG,eventDescriptor}from'../src/protocol/catalog.js';
test('catalog includes rich SOOP events',()=>{assert.ok(EVENT_CATALOG.length>=90);assert.equal(eventDescriptor(121).name,'MISSION');assert.equal(eventDescriptor(105).name,'VIDEO_BALLOON');assert.equal(eventDescriptor(999).category,'unknown')});
