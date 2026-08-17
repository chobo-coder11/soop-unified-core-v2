import test from'node:test';import assert from'node:assert/strict';import{withDeadline}from'../src/core/deadline.js';
test('deadline rejects a hung provider call',async()=>{await assert.rejects(()=>withDeadline(new Promise(()=>{}),20,'hung provider'),/hung provider timeout/)});
