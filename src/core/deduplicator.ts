import{createHash}from'node:crypto';import type{CanonicalEvent,ProviderName}from'../types.js';

const identity=(e:CanonicalEvent)=>e.providerEventId?`event:${e.providerEventId}`:JSON.stringify([
  e.streamerId,e.code,e.user?.id,e.target?.id,e.message,
  e.donation?.kind,e.donation?.amount,e.donation?.itemCode,e.moderation?.action,
]);
export const fingerprintEvent=(e:CanonicalEvent)=>createHash('sha1').update(identity(e)).digest('hex');

interface Occurrence{sources:Map<ProviderName,number>;createdAt:number;lastSeen:number;providerEventId?:string}

/**
 * Cross-provider mirror deduplicator with one-to-one occurrence matching.
 *
 * Identical events from the same provider are always treated as distinct occurrences.
 * A later event from another provider may match exactly one occurrence that has not yet
 * seen that provider. This prevents a native/reindeer duplicate pair from causing the
 * next legitimate repeated chat message to be dropped.
 */
export class EventDeduplicator{
  private occurrences=new Map<string,Occurrence[]>();
  private entryCount=0;
  constructor(private ttlMs=2500,private maxEntries=20000){}

  accept(e:CanonicalEvent){
    const now=Date.now();this.prune(now);const fp=fingerprintEvent(e);e.fingerprint=fp;
    const list=this.occurrences.get(fp)??[];

    // A provider-stable event ID is definitive: if the exact ID was already observed,
    // suppress it even when the same provider retransmits the packet.
    if(e.providerEventId){const exact=[...list].reverse().find(o=>o.providerEventId===e.providerEventId&&now-o.lastSeen<=this.ttlMs);if(exact){exact.sources.set(e.source,now);exact.lastSeen=now;return false}}
    const match=[...list].reverse().find(o=>now-o.lastSeen<=this.ttlMs&&!o.sources.has(e.source));
    if(match){match.sources.set(e.source,now);match.lastSeen=now;return false}

    const occurrence:Occurrence={sources:new Map([[e.source,now]]),createdAt:now,lastSeen:now,providerEventId:e.providerEventId};
    list.push(occurrence);this.occurrences.set(fp,list);this.entryCount++;return true;
  }

  private prune(now:number){
    if(this.entryCount<=this.maxEntries&&this.entryCount<1000)return;
    const cutoff=now-this.ttlMs;
    for(const[fp,list]of this.occurrences){
      const kept=list.filter(o=>o.lastSeen>=cutoff);this.entryCount-=list.length-kept.length;
      if(kept.length)this.occurrences.set(fp,kept);else this.occurrences.delete(fp);
    }
    if(this.entryCount<=this.maxEntries)return;
    // Hard cap fallback: drop oldest occurrence clusters first.
    const all=[...this.occurrences.entries()].flatMap(([fp,list])=>list.map(o=>({fp,o}))).sort((a,b)=>a.o.lastSeen-b.o.lastSeen);
    const remove=Math.max(0,this.entryCount-Math.floor(this.maxEntries*.8));
    const targets=new Set(all.slice(0,remove).map(x=>x.o));
    for(const[fp,list]of this.occurrences){const kept=list.filter(o=>!targets.has(o));this.entryCount-=list.length-kept.length;if(kept.length)this.occurrences.set(fp,kept);else this.occurrences.delete(fp)}
  }
}
