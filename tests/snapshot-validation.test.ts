import test from'node:test';import assert from'node:assert/strict';import{validateChannelSnapshot,validateLiveSnapshot}from'../src/core/snapshot-validation.js';
test('impossible online snapshot without BNO is rejected before consensus',()=>{const x=validateLiveSnapshot({streamerId:'x',online:true,viewerCount:10},'x',true);assert.equal(x.status,'invalid');assert.ok(x.issues.includes('online_without_bno'))});
test('negative viewer counts are rejected',()=>{assert.equal(validateLiveSnapshot({streamerId:'x',online:false,viewerCount:-1}).status,'invalid');assert.equal(validateChannelSnapshot({streamerId:'x',currentViewerCount:-1}).status,'invalid')});
test('offline+BNO transition is warning rather than hard failure',()=>{const x=validateLiveSnapshot({streamerId:'x',online:false,bno:'123'});assert.equal(x.status,'warning')});

test('browser-style online evidence without BNO remains usable but warned',()=>{const x=validateLiveSnapshot({streamerId:'x',online:true},'x',false);assert.equal(x.status,'warning')});
