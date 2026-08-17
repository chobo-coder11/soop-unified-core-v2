import WebSocket from 'ws';
import { EventEmitter } from 'node:events';
import { randomUUID } from 'node:crypto';
import { buildPacket, parsePacket } from '../protocol/packet.js';
import { CMD_CHAT, CMD_CONNECT, CMD_DIRECT_CHAT, CMD_ENTER_INFO, CMD_JOIN, CMD_PING, ELEMENT_END, ELEMENT_START, F, SPACE } from '../protocol/constants.js';
import { decodePacket } from '../protocol/decoders.js';
import type { CanonicalEvent, LiveSnapshot, ProtocolAnomaly } from '../types.js';
import { SoopHttpClient, type SoopCookie } from '../http/soop-http.js';
import { classifyConnectionFailure, reconnectDelay } from './reconnect-policy.js';

export type ChatState='idle'|'connecting'|'connected'|'entered'|'reconnecting'|'offline-wait'|'blocked'|'protocol-error'|'closed';
export interface NativeChatOptions{
  maxBackoffMs:number;allowInsecureTls:boolean;pingIntervalMs:number;livenessTimeoutMs:number;joinTimeoutMs:number;offlinePollMs:number;cookie?:SoopCookie;
}
const DEFAULT_OPTIONS:NativeChatOptions={maxBackoffMs:30000,allowInsecureTls:false,pingIntervalMs:30000,livenessTimeoutMs:120000,joinTimeoutMs:12000,offlinePollMs:30000};

export class NativeChatConnection extends EventEmitter {
  state:ChatState='idle';
  private ws?:WebSocket;private heartbeat?:NodeJS.Timeout;private retry?:NodeJS.Timeout;private enterWatchdog?:NodeJS.Timeout;private attempt=0;private stopped=false;private live?:LiveSnapshot;private connecting=false;private lastInboundAt=0;
  private enteredWaiters:Array<{resolve:()=>void;reject:(e:Error)=>void;timer:NodeJS.Timeout}>=[];
  private opts:NativeChatOptions;

  constructor(readonly streamerId:string,private http:SoopHttpClient,options:Partial<NativeChatOptions>={}){super();this.opts={...DEFAULT_OPTIONS,...options}}
  async start(){if(['connecting','connected','entered'].includes(this.state)||this.connecting)return;this.stopped=false;await this.connect()}

  private async connect(){
    if(this.stopped||this.connecting)return;this.connecting=true;if(this.retry){clearTimeout(this.retry);this.retry=undefined}
    const reconnecting=this.attempt>0;this.state=reconnecting?'reconnecting':'connecting';if(reconnecting)this.emitSynthetic(-4,'RECONNECTING',{attemptNumber:this.attempt});
    try{
      this.live=await this.http.liveDetail(this.streamerId,this.opts.cookie);
      if(!this.live.online)throw new Error('stream offline');
      if(this.live.passwordProtected)throw new Error('password protected stream is not bypassed');
      if(!this.live.channelDomain||!this.live.channelPort)throw new Error('missing chat endpoint');
      const url=`wss://${this.live.channelDomain.toLowerCase()}:${this.live.channelPort+1}/Websocket/${this.streamerId}`;
      await new Promise<void>((resolve,reject)=>{
        const ws=new WebSocket(url,['chat'],{rejectUnauthorized:!this.opts.allowInsecureTls,handshakeTimeout:8000});this.ws=ws;let settled=false;
        ws.on('open',()=>{this.lastInboundAt=Date.now();ws.send(buildPacket(CMD_CONNECT,this.connectPayload()));this.startHeartbeat();this.startEnterWatchdog();if(!settled){settled=true;resolve()}});
        ws.on('message',b=>this.onMessage(Buffer.isBuffer(b)?b.toString('utf8'):String(b)));
        ws.on('error',err=>{if(!settled){settled=true;reject(err)}else this.emit('socket-error',err)});
        ws.on('close',(code,reason)=>this.onClose(ws,code,reason.toString()));
      });
      if(!this.stopped&&(this.state as ChatState)!=='entered')this.state='connected';
    }catch(error){this.scheduleReconnect(error instanceof Error?error.message:String(error))}
    finally{this.connecting=false}
  }

