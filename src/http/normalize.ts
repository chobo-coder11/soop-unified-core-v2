/**
 * Strict SOOP wire-value normalization.
 *
 * SOOP endpoints mix booleans/numbers/strings (for example BPWD can be "0").
 * JavaScript truthiness/Number coercion is therefore unsafe for canonical data.
 */
export function nullableString(value:unknown):string|undefined{
  if(value===null||value===undefined)return undefined;
  const s=String(value).trim();
  return s? s:undefined;
}

export function nullableNumber(value:unknown):number|undefined{
  if(value===null||value===undefined)return undefined;
  if(typeof value==='string'&&!value.trim())return undefined;
  if(typeof value==='boolean')return undefined;
  const n=typeof value==='number'?value:Number(String(value).trim());
  return Number.isFinite(n)?n:undefined;
}

export function nullableInteger(value:unknown):number|undefined{
  const n=nullableNumber(value);
  return n!==undefined&&Number.isInteger(n)?n:undefined;
}

export function nullableBoolean(value:unknown):boolean|undefined{
  if(value===null||value===undefined)return undefined;
  if(typeof value==='boolean')return value;
  if(typeof value==='number'){
    if(value===1)return true;
    if(value===0)return false;
    return undefined;
  }
  const s=String(value).trim().toLowerCase();
  if(!s)return undefined;
  if(['1','true','yes','y','on'].includes(s))return true;
  if(['0','false','no','n','off'].includes(s))return false;
  return undefined;
}

/** Broadcast ids use zero/blank as "no broadcast" in several SOOP responses. */
export function broadcastId(value:unknown):string|undefined{
  const s=nullableString(value);
  if(!s||s==='0')return undefined;
  return s;
}

export interface NormalizedViewPreset{
  name?:string;
  label?:string;
  resolution?:string;
  bps?:number;
}

export function normalizeViewPresets(value:unknown):NormalizedViewPreset[]|undefined{
  if(!Array.isArray(value))return undefined;
  const out=value.map((raw:any)=>({
    name:nullableString(raw?.name),
    label:nullableString(raw?.label),
    resolution:nullableString(raw?.label_resolution??raw?.resolution),
    bps:nullableNumber(raw?.bps),
  })).filter(x=>x.name||x.label||x.resolution||x.bps!==undefined);
  return out.length?out:undefined;
}

/** Pick the browser-view bitrate when available; fall back to the broadcast bitrate. */
export function selectViewBps(presets:NormalizedViewPreset[]|undefined,broadcastBps:number|undefined):number|undefined{
  const preferred=presets?.find(x=>x.bps!==undefined)?.bps;
  return preferred??broadcastBps;
}

import type{ChannelSnapshot,LiveSnapshot}from'../types.js';

/** Runtime canonicalization for fallback providers that may return weakly typed JS values. */
export function canonicalizeLiveSnapshot(value:any,streamerId:string):LiveSnapshot{
  const bno=broadcastId(value?.bno),bitrate=nullableNumber(value?.bitrate),viewPresets=normalizeViewPresets(value?.viewPresets),wireOnline=nullableBoolean(value?.online);
  return{...value,streamerId,online:wireOnline??Boolean(bno),bno,previousBno:broadcastId(value?.previousBno),chatNo:broadcastId(value?.chatNo),streamerNickname:nullableString(value?.streamerNickname),title:nullableString(value?.title),category:nullableString(value?.category),viewerCount:nullableNumber(value?.viewerCount),startedSecondsAgo:nullableNumber(value?.startedSecondsAgo),passwordProtected:nullableBoolean(value?.passwordProtected),resolution:nullableString(value?.resolution),bitrate,viewPresets,selectedViewBps:nullableNumber(value?.selectedViewBps)??selectViewBps(viewPresets,bitrate),lowLatency:nullableBoolean(value?.lowLatency),thumbnailUrl:nullableString(value?.thumbnailUrl),channelDomain:nullableString(value?.channelDomain),channelPort:nullableNumber(value?.channelPort),ftk:nullableString(value?.ftk),geoCountryCode:nullableString(value?.geoCountryCode),geoRegionCode:nullableString(value?.geoRegionCode),acceptLanguage:nullableString(value?.acceptLanguage),serviceLanguage:nullableString(value?.serviceLanguage)};
}

export function canonicalizeChannelSnapshot(value:any,streamerId:string):ChannelSnapshot{
  const bn=nullableNumber(value?.broadNo),broadNo=bn!==undefined&&Number.isInteger(bn)&&bn>0?bn:undefined;
  return{...value,streamerId,nickname:nullableString(value?.nickname),stationName:nullableString(value?.stationName),stationTitle:nullableString(value?.stationTitle),profileImage:nullableString(value?.profileImage),favorites:nullableNumber(value?.favorites),subscribers:nullableNumber(value?.subscribers),totalViewCount:nullableNumber(value?.totalViewCount),currentViewerCount:nullableNumber(value?.currentViewerCount),broadNo,broadTitle:nullableString(value?.broadTitle),isPassword:nullableBoolean(value?.isPassword),explanation:nullableString(value?.explanation)};
}
