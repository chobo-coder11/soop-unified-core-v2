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
import{RouletteManager}from'../roulette/manager.js';
import{ROULETTE_ADMIN_HTML,ROULETTE_OVERLAY_HTML,ROULETTE_ADMIN_JS,ROULETTE_OVERLAY_JS}from'../roulette/ui.js';

const json=(res:ServerResponse,status:number,data:any)=>{const body=JSON.stringify(data);res.writeHead(status,{'content-type':'application/json; charset=utf-8','content-length':Buffer.byteLength(body)});res.end(body)};
const clean=(value:any,debug=false)=>debug?value:JSON.parse(JSON.stringify(value,(key,v)=>key==='raw'?undefined:v));

async function readJson(req:IncomingMessage,maxBytes:number){
  let size=0;const chunks:Buffer[]=[];
  for await(const chunk of req){const b=Buffer.isBuffer(chunk)?chunk:Buffer.from(chunk);size+=b.length;if(size>maxBytes)throw new Error('request_body_too_large');chunks.push(b)}
  if(!chunks.length)return{};
  try{return JSON.parse(Buffer.concat(chunks).toString('utf8'))}catch{throw new Error('invalid_json')}
}

export class ApiServer{
  readonly server:http.Server;readonly ws:WsHub;private limiter:FixedWindowRateLimiter;private roulette=new RouletteManager();private rouletteClients=new Set<ServerResponse>();
  constructor(private service:UnifiedService,private cfg:AppConfig){
    this.limiter=new FixedWindowRateLimiter(cfg.rateLimitPerMinute);this.ws=new WsHub(service,cfg);
    this.server=http.createServer((req,res)=>void this.handle(req,res));
    service.pool.on('event',(e)=>this.roulette.donation(e));
    this.roulette.on('change',(event)=>{const line=`data: ${JSON.stringify(event)}\n\n`;for(const client of this.rouletteClients)try{client.write(line)}catch{this.rouletteClients.delete(client)}});
    this.server.on('upgrade',(req,socket,head)=>{const u=new URL(req.url??'/',`http://${req.headers.host??'localhost'}`);if(u.pathname!=='/v1/ws'||!this.authorized(req)){socket.destroy();return}const lim=this.limiter.allow(req.socket.remoteAddress??'unknown');if(!lim.ok){socket.destroy();return}this.ws.handleUpgrade(req,socket,head)})
  }
  listen(){return new Promise<void>(r=>this.server.listen(this.cfg.port,this.cfg.host,r))}
  private authorized(req:IncomingMessage){if(!this.cfg.apiKey)return true;const raw=req.headers['x-api-key'],apiKey=Array.isArray(raw)?raw[0]:raw,bearer=(req.headers.authorization??'').replace(/^Bearer\s+/i,'');return secureTokenEqual(apiKey,this.cfg.apiKey)||secureTokenEqual(bearer,this.cfg.apiKey)}
  private writeAllowed(){return this.cfg.enableWriteApi&&Boolean(this.cfg.apiKey)}
  private local(req:IncomingMessage){const ip=req.socket.remoteAddress??'';return ip==='127.0.0.1'||ip==='::1'||ip==='::ffff:127.0.0.1'}

