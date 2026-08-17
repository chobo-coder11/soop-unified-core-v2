import test from'node:test';import assert from'node:assert/strict';import{FixedWindowRateLimiter}from'../src/server/rate-limit.js';
test('rate limiter enforces window quota',()=>{const r=new FixedWindowRateLimiter(2,100);assert.equal(r.allow('a').ok,true);assert.equal(r.allow('a').ok,true);assert.equal(r.allow('a').ok,false)});
test('rate limiter bounds unique-client memory',()=>{const r=new FixedWindowRateLimiter(10,100);for(let i=0;i<150;i++)r.allow(`ip-${i}`);assert.ok(r.size()<=100)});
