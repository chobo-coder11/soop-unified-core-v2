import { DEFAULT_BASE_URLS, DEFAULT_USER_AGENT } from '../protocol/constants.js';
import type { ChannelSnapshot, LiveSnapshot } from '../types.js';

export interface SoopCookie { [key: string]: string | number | undefined }

export class SoopHttpClient {
  constructor(private timeoutMs = 4500) {}

  private async request(url: string, init: RequestInit = {}): Promise<Response> {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), this.timeoutMs);
    try {
      return await fetch(url, {
        ...init,
        signal: controller.signal,
        headers: { 'User-Agent': DEFAULT_USER_AGENT, ...init.headers },
      });
    } finally { clearTimeout(timer); }
  }

  async signIn(userId: string, password: string): Promise<SoopCookie> {
    const form = new FormData();
    form.append('szWork', 'login');
    form.append('szType', 'json');
    form.append('szUid', userId);
    form.append('szPassword', password);
    const response = await this.request(`${DEFAULT_BASE_URLS.auth}/app/LoginAction.php`, { method: 'POST', body: form });
    if (!response.ok) throw new Error(`auth HTTP ${response.status}`);

    const headers: any = response.headers;
    const setCookies: string[] = typeof headers.getSetCookie === 'function'
      ? headers.getSetCookie()
      : [response.headers.get('set-cookie') ?? ''].filter(Boolean);
    const cookies: SoopCookie = {};
    for (const line of setCookies) {
      const first = line.split(';', 1)[0];
      const eq = first.indexOf('=');
      if (eq <= 0) continue;
      const key = first.slice(0, eq).trim();
      const value = first.slice(eq + 1).trim();
      if (key) cookies[key] = value;
    }
    if (!cookies.AuthTicket) throw new Error('SOOP login did not return AuthTicket');
    return cookies;
  }

  async liveDetail(id: string, cookie?: SoopCookie): Promise<LiveSnapshot> {
    const body = new URLSearchParams({ bid:id,type:'live',pwd:'',player_type:'html5',stream_type:'common',quality:'HD',mode:'landing',from_api:'0',is_revive:'false' });
    const headers: Record<string,string> = { 'Content-Type':'application/x-www-form-urlencoded' };
    if (cookie) headers.Cookie = Object.entries(cookie).filter(([,v])=>v!==undefined).map(([k,v])=>`${k}=${encodeURIComponent(String(v))}`).join('; ');
    const response = await this.request(`${DEFAULT_BASE_URLS.live}/afreeca/player_live_api.php?bjid=${encodeURIComponent(id)}`, { method:'POST', headers, body });
    if (!response.ok) throw new Error(`live HTTP ${response.status}`);
    const json: any = await response.json();
    const x = json?.CHANNEL ?? {};
    const online = Number(x.RESULT)!==0 && Boolean(x.BNO);
    return {
      streamerId:id,online,bno:x.BNO?String(x.BNO):undefined,chatNo:x.CHATNO?String(x.CHATNO):undefined,
      streamerNickname:x.BJNICK,title:x.TITLE,category:x.CATE,
      viewerCount:Number.isFinite(Number(x.CTUSER))?Number(x.CTUSER):undefined,
      startedSecondsAgo:Number.isFinite(Number(x.BTIME))?Number(x.BTIME):undefined,passwordProtected:Boolean(x.BPWD),
      resolution:x.RESOLUTION,bitrate:Number.isFinite(Number(x.BPS))?Number(x.BPS):undefined,
      channelDomain:x.CHDOMAIN,channelPort:Number.isFinite(Number(x.CHPT))?Number(x.CHPT):undefined,ftk:x.FTK,
      geoCountryCode:x.geo_cc,geoRegionCode:x.geo_rc,acceptLanguage:x.acpt_lang,serviceLanguage:x.svc_lang,
      thumbnailUrl:x.BNO?`https://liveimg.sooplive.co.kr/h/${x.BNO}.webp`:undefined,raw:json,
    };
  }

  async station(id:string):Promise<ChannelSnapshot>{
    const response=await this.request(`${DEFAULT_BASE_URLS.channel}/api/${encodeURIComponent(id)}/station`);
    if(!response.ok)throw new Error(`channel HTTP ${response.status}`);
    const json:any=await response.json(),s=json?.station??{},b=json?.broad??{},u=s?.upd??json?.upd??{};
    return{streamerId:id,nickname:s.user_nick,stationName:s.station_name,stationTitle:s.station_title,profileImage:json?.profile_image,
      favorites:Number.isFinite(Number(u.fan_cnt))?Number(u.fan_cnt):undefined,subscribers:Number.isFinite(Number(json?.subscription?.total))?Number(json.subscription.total):undefined,
      totalViewCount:Number.isFinite(Number(u.total_view_cnt))?Number(u.total_view_cnt):undefined,currentViewerCount:Number.isFinite(Number(b.current_sum_viewer))?Number(b.current_sum_viewer):undefined,
      broadNo:Number.isFinite(Number(b.broad_no))?Number(b.broad_no):undefined,broadTitle:b.broad_title,isPassword:Boolean(b.is_password),raw:json};
  }
}