  private connectPayload(){const ticket=String(this.opts.cookie?.AuthTicket??'');return ticket?`${F}${ticket}${F.repeat(2)}16${F}`:`${F.repeat(3)}16${F}`}
  private joinPayload(){if(!this.live)return`${F}${F.repeat(5)}`;const chatNo=this.live.chatNo??'',ticket=String(this.opts.cookie?.AuthTicket??'');if(!ticket)return`${F}${chatNo}${F.repeat(5)}`;const ftk=this.live.ftk??'',params:[string,string][]=[['set_bps',String(this.live.bitrate??'')],['view_bps',String(this.live.bitrate??'')],['quality','normal'],['uuid',String(this.opts.cookie?._au??'')],['geo_cc',this.live.geoCountryCode??''],['geo_rc',this.live.geoRegionCode??''],['acpt_lang',this.live.acceptLanguage??''],['svc_lang',this.live.serviceLanguage??''],['subscribe','0'],['lowlatency','0'],['mode','landing']];const query=params.map(([k,v])=>`${SPACE}&${SPACE}${k}${SPACE}=${SPACE}${v}`).join(''),meta=`log${ELEMENT_START}${query}${ELEMENT_END}`+`pwd${ELEMENT_START}${ELEMENT_END}`+`auth_info${ELEMENT_START}${ticket}${ELEMENT_END}`+`pver${ELEMENT_START}1${ELEMENT_END}`+`access_system${ELEMENT_START}html5${ELEMENT_END}`;return`${F}${chatNo}${F}${ftk}${F}0${F}${meta}${F}`}

  private anomaly(kind:ProtocolAnomaly['kind'],detail:string,raw?:string,code?:number){const a:ProtocolAnomaly={kind,streamerId:this.streamerId,source:'native',receivedAt:new Date().toISOString(),detail,raw,code};this.emit('protocol-anomaly',a)}
  private onMessage(raw:string){
    this.lastInboundAt=Date.now();let packet;try{packet=parsePacket(raw)}catch(e){this.anomaly('parse-error',e instanceof Error?e.message:String(e),raw);return}
    if(!packet.lengthValid)this.anomaly('length-mismatch',`declared=${packet.declaredLength} actual=${packet.actualLength}`,raw,packet.code);
    const event=decodePacket(this.streamerId,packet,'native');if(event.category==='unknown')this.anomaly('unknown-code',`unclassified opcode ${packet.code}`,raw,packet.code);this.emit('event',event);
    if(packet.code===1)this.ws?.send(buildPacket(CMD_JOIN,this.joinPayload()));
    if(packet.code===2){this.stopEnterWatchdog();if(this.opts.cookie?.AuthTicket){const synAck=packet.parts[6];if(synAck)this.ws?.send(buildPacket(CMD_ENTER_INFO,`${F}${synAck}${F}0${F}`))}this.state='entered';this.resolveEntered();if(this.attempt){this.emitSynthetic(-5,'RECONNECTED',{totalAttempts:this.attempt});this.attempt=0}}
  }

  async waitUntilEntered(timeoutMs=10000){if(this.state==='entered')return;if(this.state==='closed'||this.state==='blocked')throw new Error(`connection ${this.state}`);return new Promise<void>((resolve,reject)=>{const timer=setTimeout(()=>{this.enteredWaiters=this.enteredWaiters.filter(x=>x.timer!==timer);reject(new Error('chat enter timeout'))},timeoutMs);this.enteredWaiters.push({resolve,reject,timer})})}
  private resolveEntered(){for(const w of this.enteredWaiters){clearTimeout(w.timer);w.resolve()}this.enteredWaiters=[]}
  private rejectEntered(error:Error){for(const w of this.enteredWaiters){clearTimeout(w.timer);w.reject(error)}this.enteredWaiters=[]}

