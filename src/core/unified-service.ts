import type { AppConfig } from '../config.js';
import type { ChannelSnapshot, LiveSnapshot, UnifiedResult } from '../types.js';
import { ProviderRegistry } from './provider-registry.js';
import { RawPacketStore } from './raw-store.js';
import { Metrics } from './metrics.js';
import { ConnectionPool } from './connection-pool.js';
import { SingleFlightCache } from './single-flight-cache.js';
import { AuthSessionManager } from './auth-sessions.js';

export class UnifiedService {
 readonly providers:ProviderRegistry;readonly raw:RawPacketStore;readonly metrics:Metrics;readonly pool:ConnectionPool;readonly auth:AuthSessionManager;
 private liveCache:SingleFlightCache<UnifiedResult<LiveSnapshot>>;private channelCache:SingleFlightCache<UnifiedResult<ChannelSnapshot>>;
 constructor(readonly cfg:AppConfig){this.metrics=new Metrics();this.providers=new ProviderRegistry(cfg,this.metrics);this.raw=new RawPacketStore(cfg.rawBufferPerStream);this.pool=new ConnectionPool(cfg,this.providers,this.raw,this.metrics);this.auth=new AuthSessionManager(cfg,this.metrics);this.liveCache=new SingleFlightCache(cfg.liveCacheMs,2000,cfg.cacheStaleIfErrorMs);this.channelCache=new SingleFlightCache(cfg.channelCacheMs,2000,Math.max(cfg.cacheStaleIfErrorMs,cfg.channelCacheMs))}
 live(id:string,bypassCache=false){this.metrics.inc('soop_rest_live_requests_total');return this.liveCache.get(id,()=>this.providers.live(id),bypassCache)}
 channel(id:string,bypassCache=false){this.metrics.inc('soop_rest_channel_requests_total');return this.channelCache.get(id,()=>this.providers.channel(id),bypassCache)}
 async viewers(id:string,bypassCache=false){const x=await this.live(id,bypassCache);return{streamerId:id,viewerCount:x.data.viewerCount,online:x.data.online,onlineState:x.consensus.onlineState,confidence:x.confidence,source:x.source,corroboratedBy:x.corroboratedBy,consensus:x.consensus,observedAt:x.observedAt}}
 async state(id:string,bypassCache=false){const[live,channel]=await Promise.all([this.live(id,bypassCache),this.channel(id,bypassCache)]);return{streamerId:id,live,channel,connection:this.pool.list().find(x=>x.streamerId===id)}}
 diagnostics(){return{providers:this.providers.health(),reliability:this.providers.reliabilitySnapshot(),drift:this.pool.drift.snapshot(),incidents:this.raw.incidents(20),flightRecordings:this.raw.flightRecordings(5),anomalies:this.raw.recentAnomalies(50)}}
 async batch(kind:'live'|'channel'|'viewers'|'state',ids:string[],bypassCache=false){const unique=[...new Set(ids)],results:Record<string,unknown>={};let cursor=0;const worker=async()=>{while(true){const i=cursor++;if(i>=unique.length)return;const id=unique[i];try{results[id]=kind==='live'?await this.live(id,bypassCache):kind==='channel'?await this.channel(id,bypassCache):kind==='viewers'?await this.viewers(id,bypassCache):await this.state(id,bypassCache)}catch(e){results[id]={error:e instanceof Error?e.message:String(e)}}}};const count=Math.min(Math.max(1,this.cfg.batchConcurrency),unique.length||1);await Promise.all(Array.from({length:count},worker));return{kind,count:unique.length,results}}
 async close(){await this.auth.close();await this.pool.close();await this.providers.close()}
}
