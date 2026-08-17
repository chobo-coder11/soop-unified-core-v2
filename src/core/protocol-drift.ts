import{randomUUID}from'node:crypto';import type{CanonicalEvent,ProtocolAnomaly,ProtocolDriftIncident}from'../types.js';
interface TimedEvent{at:number;streamerId:string;unknown:boolean;code:number}
interface TimedAnomaly{at:number;anomaly:ProtocolAnomaly}
export interface DriftConfig{windowMs:number;minUnknown:number;minMalformed:number;minStreams:number;unknownRatio:number;alertCooldownMs:number}

export class ProtocolDriftDetector{
 private events:TimedEvent[]=[];private anomalies:TimedAnomaly[]=[];private incidents:ProtocolDriftIncident[]=[];private lastAlertAt=0;
 constructor(private cfg:DriftConfig,private maxEvents=100000,private maxAnomalies=20000){}
 observeEvent(e:CanonicalEvent){const at=Date.parse(e.receivedAt)||Date.now();this.events.push({at,streamerId:e.streamerId,unknown:e.category==='unknown',code:e.code});if(this.events.length>this.maxEvents)this.events.splice(0,this.events.length-this.maxEvents);this.prune(at);return this.evaluate(at)}
 observeAnomaly(anomaly:ProtocolAnomaly){const at=Date.parse(anomaly.receivedAt)||Date.now();this.anomalies.push({at,anomaly});if(this.anomalies.length>this.maxAnomalies)this.anomalies.splice(0,this.anomalies.length-this.maxAnomalies);this.prune(at);return this.evaluate(at)}
 private prune(now:number){const cutoff=now-this.cfg.windowMs;this.events=this.events.filter(x=>x.at>=cutoff);this.anomalies=this.anomalies.filter(x=>x.at>=cutoff)}
 private evaluate(now:number){
  if(now-this.lastAlertAt<this.cfg.alertCooldownMs)return undefined;
  const unknown=this.events.filter(x=>x.unknown),malformed=this.anomalies.filter(x=>['parse-error','length-mismatch'].includes(x.anomaly.kind));
  const streamIds=[...new Set([...unknown.map(x=>x.streamerId),...malformed.map(x=>x.anomaly.streamerId)])],ratio=this.events.length?unknown.length/this.events.length:0;
  let reason:ProtocolDriftIncident['reason']|undefined,severity:ProtocolDriftIncident['severity']='medium';
  if(unknown.length>=this.cfg.minUnknown&&streamIds.length>=this.cfg.minStreams&&ratio>=this.cfg.unknownRatio){reason='unknown-rate';severity=ratio>=Math.max(.2,this.cfg.unknownRatio*2)?'high':'medium'}
  else if(malformed.length>=this.cfg.minMalformed&&streamIds.length>=this.cfg.minStreams){reason='malformed-rate';severity=malformed.length>=this.cfg.minMalformed*2?'high':'medium'}
  if(!reason)return undefined;
  const incident:ProtocolDriftIncident={id:randomUUID(),startedAt:new Date(Math.max(0,now-this.cfg.windowMs)).toISOString(),detectedAt:new Date(now).toISOString(),severity,reason,windowMs:this.cfg.windowMs,totalEvents:this.events.length,unknownEvents:unknown.length,malformedPackets:malformed.length,affectedStreams:streamIds.length,unknownRatio:ratio,sampleCodes:[...new Set(unknown.map(x=>x.code))].slice(0,20),sampleSignatures:[...new Set(malformed.map(x=>x.anomaly.signature).filter((x):x is string=>Boolean(x)))].slice(0,20),sampleStreams:streamIds.slice(0,20)};
  this.incidents.push(incident);if(this.incidents.length>100)this.incidents.shift();this.lastAlertAt=now;return incident;
 }
 snapshot(){this.prune(Date.now());const unknown=this.events.filter(x=>x.unknown),malformed=this.anomalies.filter(x=>['parse-error','length-mismatch'].includes(x.anomaly.kind));return{windowMs:this.cfg.windowMs,totalEvents:this.events.length,unknownEvents:unknown.length,unknownRatio:this.events.length?unknown.length/this.events.length:0,malformedPackets:malformed.length,affectedStreams:new Set([...unknown.map(x=>x.streamerId),...malformed.map(x=>x.anomaly.streamerId)]).size,lastIncident:this.incidents.at(-1)}}
 listIncidents(){return[...this.incidents].reverse()}
}
