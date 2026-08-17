import{EventEmitter}from'node:events';
import type{CanonicalEvent,ProtocolAnomaly}from'../types.js';
import{NativeChatConnection}from'./native-chat.js';
import{ReindeerChatMirror}from'./reindeer-chat.js';
import{EventDeduplicator}from'./deduplicator.js';
import{RawPacketStore}from'./raw-store.js';
import{Metrics}from'./metrics.js';
import{ProtocolDriftDetector}from'./protocol-drift.js';
import type{AppConfig}from'../config.js';
import{ProviderRegistry}from'./provider-registry.js';

export interface GapRecord{from:string;to?:string;reason?:string}
interface Entry{conn:NativeChatConnection;mirror?:ReindeerChatMirror;refs:number;manual:boolean;idle?:NodeJS.Timeout;createdAt:string;lastEventAt?:string;events:number;acceptedEvents:number;duplicates:number;possibleGaps:number;gaps:GapRecord[]}
export class ConnectionPool extends EventEmitter{
 private entries=new Map<string,Entry>();private dedup:EventDeduplicator;readonly drift:ProtocolDriftDetector;
 constructor(private cfg:AppConfig,private providers:ProviderRegistry,readonly rawStore:RawPacketStore,readonly metrics:Metrics){super();this.dedup=new EventDeduplicator(cfg.eventDedupTtlMs);this.drift=new ProtocolDriftDetector({windowMs:cfg.driftWindowMs,minUnknown:cfg.driftMinUnknown,minMalformed:cfg.driftMinMalformed,minStreams:cfg.driftMinStreams,unknownRatio:cfg.driftUnknownRatio,alertCooldownMs:cfg.driftAlertCooldownMs})}
 async acquire(id:string,manual=false){
  let e=this.entries.get(id);
  if(!e){
   const conn=new NativeChatConnection(id,this.providers.native.directHttp(),{maxBackoffMs:this.cfg.chatMaxBackoffMs,allowInsecureTls:this.cfg.allowInsecureTls,pingIntervalMs:this.cfg.chatPingIntervalMs,livenessTimeoutMs:this.cfg.chatLivenessTimeoutMs,joinTimeoutMs:this.cfg.chatJoinTimeoutMs,offlinePollMs:this.cfg.chatOfflinePollMs,timelineLimit:this.cfg.connectionTimelineLimit});
   const mirror=this.cfg.enableReindeerEvents?new ReindeerChatMirror(id,this.cfg.chatMaxBackoffMs):undefined;e={conn,mirror,refs:0,manual,createdAt:new Date().toISOString(),events:0,acceptedEvents:0,duplicates:0,possibleGaps:0,gaps:[]};this.entries.set(id,e);
   conn.on('event',(ev:CanonicalEvent)=>this.onEvent(e!,ev));conn.on('socket-error',()=>this.metrics.inc('soop_ws_native_errors_total'));conn.on('protocol-anomaly',(a:ProtocolAnomaly)=>this.onAnomaly(a));conn.on('reconnect-scheduled',(x:any)=>this.metrics.incLabel('soop_ws_reconnect_total',{source:'native',kind:String(x.kind??'unknown')}));
   void conn.start();
   if(mirror){mirror.on('event',(ev:CanonicalEvent)=>this.onEvent(e!,ev));mirror.on('protocol-anomaly',(a:ProtocolAnomaly)=>this.onAnomaly(a));mirror.on('error-state',()=>this.metrics.inc('soop_ws_reindeer_errors_total'));mirror.on('reconnect-scheduled',()=>this.metrics.incLabel('soop_ws_reconnect_total',{source:'reindeer',kind:'transient'}));void mirror.start()}
   this.metrics.inc('soop_connections_created_total');
  }
  if(e.idle){clearTimeout(e.idle);e.idle=undefined}e.refs++;if(manual)e.manual=true;this.updateGauge();return e.conn
 }
 release(id:string){const e=this.entries.get(id);if(!e)return;e.refs=Math.max(0,e.refs-1);if(e.refs===0&&!e.manual)e.idle=setTimeout(()=>void this.destroy(id),this.cfg.streamIdleTtlMs);this.updateGauge()}
 async pin(id:string){let e=this.entries.get(id);if(!e){await this.acquire(id,true);this.release(id)}else e.manual=true}
 async unpin(id:string){const e=this.entries.get(id);if(!e)return;e.manual=false;if(e.refs===0)e.idle=setTimeout(()=>void this.destroy(id),0)}
 private onEvent(entry:Entry,e:CanonicalEvent){entry.events++;entry.lastEventAt=e.receivedAt;if(e.source==='native'&&e.type==='DISCONNECTED'){entry.possibleGaps++;entry.gaps.push({from:e.receivedAt,reason:String(e.payload?.reason??'socket disconnected')});if(entry.gaps.length>20)entry.gaps.shift()}else if(e.source==='native'&&e.type==='RECONNECTED'){const open=[...entry.gaps].reverse().find(g=>!g.to);if(open)open.to=e.receivedAt;}this.rawStore.push(e);this.metrics.incLabel('soop_events_ingested_total',{type:e.type,source:e.source});if(!this.dedup.accept(e)){entry.duplicates++;this.metrics.incLabel('soop_events_deduplicated_total',{source:e.source});return}entry.acceptedEvents++;const incident=this.drift.observeEvent(e);if(incident){this.rawStore.recordIncident(incident);this.metrics.incLabel('soop_protocol_drift_incidents_total',{reason:incident.reason,severity:incident.severity});this.emit('drift-incident',incident)}this.metrics.incLabel('soop_events_total',{type:e.type,source:e.source});this.emit('event',e)}
 private onAnomaly(a:ProtocolAnomaly){this.rawStore.pushAnomaly(a);this.metrics.incLabel('soop_protocol_anomalies_total',{kind:a.kind,source:a.source});const incident=this.drift.observeAnomaly(a);if(incident){this.rawStore.recordIncident(incident);this.metrics.incLabel('soop_protocol_drift_incidents_total',{reason:incident.reason,severity:incident.severity});this.emit('drift-incident',incident)}}
 async destroy(id:string){const e=this.entries.get(id);if(!e)return;this.entries.delete(id);await Promise.all([e.conn.stop(),e.mirror?.stop()]);this.metrics.inc('soop_connections_destroyed_total');this.updateGauge()}
 list(){return[...this.entries.entries()].map(([streamerId,e])=>{const d=e.conn.diagnostics(),ageMs=e.lastEventAt?Date.now()-Date.parse(e.lastEventAt):undefined;const integrity=e.conn.state==='entered'?'healthy':e.conn.state==='reconnecting'||e.conn.state==='offline-wait'||e.conn.state==='connecting'||e.conn.state==='connected'?'degraded':e.conn.state==='blocked'||e.conn.state==='protocol-error'?'broken':'unknown';return{streamerId,state:e.conn.state,integrity,realtimeProviders:{native:e.conn.state,reindeer:e.mirror?.state??'disabled'},refs:e.refs,manual:e.manual,createdAt:e.createdAt,lastEventAt:e.lastEventAt,lastEventAgeMs:ageMs,events:e.events,acceptedEvents:e.acceptedEvents,duplicates:e.duplicates,possibleGaps:e.possibleGaps,recentGaps:[...e.gaps],diagnostics:d}})}
 private updateGauge(){this.metrics.set('soop_connections_active',this.entries.size)}
 async close(){await Promise.all([...this.entries.keys()].map(id=>this.destroy(id)))}
}
