import test from'node:test';import assert from'node:assert/strict';import{secureTokenEqual}from'../src/server/auth.js';
test('API key comparison accepts exact secret only',()=>{assert.equal(secureTokenEqual('abc','abc'),true);assert.equal(secureTokenEqual('abd','abc'),false);assert.equal(secureTokenEqual(undefined,'abc'),false)});
test('API key comparison is open only when no key is configured',()=>{assert.equal(secureTokenEqual(undefined,undefined),true);assert.equal(secureTokenEqual('anything',undefined),true)});
