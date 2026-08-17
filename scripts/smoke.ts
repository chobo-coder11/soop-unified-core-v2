const id=process.env.STREAMER_ID||'bach023',base=process.env.UNIFIED_URL||'http://localhost:8080';
async function get(path:string){const r=await fetch(base+path);const text=await r.text();if(!r.ok)throw new Error(`${path} HTTP ${r.status}: ${text.slice(0,500)}`);let body:any;try{body=JSON.parse(text)}catch{throw new Error(`${path} returned invalid JSON`)}if(body?.ok!==true)throw new Error(`${path} returned ok!=true`);console.log(`[smoke] ${path} HTTP ${r.status}`);return body}
const health=await get('/v1/health');if(health.service!=='soop-unified-core')throw new Error('unexpected service name');
const live=await get(`/v1/live/${encodeURIComponent(id)}?refresh=1`);if(!live.data?.consensus)throw new Error('live response missing consensus metadata');
await get(`/v1/channel/${encodeURIComponent(id)}?refresh=1`);
const providers=await get('/v1/providers');if(!Array.isArray(providers.providers))throw new Error('providers response missing provider list');
await get('/v1/diagnostics');
console.log(JSON.stringify({ok:true,streamerId:id,onlineState:live.data?.consensus?.onlineState,confidence:live.data?.confidence},null,2));
