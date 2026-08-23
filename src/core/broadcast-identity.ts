import type{BroadcastIdentityAssessment,ChannelSnapshot,LiveSnapshot,UnifiedResult}from'../types.js';

export function assessBroadcastIdentity(live:UnifiedResult<LiveSnapshot>|undefined,channel:UnifiedResult<ChannelSnapshot>|undefined,revalidated=false):BroadcastIdentityAssessment{
 const liveBno=live?.data.bno,channelBroadNo=channel?.data.broadNo!==undefined?String(channel.data.broadNo):undefined,generation=live?.broadcastGeneration?.generation,generationChanged=live?.broadcastGeneration?.changed;
 if(live&&!live.data.online&&!liveBno&&!channelBroadNo)return{status:'offline',liveBno,channelBroadNo,generation,generationChanged,revalidated,confidence:.97,reason:'live evidence is offline and no active broadcast id is present'};
 if(liveBno&&channelBroadNo&&liveBno===channelBroadNo)return{status:'matched',liveBno,channelBroadNo,generation,generationChanged,revalidated,confidence:Math.min(.999,Math.max(.7,(live!.confidence+channel!.confidence)/2)),reason:'live BNO matches station broadNo'};
 if(liveBno&&channelBroadNo&&liveBno!==channelBroadNo)return{status:'mismatch',liveBno,channelBroadNo,generation,generationChanged,revalidated,confidence:.15,reason:'live BNO and station broadNo identify different broadcasts'};
 if(liveBno)return{status:'live-only',liveBno,channelBroadNo,generation,generationChanged,revalidated,confidence:Math.min(.72,live?.confidence??.5),reason:'only live endpoint supplied a broadcast id'};
 if(channelBroadNo)return{status:'channel-only',liveBno,channelBroadNo,generation,generationChanged,revalidated,confidence:Math.min(.65,channel?.confidence??.5),reason:'only station endpoint supplied a broadcast id'};
 return{status:'unknown',liveBno,channelBroadNo,generation,generationChanged,revalidated,confidence:.25,reason:'no broadcast identity evidence available'};
}
