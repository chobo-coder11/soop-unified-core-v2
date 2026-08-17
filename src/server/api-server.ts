import http,{type IncomingMessage,type ServerResponse}from'node:http';
import{URL}from'node:url';
import type{AppConfig}from'../config.js';
import type{UnifiedService}from'../core/unified-service.js';
import{EVENT_CATALOG}from'../protocol/catalog.js';
import{FixedWindowRateLimiter}from'./rate-limit.js';
import{WsHub,validId}from'./ws-hub.js';
import{secureTokenEqual}from'./auth.js';
import{httpStatusForError}from'./errors.js';
import{STUDIO_HTML}from'./studio.js';

const json=(res:ServerResponse,status:number,data:any)=>{const body=JSON.stringify(data);res.writeHead(status,{'content-type':'application/json; charset=utf-8','content-length':Buffer.byteLength(body)});res.end(body)};
const clean=(value:any,debug=false)=>debug?value:JSON.parse(JSON.stringify(value,(key,v)=>key==='raw'?undefined:v));

async function readJson(req:IncomingMessage,maxBytes:number){
  let size=0;const chunks:Buffer[]=[];
  for await(const chunk of req){const b=Buffer.isBuffer(chunk)?chunk:Buffer.from(chunk);size+=b.length;if(size>maxBytes)throw new Error('request_body_too_large');chunks.push(b)}
  if(!chunks.length)return{};
  try{return JSON.parse(Buffer.concat(chunks).toString('utf8'))}catch{throw new Error('invalid_json')}
}

export class ApiServer{
  readonly server:http.Server;readonly ws:WsHub;private limiter:FixedWindowRateLimiter;
  constructor(private service:UnifiedService,private cfg:AppConfig){
    this.limiter=new FixedWindowRateLimiter(cfg.rateLimitPerMinute);this.ws=new WsHub(service,cfg);
    this.server=http.createServer((req,res)=>void this.handle(req,res));
    this.server.on('upgrade',(req,socket,head)=>{const u=new URL(req.url??'/',`http://${req.headers.host??'localhost'}`);if(u.pathname!=='/v1/ws'||!this.authorized(req)){socket.destroy();return}const lim=this.limiter.allow(req.socket.remoteAddress??'unknown');if(!lim.ok){socket.destroy();return}this.ws.handleUpgrade(req,socket,head)})
  }
  listen(){return new Promise<void>(r=>this.server.listen(this.cfg.port,this.cfg.host,r))}
  private authorized(req:IncomingMessage){if(!this.cfg.apiKey)return true;const raw=req.headers['x-api-key'],apiKey=Array.isArray(raw)?raw[0]:raw,bearer=(req.headers.authorization??'').replace(/^Bearer\s+/i,'');return secureTokenEqual(apiKey,this.cfg.apiKey)||secureTokenEqual(bearer,this.cfg.apiKey)}
  private writeAllowed(){return this.cfg.enableWriteApi&&Boolean(this.cfg.apiKey)}

