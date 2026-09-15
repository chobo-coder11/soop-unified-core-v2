import{EventEmitter}from'node:events';import{existsSync,mkdirSync,readFileSync,renameSync,writeFileSync}from'node:fs';import{dirname,resolve}from'node:path';import type{CanonicalEvent}from'../types.js';import{RouletteEngine,type RouletteState}from'./engine.js';

export class RouletteManager extends EventEmitter{
  readonly engine:RouletteEngine;private file:string;
  constructor(file=process.env.SOOP_ROULETTE_DATA||resolve(process.cwd(),'data','roulette.json')){super();this.file=file;this.engine=new RouletteEngine(process.env.SOOP_ROULETTE_RESET_ON_START==='true'?undefined:this.load());if(process.env.SOOP_ROULETTE_RESET_ON_START==='true')this.save()}
  snapshot(){return this.engine.state}
  setStreamer(id:string){this.engine.setStreamer(id);this.changed('settings')}
  createBox(v:{title?:string;code?:string;goal:number}){const box=this.engine.createBox(v);this.changed('box_created',{box});return box}
  setActiveBox(id:string){const box=this.engine.setActiveBox(id);this.changed('active_box',{box});return box}
  setOverlay(v:{x:number;y:number;scale:number}){const overlay=this.engine.setOverlay(v);this.changed('overlay',{overlay});return overlay}
  archiveBox(id:string){const box=this.engine.archiveBox(id);this.changed('box_archived',{box});return box}
  donation(e:CanonicalEvent){if(e.category!=='donation'||e.code!==18||!e.donation?.amount)return;const extra=e.donation.extra as{ttsData?:unknown}|undefined,message=e.message??(typeof extra?.ttsData==='string'?extra.ttsData:'');const result=this.engine.processDonation({eventId:e.id,userId:e.user?.id,nickname:e.user?.nickname,amount:e.donation.amount,message});if(result.accepted)this.changed(result.winner?'spin':'donation',{result,event:{nickname:e.user?.nickname,amount:e.donation.amount,message}})}
  testDonation(v:{nickname:string;amount:number;message?:string}){const result=this.engine.processDonation({eventId:`test-${Date.now()}-${Math.random()}`,userId:`test-${v.nickname}`,nickname:v.nickname,amount:v.amount,message:v.message});this.changed(result.accepted&&result.winner?'spin':'donation',{result,event:{nickname:v.nickname,amount:v.amount,message:v.message},test:true});return result}
  private changed(type:string,payload:Record<string,unknown>={}){this.save();this.emit('change',{type,at:new Date().toISOString(),state:this.snapshot(),...payload})}
  private load(){try{if(existsSync(this.file))return JSON.parse(readFileSync(this.file,'utf8')) as RouletteState}catch{}return undefined}
  private save(){mkdirSync(dirname(this.file),{recursive:true});const temp=`${this.file}.tmp`;writeFileSync(temp,JSON.stringify(this.snapshot(),null,2),'utf8');renameSync(temp,this.file)}
}
