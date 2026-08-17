import test from'node:test';import assert from'node:assert/strict';import{loadConfig}from'../src/config.js';
const withEnv=(k:string,v:string|undefined,fn:()=>void)=>{const old=process.env[k];try{if(v===undefined)delete process.env[k];else process.env[k]=v;fn()}finally{if(old===undefined)delete process.env[k];else process.env[k]=old}};
test('numeric config rejects unsafe negative values',()=>withEnv('SOOP_RATE_LIMIT_PER_MINUTE','-5',()=>assert.equal(loadConfig().rateLimitPerMinute,1)));
test('numeric config bounds ratio to one',()=>withEnv('SOOP_DRIFT_UNKNOWN_RATIO','8',()=>assert.equal(loadConfig().driftUnknownRatio,1)));
test('invalid numeric config falls back',()=>withEnv('SOOP_PROVIDER_TIMEOUT_MS','not-a-number',()=>assert.equal(loadConfig().providerTimeoutMs,4500)));
