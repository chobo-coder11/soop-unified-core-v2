import type{ChannelSnapshot,LiveSnapshot,ProviderObservation}from'../types.js';
import{CircuitBreaker}from'../core/circuit-breaker.js';
import{PROVIDER_PROVENANCE}from'../core/provider-provenance.js';
import{withDeadline}from'../core/deadline.js';

export class SoopJsProvider{
 readonly breaker:CircuitBreaker;private client:any;private init?:Promise<void>;
 constructor(private enabled:boolean,private timeoutMs:number){this.breaker=new CircuitBreaker('soopjs',enabled)}
 private async boot(){if(this.client)return;if(!this.init)this.init=(async()=>{const m:any=await import('soop.js'),C=m.default??m;this.client=new C({browser:{headless:true}});await this.client.bootstrapping()})();await withDeadline(this.init,this.timeoutMs,'soopjs boot')}
 private async observe<T>(fn:()=>Promise<T>):Promise<ProviderObservation<T>>{const s=Date.now();try{const value=await this.breaker.run(async()=>{await this.boot();return withDeadline(fn(),this.timeoutMs,'soopjs request')});return{provider:'soopjs',ok:true,latencyMs:Date.now()-s,observedAt:new Date().toISOString(),value,provenance:PROVIDER_PROVENANCE.soopjs}}catch(e){return{provider:'soopjs',ok:false,latencyMs:Date.now()-s,observedAt:new Date().toISOString(),error:e instanceof Error?e.message:String(e),provenance:PROVIDER_PROVENANCE.soopjs}}}
 live(id:string){return this.observe<LiveSnapshot>(async()=>{const j:any=await this.client.live.info(id);return{streamerId:id,online:Boolean(j),title:j?.streamTitle,thumbnailUrl:j?.thumbnailUrl,streamerNickname:j?.streamerInfo?.streamerName,raw:j}})}
 channel(id:string){return this.observe<ChannelSnapshot>(async()=>{const j:any=await this.client.search.channel(id),num=(v:any)=>{const n=Number(String(v??'').replace(/[^0-9]/g,''));return Number.isFinite(n)&&n>0?n:undefined};return{streamerId:id,nickname:j?.streamerName,profileImage:j?.streamerThumbnail,favorites:num(j?.streamerFavorites),subscribers:num(j?.streamerSubscribe),explanation:j?.streamerExplanation,raw:j}})}
 async close(){try{await withDeadline(Promise.resolve(this.client?.close?.()),Math.min(2000,this.timeoutMs),'soopjs close')}catch{}}
}
