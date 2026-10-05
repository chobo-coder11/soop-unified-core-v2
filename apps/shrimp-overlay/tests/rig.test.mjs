import test from 'node:test';
import assert from 'node:assert/strict';
import { walkingRegion, jumpDetail } from '../public/rig.mjs';
import { CHARACTERS } from '../public/characters.mjs';
import { moveAgent } from '../public/motion.mjs';
test('locomotion leaves the central face stable and tail follows facing direction',()=>{
 for(const c of CHARACTERS)for(const dir of [-1,1]){
  const r=walkingRegion(c.profile,dir);
  assert.ok(r.x>=0&&r.y>=0&&r.x+r.w<=1&&r.y+r.h<=1);
  assert.ok(!(.5>=r.x&&.5<=r.x+r.w&&.52>=r.y&&.52<=r.y+r.h),c.id);
 }
 assert.equal(walkingRegion('swim',1).x,0);assert.ok(walkingRegion('swim',-1).x>.5);
});
test('each species gait depends on distance and remains equal at 30/60/120fps',()=>{
 for(const c of CHARACTERS){
  const runs=[30,60,120].map(fps=>{const a={x:200,dir:1,speed:1,phase:0,velocity:28};for(let i=0;i<fps;i++)moveAgent(a,i*1000/fps,1/fps,{width:1000,size:108,speed:28,character:c.id});return a;});
  for(const r of runs){assert.ok(Math.abs(r.x-228)<.00001);assert.ok(Math.abs(r.phase-runs[0].phase)<.00001);}
 }
});
test('jump prepares, leaves the ground, lands and recovers continuously',()=>{
 assert.ok(jumpDetail(.08).bob>0);assert.ok(jumpDetail(.47).bob< -23);
 for(const boundary of [.16,.78,1]){const before=jumpDetail(boundary-.000001),after=jumpDetail(boundary+.000001);for(const key of ['bob','sx','sy'])assert.ok(Math.abs(before[key]-after[key])<.001,key);}
 assert.deepEqual(jumpDetail(0),{bob:0,sx:1,sy:1});assert.ok(Math.abs(jumpDetail(1).bob)<1e-10);
});
