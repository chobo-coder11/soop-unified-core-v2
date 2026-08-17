import { EventEmitter } from 'node:events';
import { parsePacket } from '../protocol/packet.js';
import { decodePacket } from '../protocol/decoders.js';
import type { CanonicalEvent,ProtocolAnomaly } from '../types.js';

export type MirrorState='idle'|'connecting'|'connected'|'reconnecting'|'closed'|'unavailable';
/** Optional secondary realtime implementation used to cross-check the native protocol core. */
export class ReindeerChatMirror extends EventEmitter {
 state:MirrorState='idle';private chat:any;private stopped=false;private attempt=0;private retry?:NodeJS.Timeout;private connecting=false;
 constructor(readonly streamerId:string,private maxBackoff=30000){super()}
 async start(){if(['connecting','connected'].includes(this.state)||this.connecting)return;this.stopped=false;await this.connect()}
 private async connect(){if(this.connecting||this.stopped)return;this.connecting=true;if(this.retry){clearTimeout(this.retry);this.retry=undefined}this.state=this.attempt?'reconnecting':'connecting';try{const m:any=await import('soop-extension'),client=new m.SoopClient(),chat=client.chat({streamerId:this.streamerId});this.chat=chat;chat.on(m.SoopChatEvent.RAW,(raw:any)=>this.onRaw(raw));chat.on(m.SoopChatEvent.DISCONNECT,()=>{if(!this.stopped)this.schedule('disconnect')});await chat.connect();this.state='connected';this.attempt=0}catch(error){const msg=error instanceof Error?error.message:String(error);if(/Cannot find package|Cannot find module|ERR_MODULE_NOT_FOUND/.test(msg)){this.state='unavailable';this.emit('error-state',new Error(msg));return}this.schedule(msg)}finally{this.connecting=false}}
 private anomaly(kind:ProtocolAnomaly['kind'],detail:string,raw?:string,code?:number){this.emit('protocol-anomaly',{kind,streamerId:this.streamerId,source:'reindeer',receivedAt:new Date().toISOString(),detail,raw,code} satisfies ProtocolAnomaly)}
 private onRaw(value:any){const raw=Buffer.isBuffer(value)?value.toString('utf8'):String(value);try{const packet=parsePacket(raw);if(!packet.lengthValid)this.anomaly('length-mismatch',`declared=${packet.declaredLength} actual=${packet.actualLength}`,raw,packet.code);const event:CanonicalEvent=decodePacket(this.streamerId,packet,'reindeer');this.emit('event',event)}catch(e){this.anomaly('parse-error',e instanceof Error?e.message:String(e),raw)}}
 private schedule(reason:string){if(this.stopped||this.retry)return;this.state='reconnecting';this.attempt++;const base=Math.min(2000*2**Math.max(0,this.attempt-1),this.maxBackoff),delay=Math.floor(base*(.8+Math.random()*.4));this.retry=setTimeout(()=>{this.retry=undefined;void this.connect()},delay);this.emit('reconnect-scheduled',{attempt:this.attempt,delay,reason})}
 async stop(){this.stopped=true;this.state='closed';if(this.retry)clearTimeout(this.retry);this.retry=undefined;try{await this.chat?.disconnect?.()}catch{}this.chat=undefined}
}
