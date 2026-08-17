export class SoopUnifiedClient{
  constructor(private baseUrl='http://localhost:8080',private apiKey?:string){}
  private headers(extra:Record<string,string>={}){return this.apiKey?{'x-api-key':this.apiKey,...extra}:extra}
  private async request(path:string,init:RequestInit={}){const r=await fetch(`${this.baseUrl}${path}`,{...init,headers:{...this.headers(),...(init.headers as any)}});const data:any=await r.json().catch(()=>({}));if(!r.ok)throw new Error(data?.error??`Unified API ${r.status}`);return data}
  private get(path:string){return this.request(path)}
  private post(path:string,body:any){return this.request(path,{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify(body)})}
  live(id:string){return this.get(`/v1/live/${encodeURIComponent(id)}`)}
  channel(id:string){return this.get(`/v1/channel/${encodeURIComponent(id)}`)}
  viewers(id:string){return this.get(`/v1/viewers/${encodeURIComponent(id)}`)}
  state(id:string){return this.get(`/v1/state/${encodeURIComponent(id)}`)}
  batch(kind:'live'|'channel'|'viewers'|'state',ids:string[]){return this.get(`/v1/${kind}?ids=${ids.map(encodeURIComponent).join(',')}`)}
  providers(){return this.get('/v1/providers')}
  login(userId:string,password:string){return this.post('/v1/auth/login',{userId,password})}
  logout(sessionId:string){return this.post('/v1/auth/logout',{sessionId})}
  sendChat(streamerId:string,sessionId:string,message:string){return this.post(`/v1/chat/${encodeURIComponent(streamerId)}/send`,{sessionId,message})}
  sendWhisper(streamerId:string,sessionId:string,targetId:string,message:string){return this.post(`/v1/chat/${encodeURIComponent(streamerId)}/whisper`,{sessionId,targetId,message})}
}
