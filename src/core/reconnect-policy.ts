export type ConnectionFailureKind='offline'|'blocked'|'auth'|'protocol'|'transient';
export function classifyConnectionFailure(reason:string):ConnectionFailureKind{
 const r=reason.toLowerCase();
 if(/password protected|forbidden stream|access denied/.test(r))return'blocked';
 if(/stream offline|offline/.test(r))return'offline';
 if(/auth|ticket|unauthor|login|cookie/.test(r))return'auth';
 if(/packet|protocol|invalid soop|length mismatch|decode|malformed/.test(r))return'protocol';
 return'transient';
}
export function reconnectDelay(kind:ConnectionFailureKind,attempt:number,maxBackoffMs:number,offlinePollMs:number,random=Math.random):number|null{
 if(kind==='blocked'||(kind==='auth'&&attempt>=3)||(kind==='protocol'&&attempt>=5))return null;
 const n=Math.max(0,attempt-1);let base:number;
 if(kind==='offline')base=offlinePollMs;
 else if(kind==='auth')base=Math.min(120000,5000*2**Math.min(n,5));
 else if(kind==='protocol')base=Math.min(Math.max(15000,maxBackoffMs),15000*2**Math.min(n,3));
 else base=Math.min(maxBackoffMs,2000*2**Math.min(n,10));
 return Math.max(250,Math.floor(base*(.85+random()*.3)));
}
