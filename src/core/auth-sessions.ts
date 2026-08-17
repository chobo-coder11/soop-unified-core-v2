import type { AppConfig } from '../config.js';
import type { SoopCookie } from '../http/soop-http.js';
import { SoopHttpClient } from '../http/soop-http.js';
import { NativeChatConnection } from './native-chat.js';
import type { Metrics } from './metrics.js';
import{createSessionToken,hashSessionToken,sessionRefFromHash}from'./session-token.js';

interface Session { tokenHash:string; ref:string; userId:string; cookie:SoopCookie; createdAt:number; expiresAt:number; connections:Map<string,NativeChatConnection> }
/**
 * In-memory credential/session vault.
 * Passwords are used only during login and are never retained.
 * Raw bearer session tokens are returned once to the caller and only their SHA-256 hashes
 * are stored internally, so the session listing can never expose a usable send-chat token.
 */
export class AuthSessionManager {
  private sessions=new Map<string,Session>();
  private http:SoopHttpClient;
  private sweep?:NodeJS.Timeout;

  constructor(private cfg:AppConfig,private metrics:Metrics){
    this.http=new SoopHttpClient(cfg.providerTimeoutMs);
    this.sweep=setInterval(()=>void this.cleanup(),60_000);
    this.sweep.unref?.();
  }

  enabled(){return this.cfg.enableWriteApi}

  async login(userId:string,password:string){
    if(!this.cfg.enableWriteApi)throw new Error('write API disabled');
    if(!/^[A-Za-z0-9_-]{1,64}$/.test(userId)||!password)throw new Error('invalid credentials');
    const cookie=await this.http.signIn(userId,password);
    const token=createSessionToken(),tokenHash=hashSessionToken(token),now=Date.now();
    const session:Session={tokenHash,ref:sessionRefFromHash(tokenHash),userId,cookie,createdAt:now,expiresAt:now+this.cfg.authSessionTtlMs,connections:new Map()};
    this.sessions.set(tokenHash,session);this.metrics.inc('soop_auth_sessions_created_total');
    return{sessionId:token,userId,expiresAt:new Date(session.expiresAt).toISOString()};
  }

  private get(sessionToken:string){const key=hashSessionToken(sessionToken),session=this.sessions.get(key);if(!session)throw new Error('invalid auth session');if(Date.now()>=session.expiresAt){void this.logout(sessionToken);throw new Error('auth session expired')}return session}

  async sendChat(sessionToken:string,streamerId:string,message:string){const c=await this.connection(this.get(sessionToken),streamerId);await c.sendChat(message);this.metrics.inc('soop_chat_messages_sent_total')}
  async sendWhisper(sessionToken:string,streamerId:string,targetId:string,message:string){const c=await this.connection(this.get(sessionToken),streamerId);await c.sendWhisper(targetId,message);this.metrics.inc('soop_whispers_sent_total')}

  private async connection(session:Session,streamerId:string){
    let conn=session.connections.get(streamerId);
    if(!conn){conn=new NativeChatConnection(streamerId,this.http,{maxBackoffMs:this.cfg.chatMaxBackoffMs,allowInsecureTls:this.cfg.allowInsecureTls,pingIntervalMs:this.cfg.chatPingIntervalMs,livenessTimeoutMs:this.cfg.chatLivenessTimeoutMs,joinTimeoutMs:this.cfg.chatJoinTimeoutMs,offlinePollMs:this.cfg.chatOfflinePollMs,cookie:session.cookie});session.connections.set(streamerId,conn);await conn.start()}
    await conn.waitUntilEntered();return conn;
  }

  async logout(sessionToken:string){const key=hashSessionToken(sessionToken),session=this.sessions.get(key);if(!session)return false;this.sessions.delete(key);await Promise.all([...session.connections.values()].map(c=>c.stop()));this.metrics.inc('soop_auth_sessions_destroyed_total');return true}
  list(){return[...this.sessions.values()].map(s=>({sessionRef:s.ref,userId:s.userId,createdAt:new Date(s.createdAt).toISOString(),expiresAt:new Date(s.expiresAt).toISOString(),connections:[...s.connections.keys()]}))}
  private async cleanup(){const now=Date.now();for(const [key,s] of [...this.sessions.entries()])if(now>=s.expiresAt){this.sessions.delete(key);await Promise.all([...s.connections.values()].map(c=>c.stop()));this.metrics.inc('soop_auth_sessions_destroyed_total')}}
  async close(){if(this.sweep)clearInterval(this.sweep);const sessions=[...this.sessions.values()];this.sessions.clear();await Promise.all(sessions.flatMap(s=>[...s.connections.values()].map(c=>c.stop())))}
}
