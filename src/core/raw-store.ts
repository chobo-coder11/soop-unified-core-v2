import{createHash}from'node:crypto';import type{CanonicalEvent,ProtocolAnomaly,ProtocolDriftIncident,ProtocolIncidentBundle,RawPacketRecord}from'../types.js';
export class RawPacketStore{
 private byStream=new Map<string,RawPacketRecord[]>();private unknown=new Map<string,{count:number;firstSeen:string;lastSeen:string;code:number;type:string;streams:Set<string>}>();private anomalies:ProtocolAnomaly[]=[];private incidentLog:ProtocolDriftIncident[]=[];private bundles:ProtocolIncidentBundle[]=[];
 constructor(private limit=1000,private anomalyLimit=2000,private incidentLimit=100,private unknownLimit=5000){}
 push(e:CanonicalEvent){if(!e.raw)return;const sig=createHash('sha1').update(e.raw).digest('hex').slice(0,16),r={streamerId:e.streamerId,code:e.code,type:e.type,receivedAt:e.receivedAt,raw:e.raw,signature:sig},a=this.byStream.get(e.streamerId)??[];a.push(r);if(a.length>this.limit)a.splice(0,a.length-this.limit);this.byStream.set(e.streamerId,a);if(e.category==='unknown'){const k=`${e.code}:${sig}`,old=this.unknown.get(k);this.unknown.set(k,{count:(old?.count??0)+1,firstSeen:old?.firstSeen??e.receivedAt,lastSeen:e.receivedAt,code:e.code,type:e.type,streams:new Set([...(old?.streams??[]),e.streamerId])});if(this.unknown.size>this.unknownLimit){const oldest=[...this.unknown.entries()].sort((a,b)=>Date.parse(a[1].lastSeen)-Date.parse(b[1].lastSeen));for(let i=0;i<oldest.length-Math.floor(this.unknownLimit*.8);i++)this.unknown.delete(oldest[i][0])}}}
 pushAnomaly(a:ProtocolAnomaly){if(a.raw&&!a.signature)a.signature=createHash('sha1').update(a.raw).digest('hex').slice(0,16);this.anomalies.push(a);if(this.anomalies.length>this.anomalyLimit)this.anomalies.splice(0,this.anomalies.length-this.anomalyLimit)}
 recordIncident(i:ProtocolDriftIncident){
  this.incidentLog.push(i);if(this.incidentLog.length>this.incidentLimit)this.incidentLog.shift();
  const streamSet=new Set(i.sampleStreams),packets=i.sampleStreams.flatMap(id=>(this.byStream.get(id)??[]).slice(-25)).slice(-300),anomalies=this.anomalies.filter(a=>streamSet.has(a.streamerId)).slice(-100);
  this.bundles.push({incident:i,capturedAt:new Date().toISOString(),packets,anomalies});if(this.bundles.length>this.incidentLimit)this.bundles.shift();
 }
 recent(id:string,limit=100){return(this.byStream.get(id)??[]).slice(-Math.max(1,Math.min(limit,this.limit)))}
 recentAnomalies(limit=100){return this.anomalies.slice(-Math.max(1,Math.min(limit,this.anomalyLimit))).reverse()}
 incidents(limit=50){return this.incidentLog.slice(-Math.max(1,Math.min(limit,this.incidentLimit))).reverse()}
 flightRecordings(limit=10){return this.bundles.slice(-Math.max(1,Math.min(limit,this.incidentLimit))).reverse()}
 unknownSummary(){return[...this.unknown.entries()].map(([signature,v])=>({signature,count:v.count,firstSeen:v.firstSeen,lastSeen:v.lastSeen,code:v.code,type:v.type,affectedStreams:v.streams.size})).sort((a,b)=>b.count-a.count)}
}