  private async handle(req:IncomingMessage,res:ServerResponse){
    const u=new URL(req.url??'/',`http://${req.headers.host??'localhost'}`);
    if(req.method==='GET'&&u.pathname==='/livez')return json(res,200,{ok:true,status:'alive',uptimeSec:Math.floor(process.uptime())});
    if(req.method==='GET'&&u.pathname==='/readyz')return json(res,200,{ok:true,status:'ready',connections:this.service.pool.list().length,time:new Date().toISOString()});
    if(req.method==='GET'&&u.pathname==='/studio'){const body=STUDIO_HTML;res.writeHead(200,{'content-type':'text/html; charset=utf-8','content-length':Buffer.byteLength(body)});return res.end(body)}
    if(!this.authorized(req))return json(res,401,{ok:false,error:'unauthorized'});
    const lim=this.limiter.allow(req.socket.remoteAddress??'unknown');res.setHeader('x-ratelimit-remaining',String(lim.remaining));
    if(!lim.ok)return json(res,429,{ok:false,error:'rate_limited',resetMs:lim.resetMs});
    const debug=u.searchParams.get('debug')==='1',refresh=u.searchParams.get('refresh')==='1';
    try{
      if(req.method==='GET'&&u.pathname==='/v1/health')return json(res,200,{ok:true,service:'soop-unified-core',version:'2.4.0',providers:this.service.providers.health(),connections:this.service.pool.list().length,writeApi:this.writeAllowed(),time:new Date().toISOString()});
      if(req.method==='GET'&&u.pathname==='/v1/providers')return json(res,200,{ok:true,providers:this.service.providers.health(),reliability:this.service.providers.reliabilitySnapshot()});
      if(req.method==='GET'&&u.pathname==='/v1/diagnostics')return json(res,200,{ok:true,...this.service.diagnostics()});
      if(req.method==='GET'&&u.pathname==='/v1/diagnostics/drift')return json(res,200,{ok:true,drift:this.service.pool.drift.snapshot(),incidents:this.service.raw.incidents(100),flightRecordings:this.service.raw.flightRecordings(20)});
      if(req.method==='GET'&&u.pathname==='/v1/diagnostics/anomalies')return json(res,200,{ok:true,anomalies:this.service.raw.recentAnomalies(Math.min(1000,Number(u.searchParams.get('limit')||100)))});
      if(req.method==='GET'&&u.pathname==='/v1/catalog/events'){const support=u.searchParams.get('support');const events=support?EVENT_CATALOG.filter(e=>e.supportLevel===support):EVENT_CATALOG;return json(res,200,{ok:true,count:events.length,total:EVENT_CATALOG.length,events});}
      if(req.method==='GET'&&u.pathname==='/v1/streams')return json(res,200,{ok:true,streams:this.service.pool.list()});
      if(req.method==='GET'&&u.pathname==='/v1/metrics')return json(res,200,{ok:true,...this.service.metrics.json()});
      if(req.method==='GET'&&u.pathname==='/metrics'){const body=this.service.metrics.prometheus();res.writeHead(200,{'content-type':'text/plain; version=0.0.4'});return res.end(body)}
      if(req.method==='GET'&&u.pathname==='/v1/raw/unknown')return json(res,200,{ok:true,unknown:this.service.raw.unknownSummary()});
      const raw=u.pathname.match(/^\/v1\/raw\/([A-Za-z0-9_-]+)$/);if(req.method==='GET'&&raw)return json(res,200,{ok:true,streamerId:raw[1],packets:this.service.raw.recent(raw[1],Math.min(1000,Number(u.searchParams.get('limit')||100)))});

      // Batch: /v1/live?ids=a,b,c (same for channel/viewers/state)
      const batch=u.pathname.match(/^\/v1\/(live|channel|viewers|state)$/);
      if(req.method==='GET'&&batch){const ids=(u.searchParams.get('ids')??'').split(',').map(x=>x.trim()).filter(validId).slice(0,500);if(!ids.length)return json(res,400,{ok:false,error:'ids_required'});const data=await this.service.batch(batch[1] as any,ids,refresh);return json(res,200,{ok:true,data:clean(data,debug)})}

      const m=u.pathname.match(/^\/v1\/(live|channel|viewers|state)\/([A-Za-z0-9_-]+)$/);
      if(req.method==='GET'&&m){const kind=m[1],id=m[2];if(!validId(id))return json(res,400,{ok:false,error:'invalid_streamer_id'});const data=kind==='live'?await this.service.live(id,refresh):kind==='channel'?await this.service.channel(id,refresh):kind==='viewers'?await this.service.viewers(id,refresh):await this.service.state(id,refresh);return json(res,200,{ok:true,data:clean(data,debug)})}

      const s=u.pathname.match(/^\/v1\/streams\/([A-Za-z0-9_-]+)$/);
      if(s&&validId(s[1])){if(req.method==='POST'){await this.service.pool.pin(s[1]);return json(res,202,{ok:true,streamerId:s[1],status:'connecting'})}if(req.method==='DELETE'){await this.service.pool.unpin(s[1]);return json(res,200,{ok:true,streamerId:s[1],status:'released'})}}

      // Authenticated write API. Disabled unless BOTH SOOP_ENABLE_WRITE_API=true and SOOP_API_KEY is set.
      if(u.pathname.startsWith('/v1/auth')||u.pathname.startsWith('/v1/chat')){
        if(!this.writeAllowed())return json(res,403,{ok:false,error:'write_api_disabled_or_api_key_missing'});
        if(req.method==='POST'&&u.pathname==='/v1/auth/login'){const body=await readJson(req,this.cfg.maxBodyBytes);const data=await this.service.auth.login(String(body.userId??''),String(body.password??''));return json(res,200,{ok:true,data})}
        if(req.method==='POST'&&u.pathname==='/v1/auth/logout'){const body=await readJson(req,this.cfg.maxBodyBytes);return json(res,200,{ok:true,loggedOut:await this.service.auth.logout(String(body.sessionId??''))})}
        if(req.method==='GET'&&u.pathname==='/v1/auth/sessions')return json(res,200,{ok:true,sessions:this.service.auth.list()});
        const send=u.pathname.match(/^\/v1\/chat\/([A-Za-z0-9_-]+)\/(send|whisper)$/);
        if(req.method==='POST'&&send){const id=send[1],body=await readJson(req,this.cfg.maxBodyBytes),sessionId=String(body.sessionId??''),message=String(body.message??'');if(send[2]==='send')await this.service.auth.sendChat(sessionId,id,message);else await this.service.auth.sendWhisper(sessionId,id,String(body.targetId??''),message);return json(res,202,{ok:true,streamerId:id,type:send[2]})}
      }

      return json(res,404,{ok:false,error:'not_found'});
    }catch(e){this.service.metrics.inc('soop_http_errors_total');const msg=e instanceof Error?e.message:String(e);const status=httpStatusForError(msg);return json(res,status,{ok:false,error:msg})}
  }
  async close(){await this.ws.close();await new Promise<void>(r=>this.server.close(()=>r()))}
}
