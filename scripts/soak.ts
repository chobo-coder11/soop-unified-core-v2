const base=process.env.UNIFIED_URL||'http://127.0.0.1:8080';
const ids=(process.env.STREAMER_IDS||process.env.STREAMER_ID||'').split(',').map(x=>x.trim()).filter(Boolean);
const durationSec=Math.max(30,Number(process.env.SOAK_DURATION_SECONDS||300));
const intervalMs=Math.max(1000,Number(process.env.SOAK_INTERVAL_MS||5000));
if(!ids.length)throw new Error('STREAMER_IDS or STREAMER_ID required');
const end=Date.now()+durationSec*1000;let requests=0,failures=0,uncertain=0,lastProviders:any;
while(Date.now()<end){
  const started=Date.now();
  for(const id of ids){
    requests++;
    try{const r=await fetch(`${base}/v1/state/${encodeURIComponent(id)}?refresh=1`);if(!r.ok)throw new Error(`HTTP ${r.status}`);const j:any=await r.json();const state=j?.data?.live?.consensus?.onlineState;if(state==='uncertain')uncertain++}catch(e){failures++;console.error('[soak] request failed',id,e instanceof Error?e.message:String(e))}
  }
  try{const r=await fetch(`${base}/v1/providers`);if(r.ok)lastProviders=(await r.json())?.providers}catch{}
  const sleep=Math.max(0,intervalMs-(Date.now()-started));if(sleep)await new Promise(r=>setTimeout(r,sleep));
}
const failureRate=requests?failures/requests:1;console.log(JSON.stringify({ok:failureRate<=.02,requests,failures,failureRate,uncertain,lastProviders},null,2));if(failureRate>.02)process.exit(1);
