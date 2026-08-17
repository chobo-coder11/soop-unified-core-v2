interface CacheEntry<T>{value:T;expiresAt:number;staleUntil:number}
/** TTL cache with request coalescing and stale-if-error fallback. */
export class SingleFlightCache<T>{
 private cache=new Map<string,CacheEntry<T>>();private inflight=new Map<string,Promise<T>>();
 constructor(private ttlMs:number,private maxEntries=2000,private staleIfErrorMs=0){}
 async get(key:string,loader:()=>Promise<T>,bypass=false):Promise<T>{const now=Date.now(),hit=this.cache.get(key);if(!bypass&&hit&&hit.expiresAt>now)return hit.value;const active=this.inflight.get(key);if(active&&!bypass)return active;const promise=loader().then(value=>{this.set(key,value);return value}).catch(error=>{if(!bypass&&hit&&hit.staleUntil>now)return hit.value;throw error}).finally(()=>this.inflight.delete(key));this.inflight.set(key,promise);return promise}
 private set(key:string,value:T){const now=Date.now();this.cache.set(key,{value,expiresAt:now+this.ttlMs,staleUntil:now+this.ttlMs+this.staleIfErrorMs});if(this.cache.size>this.maxEntries){const first=this.cache.keys().next().value as string|undefined;if(first)this.cache.delete(first)}}
 delete(key:string){this.cache.delete(key)}clear(){this.cache.clear();this.inflight.clear()}
}
