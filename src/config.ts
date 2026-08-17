export interface AppConfig {
  host:string; port:number; apiKey?:string; rateLimitPerMinute:number;
  streamIdleTtlMs:number; rawBufferPerStream:number; eventDedupTtlMs:number;
  providerTimeoutMs:number; javaSidecarUrl:string; enableJavaSidecar:boolean;
  enableReindeerProvider:boolean; enableReindeerEvents:boolean;
  enableSoopJsProvider:boolean; maxWsSubscriptions:number; maxWsClients:number;
  wsClientIdleMs:number; wsMaxPayloadBytes:number; wsBackpressureBytes:number;
  liveCacheMs:number; channelCacheMs:number; batchConcurrency:number;
  enableWriteApi:boolean; authSessionTtlMs:number; maxBodyBytes:number;
  allowInsecureTls:boolean; chatPingIntervalMs:number; chatLivenessTimeoutMs:number;
  chatJoinTimeoutMs:number; chatOfflinePollMs:number; chatMaxBackoffMs:number;
  cacheStaleIfErrorMs:number; wsReplayEvents:number; connectionTimelineLimit:number;
  driftWindowMs:number; driftMinUnknown:number; driftMinMalformed:number;
  driftMinStreams:number; driftUnknownRatio:number; driftAlertCooldownMs:number;
}
const bool=(name:string,fallback:boolean)=>{const v=process.env[name];return v==null||v===''?fallback:['1','true','yes','on'].includes(v.toLowerCase())};
const num=(name:string,fallback:number,min=0,max=Number.MAX_SAFE_INTEGER)=>{const raw=process.env[name];if(raw==null||raw==='')return fallback;const n=Number(raw);return Number.isFinite(n)?Math.max(min,Math.min(max,n)):fallback};
export function loadConfig():AppConfig{return{
  host:process.env.HOST||'0.0.0.0',port:num('PORT',8080),apiKey:process.env.SOOP_API_KEY||undefined,
  rateLimitPerMinute:num('SOOP_RATE_LIMIT_PER_MINUTE',240,1,100000),streamIdleTtlMs:num('SOOP_STREAM_IDLE_TTL_MS',30000,0,3600000),
  rawBufferPerStream:num('SOOP_RAW_BUFFER_PER_STREAM',1000,10,100000),eventDedupTtlMs:num('SOOP_EVENT_DEDUP_TTL_MS',2500,250,60000),
  providerTimeoutMs:num('SOOP_PROVIDER_TIMEOUT_MS',4500,500,60000),javaSidecarUrl:process.env.SOOP_JAVA_SIDECAR_URL||'http://127.0.0.1:8091',
  enableJavaSidecar:bool('SOOP_ENABLE_JAVA_SIDECAR',true),enableReindeerProvider:bool('SOOP_ENABLE_REINDEER_PROVIDER',true),
  enableReindeerEvents:bool('SOOP_ENABLE_REINDEER_EVENTS',false),enableSoopJsProvider:bool('SOOP_ENABLE_SOOPJS_PROVIDER',false),
  maxWsSubscriptions:num('SOOP_MAX_WS_SUBSCRIPTIONS',100,1,5000),maxWsClients:num('SOOP_MAX_WS_CLIENTS',500,1,100000),
  wsClientIdleMs:num('SOOP_WS_CLIENT_IDLE_MS',90000,10000,3600000),wsMaxPayloadBytes:num('SOOP_WS_MAX_PAYLOAD_BYTES',65536,1024,10485760),wsBackpressureBytes:num('SOOP_WS_BACKPRESSURE_BYTES',2000000,65536,67108864),liveCacheMs:num('SOOP_LIVE_CACHE_MS',1200,0,60000),
  channelCacheMs:num('SOOP_CHANNEL_CACHE_MS',15000,0,300000),batchConcurrency:num('SOOP_BATCH_CONCURRENCY',8,1,100),
  enableWriteApi:bool('SOOP_ENABLE_WRITE_API',false),authSessionTtlMs:num('SOOP_AUTH_SESSION_TTL_MS',8*60*60*1000,60000,7*24*60*60*1000),
  maxBodyBytes:num('SOOP_MAX_BODY_BYTES',65536,1024,10485760),
  allowInsecureTls:bool('SOOP_ALLOW_INSECURE_TLS',false),chatPingIntervalMs:num('SOOP_CHAT_PING_INTERVAL_MS',30000,5000,300000),
  chatLivenessTimeoutMs:num('SOOP_CHAT_LIVENESS_TIMEOUT_MS',120000,15000,1800000),chatJoinTimeoutMs:num('SOOP_CHAT_JOIN_TIMEOUT_MS',12000,3000,120000),
  chatOfflinePollMs:num('SOOP_CHAT_OFFLINE_POLL_MS',30000,5000,600000),chatMaxBackoffMs:num('SOOP_CHAT_MAX_BACKOFF_MS',30000,2000,600000),
  cacheStaleIfErrorMs:num('SOOP_CACHE_STALE_IF_ERROR_MS',15000,0,600000),wsReplayEvents:num('SOOP_WS_REPLAY_EVENTS',5000,100,50000),connectionTimelineLimit:num('SOOP_CONNECTION_TIMELINE_LIMIT',100,20,1000),
  driftWindowMs:num('SOOP_DRIFT_WINDOW_MS',60000,5000,3600000),driftMinUnknown:num('SOOP_DRIFT_MIN_UNKNOWN',20,1,100000),
  driftMinMalformed:num('SOOP_DRIFT_MIN_MALFORMED',5,1,100000),driftMinStreams:num('SOOP_DRIFT_MIN_STREAMS',3,1,10000),
  driftUnknownRatio:num('SOOP_DRIFT_UNKNOWN_RATIO',0.08,0,1),driftAlertCooldownMs:num('SOOP_DRIFT_ALERT_COOLDOWN_MS',30000,0,3600000)
}}
