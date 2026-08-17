export type ApiErrorCode='INVALID_REQUEST'|'PAYLOAD_TOO_LARGE'|'UNAUTHORIZED'|'FORBIDDEN'|'RESTRICTED_STREAM'|'STREAM_OFFLINE'|'UPSTREAM_TIMEOUT'|'UPSTREAM_UNAVAILABLE'|'UPSTREAM_CHANGED'|'UPSTREAM_FAILURE';
export interface ApiErrorInfo{status:number;code:ApiErrorCode;retryable:boolean;message:string}

export function classifyApiError(message:string):ApiErrorInfo{
  const raw=String(message||'unknown error'),m=raw.toLowerCase();
  if(m==='invalid_json'||m.includes('invalid credentials')||m.includes('invalid chat message')||m.includes('invalid whisper message')||m.includes('invalid target id'))return{status:400,code:'INVALID_REQUEST',retryable:false,message:raw};
  if(m==='request_body_too_large')return{status:413,code:'PAYLOAD_TOO_LARGE',retryable:false,message:raw};
  if(m.includes('invalid auth session')||m.includes('auth session expired')||m.includes('authenticated session required'))return{status:401,code:'UNAUTHORIZED',retryable:false,message:raw};
  if(m.includes('write api disabled'))return{status:403,code:'FORBIDDEN',retryable:false,message:raw};
  if(m.includes('password protected'))return{status:403,code:'RESTRICTED_STREAM',retryable:false,message:raw};
  if(m.includes('stream offline'))return{status:503,code:'STREAM_OFFLINE',retryable:false,message:raw};
  if(m.includes('timeout')||m.includes('aborted')||m.includes('econnreset')||m.includes('econnrefused')||m.includes('fetch failed'))return{status:503,code:'UPSTREAM_TIMEOUT',retryable:true,message:raw};
  if(m.includes('all live providers failed')||m.includes('all channel providers failed'))return{status:502,code:'UPSTREAM_UNAVAILABLE',retryable:true,message:raw};
  if(m.includes('missing chat endpoint')||m.includes('protocol'))return{status:502,code:'UPSTREAM_CHANGED',retryable:true,message:raw};
  return{status:502,code:'UPSTREAM_FAILURE',retryable:true,message:raw};
}

export function httpStatusForError(message:string){return classifyApiError(message).status}
