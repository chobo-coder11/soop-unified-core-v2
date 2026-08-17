import type{ChannelSnapshot,LiveSnapshot,ProviderHealth,ProviderName,ProviderObservation,UnifiedResult}from'../types.js';
import{NativeProvider}from'../providers/native-provider.js';
import{ReindeerProvider}from'../providers/reindeer-provider.js';
import{JavaSidecarProvider}from'../providers/java-sidecar-provider.js';
import{SoopJsProvider}from'../providers/soopjs-provider.js';
import{channelConsensus,liveConsensus}from'./consensus.js';
import{AdaptiveReliability}from'./adaptive-reliability.js';
import{PROVIDER_PROVENANCE}from'./provider-provenance.js';
import{withDeadline}from'./deadline.js';
import type{AppConfig}from'../config.js';
import type{Metrics}from'./metrics.js';

export class ProviderRegistry{
 readonly native:NativeProvider;readonly reindeer:ReindeerProvider;readonly java:JavaSidecarProvider;readonly soopjs:SoopJsProvider;readonly reliability=new AdaptiveReliability();
 constructor(private cfg:AppConfig,private metrics?:Metrics){this.native=new NativeProvider(cfg.providerTimeoutMs);this.reindeer=new ReindeerProvider(cfg.enableReindeerProvider,cfg.providerTimeoutMs);this.java=new JavaSidecarProvider(cfg.javaSidecarUrl,cfg.enableJavaSidecar,cfg.providerTimeoutMs);this.soopjs=new SoopJsProvider(cfg.enableSoopJsProvider,cfg.providerTimeoutMs)}
 private failure<T>(provider:ProviderName,error:unknown,latencyMs=this.cfg.providerTimeoutMs):ProviderObservation<T>{return{provider,ok:false,latencyMs,observedAt:new Date().toISOString(),error:error instanceof Error?error.message:String(error),provenance:PROVIDER_PROVENANCE[provider]}}
 private record<T>(kind:'live'|'channel',obs:ProviderObservation<T>[],result:UnifiedResult<T>){for(const o of obs){this.metrics?.incLabel('soop_provider_requests_total',{provider:o.provider,kind,result:o.ok?'success':'failure'});this.metrics?.observe('soop_provider_latency_ms',o.latencyMs,{provider:o.provider,kind});if(!o.ok)this.metrics?.incLabel('soop_provider_failures_total',{provider:o.provider,kind})}if(result.consensus.status==='uncertain')this.metrics?.incLabel('soop_consensus_uncertain_total',{kind});if(result.consensus.outlierProviders?.length)for(const p of result.consensus.outlierProviders)this.metrics?.incLabel('soop_consensus_outlier_total',{provider:p,kind})}
 private async collect<T>(kind:'live'|'channel',id:string):Promise<ProviderObservation<T>[]>{
  const calls=[
   ['native',withDeadline((this.native as any)[kind](id),this.cfg.providerTimeoutMs+100,`native ${kind}`)],
   ['reindeer',withDeadline((this.reindeer as any)[kind](id),this.cfg.providerTimeoutMs+100,`reindeer ${kind}`)],
   ['java',withDeadline((this.java as any)[kind](id),this.cfg.providerTimeoutMs+100,`java ${kind}`)],
   ['soopjs',withDeadline((this.soopjs as any)[kind](id),this.cfg.providerTimeoutMs+100,`soopjs ${kind}`)],
  ] as const;
  const settled=await Promise.allSettled(calls.map(x=>x[1]));const out:ProviderObservation<T>[]=[];
  for(let i=0;i<settled.length;i++){const name=calls[i][0],r=settled[i];if(r.status==='fulfilled'){if(name==='java')out.push(...(r.value as ProviderObservation<T>[]));else out.push(r.value as ProviderObservation<T>)}else if(name==='java'){out.push(this.failure('soopapi',r.reason),this.failure('soop4j',r.reason))}else out.push(this.failure(name as ProviderName,r.reason))}
  return out
 }
 async live(id:string):Promise<UnifiedResult<LiveSnapshot>>{const obs=await this.collect<LiveSnapshot>('live',id),result=liveConsensus(obs,(provider,o)=>this.reliability.weight(provider,'live',o));this.reliability.record('live',obs);this.record('live',obs,result);return result}
 async channel(id:string):Promise<UnifiedResult<ChannelSnapshot>>{const obs=await this.collect<ChannelSnapshot>('channel',id),result=channelConsensus(obs,(provider,o)=>this.reliability.weight(provider,'channel',o));this.reliability.record('channel',obs);this.record('channel',obs,result);return result}
 health():ProviderHealth[]{return[this.native.breaker.snapshot(),this.reindeer.breaker.snapshot(),...this.java.health(),this.soopjs.breaker.snapshot()].map(h=>({...h,...this.reliability.healthFields(h.name)}))}
 reliabilitySnapshot(){return this.reliability.snapshot()}
 async close(){await this.soopjs.close()}
}
