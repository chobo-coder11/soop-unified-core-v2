import type{OnlineState,ProviderName,ProviderObservation}from'../types.js';

const BASE:Record<ProviderName,number>={native:1,reindeer:.9,soopapi:.97,soop4j:.9,soopjs:.55};
interface Stat{samples:number;successEwma:number;disagreementEwma:number;latencyEwma:number}
const alpha=(samples:number)=>samples<5?.45:samples<20?.25:.12;
const clamp=(v:number,min:number,max:number)=>Math.max(min,Math.min(max,v));

export class AdaptiveReliability{
  private stats=new Map<ProviderName,Stat>();
  private get(name:ProviderName){let s=this.stats.get(name);if(!s){s={samples:0,successEwma:1,disagreementEwma:0,latencyEwma:0};this.stats.set(name,s)}return s}
  weight(name:ProviderName,observation?:ProviderObservation<unknown>){
    const s=this.get(name),base=BASE[name],success=.35+.65*s.successEwma,agreement=1-.55*s.disagreementEwma;
    const latency=s.latencyEwma||observation?.latencyMs||0,latencyFactor=1/(1+Math.max(0,latency-250)/6000);
    const staleFactor=observation?.stale?.7:1;
    return clamp(base*success*agreement*latencyFactor*staleFactor,base*.12,base);
  }
  record<T>(observations:ProviderObservation<T>[],onlineState?:OnlineState){
    for(const o of observations){
      const s=this.get(o.provider),a=alpha(s.samples);s.samples++;
      s.successEwma=s.successEwma*(1-a)+(o.ok?1:0)*a;
      if(o.ok)s.latencyEwma=s.latencyEwma? s.latencyEwma*(1-a)+o.latencyMs*a:o.latencyMs;
      if(onlineState&&onlineState!=='uncertain'&&o.ok&&o.value&&typeof (o.value as any).online==='boolean'){
        const disagrees=((o.value as any).online? 'online':'offline')!==onlineState;
        s.disagreementEwma=s.disagreementEwma*(1-a)+(disagrees?1:0)*a;
      }
    }
  }
  penalizeDisagreement(providers:ProviderName[],severity=1){
    for(const name of providers){const s=this.get(name),a=alpha(s.samples);s.disagreementEwma=s.disagreementEwma*(1-a)+Math.max(0,Math.min(1,severity))*a}
  }
  snapshot(){return([...this.stats.entries()] as Array<[ProviderName,Stat]>).map(([name,s])=>({name,baseWeight:BASE[name],dynamicWeight:this.weight(name),samples:s.samples,successRate:Number(s.successEwma.toFixed(4)),disagreementRate:Number(s.disagreementEwma.toFixed(4)),ewmaLatencyMs:Number(s.latencyEwma.toFixed(1))}))}
  healthFields(name:ProviderName){const s=this.get(name);return{dynamicWeight:Number(this.weight(name).toFixed(4)),successRate:Number(s.successEwma.toFixed(4)),disagreementRate:Number(s.disagreementEwma.toFixed(4)),ewmaLatencyMs:Number(s.latencyEwma.toFixed(1))}}
}