  private async handle(req:IncomingMessage,res:ServerResponse){
    const u=new URL(req.url??'/',`http://${req.headers.host??'localhost'}`);
    if(req.method==='GET'&&u.pathname==='/livez')return json(res,200,{ok:true,status:'alive',uptimeSec:Math.floor(process.uptime())});
    if(req.method==='GET'&&u.pathname==='/readyz')return json(res,200,{ok:true,status:'ready',connections:this.service.pool.list().length,time:new Date().toISOString()});
    if(req.method==='GET'&&u.pathname==='/studio'){const body=STUDIO_HTML;res.writeHead(200,{'content-type':'text/html; charset=utf-8','content-length':Buffer.byteLength(body)});return res.end(body)}
    if(req.method==='GET'&&u.pathname==='/roulette'){const body=ROULETTE_ADMIN_HTML;res.writeHead(200,{'content-type':'text/html; charset=utf-8','content-length':Buffer.byteLength(body),'cache-control':'no-store'});return res.end(body)}
    if(req.method==='GET'&&u.pathname==='/roulette/overlay'){const body=ROULETTE_OVERLAY_HTML;res.writeHead(200,{'content-type':'text/html; charset=utf-8','content-length':Buffer.byteLength(body),'cache-control':'no-store'});return res.end(body)}
    if(req.method==='GET'&&u.pathname==='/roulette/admin.js'){const body=ROULETTE_ADMIN_JS;res.writeHead(200,{'content-type':'text/javascript; charset=utf-8','content-length':Buffer.byteLength(body),'cache-control':'no-store'});return res.end(body)}
    if(req.method==='GET'&&u.pathname==='/roulette/overlay.js'){const body=ROULETTE_OVERLAY_JS;res.writeHead(200,{'content-type':'text/javascript; charset=utf-8','content-length':Buffer.byteLength(body),'cache-control':'no-store'});return res.end(body)}
    if(u.pathname.startsWith('/v1/roulette')){
      if(!this.local(req))return json(res,403,{ok:false,error:'룰렛 관리는 이 PC에서만 사용할 수 있습니다.'});
      try{
        if(req.method==='GET'&&u.pathname==='/v1/roulette/state')return json(res,200,{ok:true,state:this.roulette.snapshot()});
        if(req.method==='GET'&&u.pathname==='/v1/roulette/connection'){const id=this.roulette.snapshot().streamerId;if(!id)return json(res,200,{ok:true,connection:{state:'idle',label:'방송국을 연결해 주세요.'}});const data=await this.service.state(id),nickname=data.channel?.data.nickname||data.live?.data.streamerNickname||id,online=Boolean(data.live?.data.online),socket=data.connection?.state??(online?'connecting':'offline-wait'),ready=socket==='entered';return json(res,200,{ok:true,connection:{streamerId:id,nickname,online,socket,ready,integrity:data.collectionIntegrity,label:ready?'실시간 후원 수집 중':online?'실시간 연결 중':'현재 방송 오프라인'}})}
        if(req.method==='GET'&&u.pathname==='/v1/roulette/events'){res.writeHead(200,{'content-type':'text/event-stream; charset=utf-8','cache-control':'no-cache, no-transform','connection':'keep-alive','x-accel-buffering':'no'});res.write(`retry: 1500\ndata: ${JSON.stringify({type:'ready',state:this.roulette.snapshot()})}\n\n`);this.rouletteClients.add(res);const heartbeat=setInterval(()=>{try{res.write(': keepalive\n\n')}catch{}},10_000);req.on('close',()=>{clearInterval(heartbeat);this.rouletteClients.delete(res)});return}
        if(req.method==='POST'&&u.pathname==='/v1/roulette/settings'){const body=await readJson(req,this.cfg.maxBodyBytes),next=String(body.streamerId??'').trim();if(!validId(next))return json(res,400,{ok:false,error:'SOOP 스트리머 ID를 확인해 주세요.'});const old=this.roulette.snapshot().streamerId;if(old&&old!==next)await this.service.pool.unpin(old);this.roulette.setStreamer(next);await this.service.pool.pin(next);return json(res,200,{ok:true,state:this.roulette.snapshot()})}
        if(req.method==='POST'&&u.pathname==='/v1/roulette/boxes'){const body=await readJson(req,this.cfg.maxBodyBytes),box=this.roulette.createBox({title:String(body.title??''),code:String(body.code??''),goal:Number(body.goal)});return json(res,201,{ok:true,box,state:this.roulette.snapshot()})}
        if(req.method==='POST'&&u.pathname==='/v1/roulette/active-box'){const body=await readJson(req,this.cfg.maxBodyBytes),box=this.roulette.setActiveBox(String(body.boxId??''));return json(res,200,{ok:true,box,state:this.roulette.snapshot()})}
        if(req.method==='POST'&&u.pathname==='/v1/roulette/overlay-settings'){const body=await readJson(req,this.cfg.maxBodyBytes),overlay=this.roulette.setOverlay({x:Number(body.x),y:Number(body.y),scale:Number(body.scale)});return json(res,200,{ok:true,overlay,state:this.roulette.snapshot()})}
        const boxPath=u.pathname.match(/^\/v1\/roulette\/boxes\/([0-9a-f-]+)$/);if(req.method==='DELETE'&&boxPath){const box=this.roulette.archiveBox(boxPath[1]);return json(res,200,{ok:true,box,state:this.roulette.snapshot()})}
        if(req.method==='POST'&&u.pathname==='/v1/roulette/test-donation'){const body=await readJson(req,this.cfg.maxBodyBytes),result=this.roulette.testDonation({nickname:String(body.nickname||'테스트요정'),amount:Number(body.amount),message:String(body.message??'')});return json(res,200,{ok:true,result,state:this.roulette.snapshot()})}
        return json(res,404,{ok:false,error:'not_found'});
      }catch(e){return json(res,400,{ok:false,error:e instanceof Error?e.message:String(e)})}
    }
    if(!this.authorized(req))return json(res,401,{ok:false,error:'unauthorized'});
    const lim=this.limiter.allow(req.socket.remoteAddress??'unknown');res.setHeader('x-ratelimit-remaining',String(lim.remaining));
    if(!lim.ok)return json(res,429,{ok:false,error:'rate_limited',resetMs:lim.resetMs});
    const debug=u.searchParams.get('debug')==='1',refresh=u.searchParams.get('refresh')==='1';
    try{
      if(req.method==='GET'&&u.pathname==='/v1/health')return json(res,200,{ok:true,service:'soop-unified-core',version:'2.5.0',providers:this.service.providers.health(),connections:this.service.pool.list().length,writeApi:this.writeAllowed(),time:new Date().toISOString()});
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
  async close(){const id=this.roulette.snapshot().streamerId;if(id)await this.service.pool.unpin(id);for(const client of this.rouletteClients)client.end();await this.ws.close();await new Promise<void>(r=>this.server.close(()=>r()))}
}
