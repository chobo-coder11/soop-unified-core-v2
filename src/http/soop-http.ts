import { DEFAULT_BASE_URLS, DEFAULT_USER_AGENT } from '../protocol/constants.js';
import type { ChannelSnapshot, LiveSnapshot } from '../types.js';
import { broadcastId, normalizeViewPresets, nullableBoolean, nullableNumber, nullableString, selectViewBps } from './normalize.js';

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
    const bno=broadcastId(x.BNO),previousBno=broadcastId(x.PBNO),result=nullableNumber(x.RESULT);
    const bitrate=nullableNumber(x.BPS),viewPresets=normalizeViewPresets(x.VIEWPRESET);
    const online=(result??0)!==0&&Boolean(bno);
    return {
      streamerId:id,online,bno,previousBno,chatNo:broadcastId(x.CHATNO),
      streamerNickname:nullableString(x.BJNICK),title:nullableString(x.TITLE),category:nullableString(x.CATE),
      viewerCount:nullableNumber(x.CTUSER),startedSecondsAgo:nullableNumber(x.BTIME),passwordProtected:nullableBoolean(x.BPWD),
      resolution:nullableString(x.RESOLUTION),bitrate,viewPresets,selectedViewBps:selectViewBps(viewPresets,bitrate),lowLatency:nullableBoolean(x.LOWLAYTENCYBJ),
      channelDomain:nullableString(x.CHDOMAIN),channelPort:nullableNumber(x.CHPT),ftk:nullableString(x.FTK),
      geoCountryCode:nullableString(x.geo_cc),geoRegionCode:nullableString(x.geo_rc),acceptLanguage:nullableString(x.acpt_lang),serviceLanguage:nullableString(x.svc_lang),
      thumbnailUrl:bno?`https://liveimg.sooplive.co.kr/h/${bno}.webp`:undefined,raw:json,
    };
  }

  async station(id:string):Promise<ChannelSnapshot>{
    const response=await this.request(`${DEFAULT_BASE_URLS.channel}/api/${encodeURIComponent(id)}/station`);
    if(!response.ok)throw new Error(`channel HTTP ${response.status}`);
    const json:any=await response.json(),s=json?.station??{},b=json?.broad??{},u=s?.upd??json?.upd??{};
    const broadNoRaw=nullableNumber(b.broad_no),broadNo=broadNoRaw!==undefined&&Number.isInteger(broadNoRaw)&&broadNoRaw>0?broadNoRaw:undefined;
    return{streamerId:id,nickname:nullableString(s.user_nick),stationName:nullableString(s.station_name),stationTitle:nullableString(s.station_title),profileImage:nullableString(json?.profile_image),
      favorites:nullableNumber(u.fan_cnt),subscribers:nullableNumber(json?.subscription?.total),totalViewCount:nullableNumber(u.total_view_cnt),currentViewerCount:nullableNumber(b.current_sum_viewer),
      broadNo,broadTitle:nullableString(b.broad_title),isPassword:nullableBoolean(b.is_password),raw:json};
  }

}
