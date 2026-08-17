interface CacheEntry<T>{value:T;storedAt:number;expiresAt:number;staleUntil:number}
export interface CacheLoadResult<T>{value:T;freshness:{state:'fresh'|'stale';ageMs:number;staleReason?:string}}

/** TTL cache with request coalescing and explicit stale-if-error metadata. */
export class SingleFlightCache<T>{
 private cache=new Map<string,CacheEntry<T>>();private inflight=new Map<string,Promise<CacheLoadResult<T>>>();
 constructor(private ttlMs:number,private maxEntries=2000,private staleIfErrorMs=0){}
 async getWithMeta(key:string,loader:()=>Promise<T>,bypass=false):Promise<CacheLoadResult<T>>{
  const now=Date.now(),hit=this.cache.get(key);
  if(!bypass&&hit&&hit.expiresAt>now)return{value:hit.value,freshness:{state:'fresh',ageMs:Math.max(0,now-hit.storedAt)}};
  const active=this.inflight.get(key);if(active&&!bypass)return active;
  const promise=loader().then(value=>{this.set(key,value);return{value,freshness:{state:'fresh' as const,ageMs:0}}}).catch(error=>{
    if(!bypass&&hit&&hit.staleUntil>now)return{value:hit.value,freshness:{state:'stale' as const,ageMs:Math.max(0,now-hit.storedAt),staleReason:error instanceof Error?error.message:String(error)}};
    throw error
  }).finally(()=>this.inflight.delete(key));
  this.inflight.set(key,promise);return promise
 }
 async get(key:string,loader:()=>Promise<T>,bypass=false):Promise<T>{return(await this.getWithMeta(key,loader,bypass)).value}
 private set(key:string,value:T){const now=Date.now();this.cache.set(key,{value,storedAt:now,expiresAt:now+this.ttlMs,staleUntil:now+this.ttlMs+this.staleIfErrorMs});if(this.cache.size>this.maxEntries){const first=this.cache.keys().next().value as string|undefined;if(first)this.cache.delete(first)}}
 delete(key:string){this.cache.delete(key)}clear(){this.cache.clear();this.inflight.clear()}
}
