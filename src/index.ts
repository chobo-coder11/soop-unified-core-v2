import{loadConfig}from'./config.js';import{UnifiedService}from'./core/unified-service.js';import{ApiServer}from'./server/api-server.js';
const cfg=loadConfig();
if(cfg.enableWriteApi&&!cfg.apiKey)console.warn('[soop-unified-core] write API requested but SOOP_API_KEY is empty; write routes will remain disabled');
const service=new UnifiedService(cfg),api=new ApiServer(service,cfg);await api.listen();console.log(`[soop-unified-core] listening on http://${cfg.host}:${cfg.port}`);let closing=false;const shutdown=async(signal:string)=>{if(closing)return;closing=true;console.log(`[soop-unified-core] ${signal}, shutting down`);await api.close();await service.close();process.exit(0)};process.on('SIGINT',()=>void shutdown('SIGINT'));process.on('SIGTERM',()=>void shutdown('SIGTERM'));
