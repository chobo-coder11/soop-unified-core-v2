import type{ChannelSnapshot,LiveSnapshot,ProviderObservation}from'../types.js';
import{CircuitBreaker}from'../core/circuit-breaker.js';
import{PROVIDER_PROVENANCE}from'../core/provider-provenance.js';
import{withDeadline}from'../core/deadline.js';

export class ReindeerProvider{
 readonly breaker:CircuitBreaker;private client:any;private init?:Promise<void>;
 constructor(private enabled:boolean,private timeoutMs:number){this.breaker=new CircuitBreaker('reindeer',enabled)}
 private async boot(){if(this.client)return;if(!this.init)this.init=(async()=>{const m:any=await import('soop-extension');this.client=new m.SoopClient()})();await withDeadline(this.init,this.timeoutMs,'reindeer boot')}
 private async observe<T>(fn:()=>Promise<T>):Promise<ProviderObservation<T>>{const s=Date.now();try{const value=await this.breaker.run(async()=>{await this.boot();return withDeadline(fn(),this.timeoutMs,'reindeer request')});return{provider:'reindeer',ok:true,latencyMs:Date.now()-s,observedAt:new Date().toISOString(),value,provenance:PROVIDER_PROVENANCE.reindeer}}catch(e){return{provider:'reindeer',ok:false,latencyMs:Date.now()-s,observedAt:new Date().toISOString(),error:e instanceof Error?e.message:String(e),provenance:PROVIDER_PROVENANCE.reindeer}}}
 live(id:string){return this.observe<LiveSnapshot>(async()=>{const j:any=await this.client.live.detail(id),x=j?.CHANNEL??{};return{streamerId:id,online:Number(x.RESULT)!==0&&Boolean(x.BNO),bno:x.BNO?String(x.BNO):undefined,chatNo:x.CHATNO?String(x.CHATNO):undefined,streamerNickname:x.BJNICK,title:x.TITLE,category:x.CATE,viewerCount:Number.isFinite(Number(x.CTUSER))?Number(x.CTUSER):undefined,passwordProtected:Boolean(x.BPWD),resolution:x.RESOLUTION,bitrate:Number(x.BPS)||undefined,channelDomain:x.CHDOMAIN,channelPort:Number(x.CHPT)||undefined,ftk:x.FTK,raw:j}})}
 channel(id:string){return this.observe<ChannelSnapshot>(async()=>{const j:any=await this.client.channel.station(id),s=j?.station??{},b=j?.broad??{},u=s?.upd??j?.upd??{};return{streamerId:id,nickname:s.user_nick,stationName:s.station_name,stationTitle:s.station_title,profileImage:j?.profile_image,favorites:Number(u.fan_cnt)||undefined,subscribers:Number(j?.subscription?.total)||undefined,totalViewCount:Number(u.total_view_cnt)||undefined,currentViewerCount:Number(b.current_sum_viewer)||undefined,broadNo:Number(b.broad_no)||undefined,broadTitle:b.broad_title,isPassword:Boolean(b.is_password),raw:j}})}
}
