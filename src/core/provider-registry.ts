import type{ChannelSnapshot,LiveSnapshot,ProviderHealth,ProviderObservation,UnifiedResult}from'../types.js';
import{NativeProvider}from'../providers/native-provider.js';
import{ReindeerProvider}from'../providers/reindeer-provider.js';
import{JavaSidecarProvider}from'../providers/java-sidecar-provider.js';
import{SoopJsProvider}from'../providers/soopjs-provider.js';
import{channelConsensus,liveConsensus}from'./consensus.js';
import{AdaptiveReliability}from'./adaptive-reliability.js';
import type{AppConfig}from'../config.js';
import type{Metrics}from'./metrics.js';

export class ProviderRegistry{
 readonly native:NativeProvider;readonly reindeer:ReindeerProvider;readonly java:JavaSidecarProvider;readonly soopjs:SoopJsProvider;readonly reliability=new AdaptiveReliability();
 constructor(private cfg:AppConfig,private metrics?:Metrics){this.native=new NativeProvider(cfg.providerTimeoutMs);this.reindeer=new ReindeerProvider(cfg.enableReindeerProvider);this.java=new JavaSidecarProvider(cfg.javaSidecarUrl,cfg.enableJavaSidecar,cfg.providerTimeoutMs);this.soopjs=new SoopJsProvider(cfg.enableSoopJsProvider)}
 private record<T>(kind:'live'|'channel',obs:ProviderObservation<T>[],result:UnifiedResult<T>){for(const o of obs){this.metrics?.incLabel('soop_provider_requests_total',{provider:o.provider,kind,result:o.ok?'success':'failure'});this.metrics?.observe('soop_provider_latency_ms',o.latencyMs,{provider:o.provider,kind});if(!o.ok)this.metrics?.incLabel('soop_provider_failures_total',{provider:o.provider,kind})}if(result.consensus.status==='uncertain')this.metrics?.incLabel('soop_consensus_uncertain_total',{kind});if(result.consensus.outlierProviders?.length)for(const p of result.consensus.outlierProviders)this.metrics?.incLabel('soop_consensus_outlier_total',{provider:p,kind})}
 async live(id:string):Promise<UnifiedResult<LiveSnapshot>>{const[n,r,j,s]=await Promise.all([this.native.live(id),this.reindeer.live(id),this.java.live(id),this.soopjs.live(id)]),obs=[n,r,...j,s];const result=liveConsensus(obs,(provider,o)=>this.reliability.weight(provider,o));this.reliability.record(obs,result.consensus.onlineState);if(result.consensus.outlierProviders?.length)this.reliability.penalizeDisagreement(result.consensus.outlierProviders,.7);this.record('live',obs,result);return result}
 async channel(id:string):Promise<UnifiedResult<ChannelSnapshot>>{const[n,r,j,s]=await Promise.all([this.native.channel(id),this.reindeer.channel(id),this.java.channel(id),this.soopjs.channel(id)]),obs=[n,r,...j,s];const result=channelConsensus(obs,(provider,o)=>this.reliability.weight(provider,o));this.reliability.record(obs);if(result.consensus.outlierProviders?.length)this.reliability.penalizeDisagreement(result.consensus.outlierProviders,.7);this.record('channel',obs,result);return result}
 health():ProviderHealth[]{return[this.native.breaker.snapshot(),this.reindeer.breaker.snapshot(),...this.java.health(),this.soopjs.breaker.snapshot()].map(h=>({...h,...this.reliability.healthFields(h.name)}))}
 reliabilitySnapshot(){return this.reliability.snapshot()}
 async close(){await this.soopjs.close()}
}
