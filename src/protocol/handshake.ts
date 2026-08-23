import type{LiveSnapshot}from'../types.js';
import type{SoopCookie}from'../http/soop-http.js';
import{ELEMENT_END,ELEMENT_START,F,SPACE}from'./constants.js';

export type HandshakeProfile='legacy-v1-ticket'|'browser-v2-null';

export function buildConnectPayload(cookie?:SoopCookie){const ticket=String(cookie?.AuthTicket??'');return ticket?`${F}${ticket}${F.repeat(2)}16${F}`:`${F.repeat(3)}16${F}`}

/**
 * Build authenticated JOIN metadata using one of two observed SOOP browser-compatible profiles.
 * legacy-v1-ticket preserves the previously validated core behavior.
 * browser-v2-null mirrors the current reindeer develop implementation and is used only as a fallback.
 */
export function buildJoinPayload(live:LiveSnapshot|undefined,cookie:SoopCookie|undefined,profile:HandshakeProfile){
 if(!live)return`${F}${F.repeat(5)}`;const chatNo=live.chatNo??'',ticket=String(cookie?.AuthTicket??'');if(!ticket)return`${F}${chatNo}${F.repeat(5)}`;
 const ftk=live.ftk??'',viewBps=live.selectedViewBps??live.bitrate,params:[string,string][]=[['set_bps',String(live.bitrate??'')],['view_bps',String(viewBps??'')],['quality','normal'],['uuid',String(cookie?._au??'')],['geo_cc',live.geoCountryCode??''],['geo_rc',live.geoRegionCode??''],['acpt_lang',live.acceptLanguage??''],['svc_lang',live.serviceLanguage??''],['subscribe','0'],['lowlatency','0'],['mode','landing']];
 const query=params.map(([k,v])=>`${SPACE}&${SPACE}${k}${SPACE}=${SPACE}${v}`).join(''),browser=profile==='browser-v2-null',authInfo=browser?'NULL':ticket,pver=browser?'2':'1',meta=`log${ELEMENT_START}${query}${ELEMENT_END}`+`pwd${ELEMENT_START}${ELEMENT_END}`+`auth_info${ELEMENT_START}${authInfo}${ELEMENT_END}`+`pver${ELEMENT_START}${pver}${ELEMENT_END}`+`access_system${ELEMENT_START}html5${ELEMENT_END}`;return`${F}${chatNo}${F}${ftk}${F}0${F}${meta}${F}`;
}