  async sendChat(message:string){if(!this.opts.cookie?.AuthTicket)throw new Error('authenticated session required');if(!message||message.length>2000)throw new Error('invalid chat message');await this.waitUntilEntered();const ws=this.ws;if(!ws||ws.readyState!==WebSocket.OPEN)throw new Error('chat socket not connected');ws.send(buildPacket(CMD_CHAT,`${F}${message}${F.repeat(6)}`))}
  async sendWhisper(targetId:string,message:string){if(!this.opts.cookie?.AuthTicket)throw new Error('authenticated session required');if(!/^[A-Za-z0-9_-]{1,64}$/.test(targetId))throw new Error('invalid target id');if(!message||message.length>2000)throw new Error('invalid whisper message');await this.waitUntilEntered();const ws=this.ws;if(!ws||ws.readyState!==WebSocket.OPEN)throw new Error('chat socket not connected');ws.send(buildPacket(CMD_DIRECT_CHAT,`${F}${message}${F}${targetId}${F}`))}

  private emitSynthetic(code:number,type:string,payload:Record<string,unknown>){const event:CanonicalEvent={id:randomUUID(),streamerId:this.streamerId,code,type,description:type,category:'connection',supportLevel:'stable',source:'native',receivedAt:new Date().toISOString(),payload};this.emit('event',event)}
  private onClose(ws:WebSocket,code:number,reason:string){if(this.ws!==ws)return;this.stopHeartbeat();this.stopEnterWatchdog();this.ws=undefined;this.emitSynthetic(-3,'DISCONNECTED',{statusCode:code,reason,causedByError:code!==1000});if(!this.stopped)this.scheduleReconnect(reason||`close ${code}`)}

  private scheduleReconnect(reason:string){
    if(this.stopped||this.retry)return;this.stopHeartbeat();this.stopEnterWatchdog();const kind=classifyConnectionFailure(reason);this.attempt++;const delay=reconnectDelay(kind,this.attempt,this.opts.maxBackoffMs,this.opts.offlinePollMs);
    if(delay===null){this.state=kind==='protocol'?'protocol-error':'blocked';const error=new Error(reason);this.rejectEntered(error);this.emit('terminal',{reason,kind});return}
    this.state=kind==='offline'?'offline-wait':kind==='protocol'?'protocol-error':'reconnecting';
    this.retry=setTimeout(()=>{this.retry=undefined;void this.connect()},delay);this.emit('reconnect-scheduled',{attempt:this.attempt,delay,reason,kind});
  }
  private startEnterWatchdog(){this.stopEnterWatchdog();this.enterWatchdog=setTimeout(()=>{if(this.state!=='entered'&&!this.stopped){this.anomaly('join-timeout','JOIN_CHANNEL did not complete before watchdog');try{this.ws?.terminate()}catch{}}},this.opts.joinTimeoutMs)}
  private stopEnterWatchdog(){if(this.enterWatchdog)clearTimeout(this.enterWatchdog);this.enterWatchdog=undefined}
  private startHeartbeat(){this.stopHeartbeat();this.heartbeat=setInterval(()=>{const ws=this.ws;if(!ws||ws.readyState!==WebSocket.OPEN)return;const now=Date.now();if(this.state==='entered'&&this.lastInboundAt&&now-this.lastInboundAt>this.opts.livenessTimeoutMs){this.anomaly('liveness-timeout',`no inbound packet for ${now-this.lastInboundAt}ms`);try{ws.terminate()}catch{}return}try{ws.send(buildPacket(CMD_PING,F))}catch{}},this.opts.pingIntervalMs);this.heartbeat.unref?.()}
  private stopHeartbeat(){if(this.heartbeat)clearInterval(this.heartbeat);this.heartbeat=undefined}
  diagnostics(){return{state:this.state,attempt:this.attempt,lastInboundAt:this.lastInboundAt?new Date(this.lastInboundAt).toISOString():undefined,tlsVerification:!this.opts.allowInsecureTls}}
  async stop(){this.stopped=true;this.state='closed';this.stopHeartbeat();this.stopEnterWatchdog();if(this.retry)clearTimeout(this.retry);this.retry=undefined;this.rejectEntered(new Error('connection closed'));const ws=this.ws;this.ws=undefined;try{ws?.close(1000,'released')}catch{}}
}
