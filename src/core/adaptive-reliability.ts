import type{ProviderName,ProviderObservation}from'../types.js';

const BASE:Record<ProviderName,number>={native:1,reindeer:.9,soopapi:.97,soop4j:.9,soopjs:.55};
type Signal='live'|'channel'|'realtime';
interface Stat{samples:number;successEwma:number;latencyEwma:number;verifiedErrorEwma:number}
const alpha=(samples:number)=>samples<5?.45:samples<20?.25:.12;
const clamp=(v:number,min:number,max:number)=>Math.max(min,Math.min(max,v));

/** Reliability learns transport success/latency per signal. It never treats consensus disagreement as ground truth. */
export class AdaptiveReliability{
 private stats=new Map<string,Stat>();
 private key(name:ProviderName,signal:Signal){return`${name}:${signal}`}
 private get(name:ProviderName,signal:Signal){const k=this.key(name,signal);let s=this.stats.get(k);if(!s){s={samples:0,successEwma:1,latencyEwma:0,verifiedErrorEwma:0};this.stats.set(k,s)}return s}
 weight(name:ProviderName,signal:Signal='live',observation?:ProviderObservation<unknown>){const s=this.get(name,signal),base=BASE[name],success=.35+.65*s.successEwma,verified=1-.65*s.verifiedErrorEwma,latency=s.latencyEwma||observation?.latencyMs||0,latencyFactor=1/(1+Math.max(0,latency-250)/6000),staleFactor=observation?.stale?.7:1;return clamp(base*success*verified*latencyFactor*staleFactor,base*.12,base)}
 record<T>(signal:Signal,observations:ProviderObservation<T>[]){for(const o of observations){const s=this.get(o.provider,signal),a=alpha(s.samples);s.samples++;s.successEwma=s.successEwma*(1-a)+(o.ok?1:0)*a;if(o.ok){s.latencyEwma=s.latencyEwma?s.latencyEwma*(1-a)+o.latencyMs*a:o.latencyMs;s.verifiedErrorEwma=s.verifiedErrorEwma*(1-a)}}}
 recordVerifiedError(name:ProviderName,signal:Signal,severity=1){const s=this.get(name,signal),a=alpha(s.samples);s.verifiedErrorEwma=s.verifiedErrorEwma*(1-a)+clamp(severity,0,1)*a}
 snapshot(){const out:any[]=[];for(const name of Object.keys(BASE) as ProviderName[])for(const signal of['live','channel','realtime']as Signal[]){const s=this.get(name,signal);out.push({name,signal,baseWeight:BASE[name],dynamicWeight:this.weight(name,signal),samples:s.samples,successRate:Number(s.successEwma.toFixed(4)),verifiedErrorRate:Number(s.verifiedErrorEwma.toFixed(4)),ewmaLatencyMs:Number(s.latencyEwma.toFixed(1))})}return out}
 healthFields(name:ProviderName){const live=this.get(name,'live'),channel=this.get(name,'channel'),samples=live.samples+channel.samples||1;return{dynamicWeight:Number(((this.weight(name,'live')+this.weight(name,'channel'))/2).toFixed(4)),successRate:Number(((live.successEwma*live.samples+channel.successEwma*channel.samples)/samples).toFixed(4)),disagreementRate:0,ewmaLatencyMs:Number(((live.latencyEwma*live.samples+channel.latencyEwma*channel.samples)/samples).toFixed(1))}}
}
