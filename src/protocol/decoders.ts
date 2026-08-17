import{randomUUID}from'node:crypto';import{eventDescriptor}from'./catalog.js';import type{CanonicalEvent}from'../types.js';import type{ParsedPacket}from'./packet.js';
const n=(v:string|undefined,f=0)=>{const x=Number(v);return Number.isFinite(x)?x:f};
const j=(v:string|undefined):unknown=>{if(!v)return{};try{return JSON.parse(v)}catch{return{text:v}}};
const o=(e:[string,unknown][])=>Object.fromEntries(e.filter(([,v])=>v!==undefined&&v!==''));
export function decodePacket(streamerId:string,p:ParsedPacket,source:'native'|'reindeer'='native'):CanonicalEvent{
 const d=eventDescriptor(p.code),a=p.parts;const e:CanonicalEvent={id:randomUUID(),streamerId,code:p.code,type:d.name,description:d.description,category:d.category,supportLevel:d.supportLevel,source,receivedAt:new Date().toISOString(),payload:{parts:a},raw:p.raw};
 switch(p.code){
  case 0:e.payload={kind:'keepAlive'};break;
  case 1:e.payload=o([['userId',a[0]],['syn',a[1]]]);break;
  case 2:e.payload=o([['chatNo',a[0]],['bjId',a[1]],['maxSubBjCount',n(a[2])],['familyNickname',a[3]],['userFlag',a[4]],['synAck',a[6]]]);break;
  case 3:e.user={nickname:a[2]};e.payload=o([['quitType',n(a[0])],['adminKickCount',n(a[1])],['nickname',a[2]],['bannedRoomBjId',a[3]],['bannedRoomBjNickname',a[4]]]);break;
  case 4:e.payload={changeType:a[0],rawUsers:a,userIds:a.filter((_,i)=>i%2===0).filter(Boolean)};break;
  case 5:e.message=a[0];e.user={id:a[1],nickname:a[5],flags:a[6],subscriptionMonth:a[7]};e.payload=o([['message',a[0]],['senderId',a[1]],['type',n(a[3])],['chatLang',n(a[4])],['senderNickname',a[5]],['senderFlag',a[6]],['subscriptionMonth',a[7]],['nicknameColor',a[8]],['nicknameColorDark',a[9]]]);break;
  case 8:e.user={id:a[0],nickname:a[7]};e.moderation={action:'mute',durationSeconds:n(a[2]),adminId:a[4]};e.payload=o([['userInfo',a[1]],['dumbCount',n(a[3])],['adminType',n(a[5])],['extraInfo',a[6]]]);break;
  case 9:e.message=a[0];e.user={id:a[1],nickname:a[4]};e.target={id:a[2],nickname:a[5]};e.payload=o([['type',n(a[3])],['flag',a[6]]]);break;
  case 11:e.user={id:a[0],nickname:a[1]};e.moderation={action:'kick',reason:a[3]};e.payload=o([['kickType',n(a[2])],['kickerNickname',a[4]]]);break;
  case 18:case 33:e.user={id:a[1],nickname:a[2]};e.target={id:a[0]};e.donation={kind:p.code===18?'star_balloon':'star_balloon_sub',amount:n(a[3]),fanOrder:n(a[4]),extra:o([['fileName',a[5]],['isDefault',a[6]],['isTopFan',a[7]],['ttsData',a[8]]])};e.payload={bjId:a[0],senderId:a[1],senderNickname:a[2],count:n(a[3]),fanOrder:n(a[4])};break;
  case 20:case 34:e.user={id:a[2],nickname:a[3]};e.target={id:a[0],nickname:a[1]};e.donation={kind:p.code===20?'fan_letter':'fan_letter_sub',amount:n(a[5]),extra:{type:n(a[4]),supporterOrder:a[6]}};e.payload={parts:a};break;
  case 23:e.moderation={action:'slow_mode',durationSeconds:n(a[0])};e.payload={seconds:n(a[0]),parts:a};break;
  case 25:e.user={id:a[0],nickname:a[1]};e.moderation={action:'blind_kick',durationSeconds:n(a[2])};break;
  case 26:e.message=a[0];e.user={id:a[1],nickname:a[4],flags:a[5],subscriptionMonth:a[6]};e.payload=o([['isAdmin',n(a[2])],['chatLang',n(a[3])]]);break;
  case 37:case 38:e.user={id:a[1],nickname:a[2]};e.target={id:a[0]};e.donation={kind:'chocolate',amount:n(a[3])};e.payload={parts:a};break;
  case 45:e.user={id:a[0],nickname:a[1]};e.target={id:a[2],nickname:a[3]};e.payload={itemType:n(a[4])};break;
  case 50:e.payload={poll:a};break;
  case 54:e.moderation={action:'ban_words'};e.payload={replaceWord:a[0],banWordList:a.slice(1).filter(Boolean)};break;
  case 58:e.message=a[0];e.payload={message:a[0]};break;
  case 70:case 71:e.user={id:a[2],nickname:a[3]};e.target={id:a[1]};e.payload={goodsType:n(a[0]),goodsName:a[4],goodsCount:n(a[5]),relay:n(a[6])};break;
  case 76:e.user={id:a[1],nickname:a[2]};e.moderation={action:'kick_and_cancel'};e.payload={status:n(a[0])};break;
  case 77:{const kickedUsers=[];for(let i=0;i+5<a.length;i+=6)if(a[i])kickedUsers.push({userId:a[i],userNickname:a[i+1],time:a[i+2],orderUserId:a[i+3],orderUserNickname:a[i+4],orderUserFlag:a[i+5]});e.payload={kickedUsers,parts:a};break;}
  case 79:e.user={id:a[1]};e.moderation={action:'spam_info'};e.payload={dobaeInfo:n(a[0])};break;
  case 86:e.user={id:a[1],nickname:a[2]};e.target={id:a[0]};e.donation={kind:'vod_balloon',amount:n(a[3])};break;
  case 87:e.user={id:a[2],nickname:a[3]};e.target={id:a[1]};e.message=a[4];e.donation={kind:'adcon',amount:n(a[9]),fanOrder:n(a[10]),extra:{message2:a[5],title:a[6],urlImg:a[7],urlDefault:a[8],isTopFan:n(a[11]),isFanChief:n(a[12]),isSubRoom:n(a[13])}};break;
  case 90:e.moderation={action:'kick_message_state'};e.payload={chatNo:a[0],hideKickMessage:a[1]==='1'||a[1]==='true'};break;
  case 91:e.user={id:a[2],nickname:a[3]};e.target={id:a[1]};e.payload={chatNo:n(a[0]),type:n(a[4])};break;
  case 93:e.user={id:a[1],nickname:a[2]};e.target={id:a[0]};e.payload={month:n(a[3]),chatNo:n(a[4])};break;
  case 95:e.message=a[0];e.payload={translation:a};break;
  case 102:e.user={id:a[0],nickname:a[1]};e.target={id:a[2],nickname:a[3]};e.donation={kind:'gift_ticket',extra:{ticketData:a[4]}};break;
  case 104:e.message=a.join(' ').trim();e.payload={notice:a};break;
  case 105:e.user={id:a[2],nickname:a[3]};e.target={id:a[1]};e.donation={kind:'video_balloon',amount:n(a[4]),fanOrder:n(a[5]),extra:{chatNo:a[0],isTopFan:n(a[6]),relay:a[7],fileName:a[8],isDefault:a[9],extraData:a[10]}};break;
  case 107:e.user={id:a[1],nickname:a[2]};e.target={id:a[0]};e.donation={kind:'station_adcon',amount:n(a[3]),extra:{isDefault:a[4],message:a[5],chatNumber:a[6]}};break;
  case 108:e.user={id:a[0],nickname:a[1]};e.target={id:a[2],nickname:a[3]};e.donation={kind:'subscription_gift',itemCode:a[7],extra:{subscriptionId:a[4],subscriptionNickname:a[5],itemType:n(a[6]),isSubscription:n(a[8]),subscriptionType:a[9],subscriptionPeriod:a[10],subscriptionRemain:n(a[11]),subscriptionPaycount:n(a[12])}};break;
  case 109:e.message=a[1];e.payload={chatNo:a[0],message:a[1],groupId:a[2],subId:a[3],version:a[4],userInfo:a[5],color:a[6],chatLang:a[7],type:a[8]};break;
  case 111:e.target={id:a[0]};e.payload={dropsName:a[1],dropsMsg:a[2],dropsImgUrl:a[3]};break;
  case 118:e.user={id:a[0],nickname:a[1]};e.target={id:a[2],nickname:a[3]};e.donation={kind:'ogq_emoticon_gift',extra:{title:a[4],imageUrl:a[5]}};break;
  case 119:e.payload={data:j(a[0])};break;
  case 120:e.target={id:a[0],nickname:a[1]};e.donation={kind:'gem_item',extra:{itemName:a[2]}};break;
  case 121:e.payload={data:j(a[0]??a.join(''))};break;
  case 122:e.message=a[0];e.payload={caption:a};break;
  case 125:e.payload={data:j(a[0]??a.join(''))};break;
  case 127:e.payload={subscriberStatus:a};break;
  default:e.payload={parts:a};
 }
 return e;
}
