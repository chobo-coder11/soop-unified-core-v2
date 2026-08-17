import WebSocket from'ws';
const base=process.env.UNIFIED_URL||'http://127.0.0.1:8080';
const ids=(process.env.STREAMER_IDS||process.env.STREAMER_ID||'').split(',').map((x:string)=>x.trim()).filter(Boolean);
const durationSec=Math.max(30,Number(process.env.SOAK_DURATION_SECONDS||300));
const intervalMs=Math.max(1000,Number(process.env.SOAK_INTERVAL_MS||5000));
const apiKey=process.env.SOOP_API_KEY||'';
if(!ids.length)throw new Error('STREAMER_IDS or STREAMER_ID required');
const headers:Record<string,string>=apiKey?{'x-api-key':apiKey}:{};const end=Date.now()+durationSec*1000;let requests=0,failures=0,uncertain=0,events=0,gaps=0,dropped=0,replayed=0,disconnects=0,lastSeq=0,lastProviders:any,lastMetrics:any;
const wsUrl=base.replace(/^http/,'ws')+'/v1/ws';
const ws=new WebSocket(wsUrl,[] as string[],{headers} as any);
await new Promise<void>((resolve,reject)=>{const timer=setTimeout(()=>reject(new Error('soak websocket connect timeout')),10000);ws.once('open',()=>{clearTimeout(timer);resolve()});ws.once('error',reject)});
ws.send(JSON.stringify({action:'subscribe',streamers:ids}));
ws.on('message',(buf:any)=>{try{const m=JSON.parse(String(buf));if(m.type==='event'){events++;if(m.replayed)replayed++;if(Number.isSafeInteger(m.seq))lastSeq=Math.max(lastSeq,m.seq)}else if(m.type==='gap'){gaps++;dropped+=Number(m.dropped||0)}}catch{}});
ws.on('close',()=>disconnects++);
while(Date.now()<end){const started=Date.now();for(const id of ids){requests++;try{const r=await fetch(`${base}/v1/state/${encodeURIComponent(id)}?refresh=1`,{headers});if(!r.ok)throw new Error(`HTTP ${r.status}`);const j:any=await r.json();const state=j?.data?.live?.consensus?.onlineState;if(state==='uncertain')uncertain++;if(j?.data?.live?.freshness?.state==='stale')console.warn('[soak] stale live data',id,j.data.live.freshness)}catch(e){failures++;console.error('[soak] request failed',id,e instanceof Error?e.message:String(e))}}
 try{const r=await fetch(`${base}/v1/providers`,{headers});if(r.ok)lastProviders=(await r.json())?.providers}catch{}
 try{const r=await fetch(`${base}/v1/metrics`,{headers});if(r.ok)lastMetrics=await r.json()}catch{}
 const sleep=Math.max(0,intervalMs-(Date.now()-started));if(sleep)await new Promise(r=>setTimeout(r,sleep))}
try{ws.close(1000,'soak complete')}catch{}
const failureRate=requests?failures/requests:1;const ok=failureRate<=.02&&disconnects===0&&gaps===0;console.log(JSON.stringify({ok,requests,failures,failureRate,uncertain,events,gaps,dropped,replayed,disconnects,lastSeq,lastProviders,runtimeMetrics:lastMetrics?.gauges},null,2));if(!ok)process.exit(1);
