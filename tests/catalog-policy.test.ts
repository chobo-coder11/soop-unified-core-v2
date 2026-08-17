import test from'node:test';
import assert from'node:assert/strict';
import{eventDescriptor}from'../src/protocol/catalog.js';
test('privileged blacklist-like signal is raw-only and not presented as blacklist API',()=>{const e=eventDescriptor(52);assert.equal(e.supportLevel,'raw-only');assert.equal(e.name,'UNCLASSIFIED_MODERATION_52');assert.doesNotMatch(`${e.name} ${e.description}`.toLowerCase(),/blacklist/)});
