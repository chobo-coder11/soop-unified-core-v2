interface WindowEntry{start:number;count:number;lastSeen:number}
/**
 * Fixed-window limiter with bounded memory. Expired clients are pruned periodically and
 * the oldest entries are evicted if a large number of unique source addresses are seen.
 */
export class FixedWindowRateLimiter{
 private m=new Map<string,WindowEntry>();private calls=0;
 constructor(private perMinute:number,private maxEntries=20000){}
 allow(key:string){
  const now=Date.now(),minute=60000;this.calls++;if((this.calls&1023)===0)this.prune(now,minute);
  let x=this.m.get(key);if(!x||now-x.start>=minute){x={start:now,count:0,lastSeen:now};this.m.set(key,x)}x.count++;x.lastSeen=now;
  if(this.m.size>this.maxEntries)this.prune(now,minute,true);
  return{ok:x.count<=this.perMinute,remaining:Math.max(0,this.perMinute-x.count),resetMs:Math.max(0,minute-(now-x.start))}
 }
 size(){return this.m.size}
 private prune(now:number,windowMs:number,force=false){
  for(const[k,v]of this.m)if(now-v.lastSeen>=windowMs)this.m.delete(k);
  if(!force||this.m.size<=this.maxEntries)return;
  const target=Math.floor(this.maxEntries*.8),oldest=[...this.m.entries()].sort((a,b)=>a[1].lastSeen-b[1].lastSeen);
  for(let i=0;i<oldest.length-target;i++)this.m.delete(oldest[i][0]);
 }
}
