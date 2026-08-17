import type{ChannelSnapshot,LiveSnapshot,ProviderName,ProviderObservation,UnifiedResult}from'../types.js';

type WeightResolver=(provider:ProviderName,observation:ProviderObservation<unknown>)=>number;
const fallbackWeights:Record<ProviderName,number>={native:1,reindeer:.9,soopapi:.97,soop4j:.9,soopjs:.55};
const weightOf=(o:ProviderObservation<unknown>,resolver?:WeightResolver)=>Math.max(.01,resolver?resolver(o.provider,o):fallbackWeights[o.provider]);
const median=(xs:number[])=>{const a=[...xs].sort((x,y)=>x-y);if(!a.length)return undefined;const m=Math.floor(a.length/2);return a.length%2?a[m]:(a[m-1]+a[m])/2};
const weightedMedian=(items:Array<{value:number;weight:number}>)=>{const a=[...items].sort((x,y)=>x.value-y.value),total=a.reduce((s,x)=>s+x.weight,0);let c=0;for(const x of a){c+=x.weight;if(c>=total/2)return x.value}return a.at(-1)?.value};
const sourcePick=<T>(o:ProviderObservation<T>[],resolver?:WeightResolver)=>o.filter(x=>x.ok&&x.value).sort((a,b)=>weightOf(b as any,resolver)-weightOf(a as any,resolver))[0];
const groups=<T>(good:Array<ProviderObservation<T>>)=>({implementationGroups:new Set(good.map(x=>x.provenance?.independenceGroup??x.provider)).size,upstreamFamilies:new Set(good.map(x=>x.provenance?.upstreamFamily??x.provider)).size});

function robustViewer<T>(good:Array<ProviderObservation<T>&{value:T}>,field:(v:T)=>number|undefined,resolver?:WeightResolver){
 const raw=good.map(o=>({provider:o.provider,value:field(o.value),weight:weightOf(o as any,resolver)})).filter((x):x is {provider:ProviderName;value:number;weight:number}=>Number.isFinite(x.value));
 if(!raw.length)return{value:undefined,outliers:[] as ProviderName[]};
 if(raw.length<3)return{value:weightedMedian(raw),outliers:[] as ProviderName[]};
 const m=median(raw.map(x=>x.value))!,dev=raw.map(x=>Math.abs(x.value-m)),mad=median(dev)??0;
 const tolerance=mad>0?Math.max(5,mad*4):Math.max(20,Math.abs(m)*.2);
 const kept=raw.filter(x=>Math.abs(x.value-m)<=tolerance),outliers=raw.filter(x=>Math.abs(x.value-m)>tolerance).map(x=>x.provider);
 return{value:weightedMedian(kept.length?kept:raw),outliers};
}

function confidence<T>(good:Array<ProviderObservation<T>>,agreement:number,totalWeight:number,status:'confirmed'|'uncertain'|'single-source',resolver?:WeightResolver){
 const maxExpected=3.2,weightFactor=Math.min(1,totalWeight/maxExpected),g=groups(good),implFactor=Math.min(1,g.implementationGroups/3),upstreamFactor=Math.min(1,.55+.2*Math.max(0,g.upstreamFamilies-1));
 let c=.08+weightFactor*.34+agreement*.34+implFactor*.16+upstreamFactor*.08;
 if(status==='single-source')c=Math.min(c,.55);if(status==='uncertain')c=Math.min(c,.49);
 return Math.max(.05,Math.min(.999,c));
}

export function liveConsensus(o:ProviderObservation<LiveSnapshot>[],resolver?:WeightResolver):UnifiedResult<LiveSnapshot>{
 const good=o.filter(x=>x.ok&&x.value) as Array<ProviderObservation<LiveSnapshot>&{value:LiveSnapshot}>;
 if(!good.length)throw new Error('All live providers failed');
 const p=sourcePick(o,resolver)!;const base={...p.value!};
 const onlineWeight=good.filter(x=>x.value.online).reduce((s,x)=>s+weightOf(x as any,resolver),0),offlineWeight=good.filter(x=>!x.value.online).reduce((s,x)=>s+weightOf(x as any,resolver),0),totalWeight=onlineWeight+offlineWeight;
 const margin=totalWeight?Math.abs(onlineWeight-offlineWeight)/totalWeight:0;
 const single=good.length===1,uncertain=!single&&margin<.18;
 const onlineState=uncertain?'uncertain':onlineWeight>=offlineWeight?'online':'offline';
 if(!uncertain)base.online=onlineState==='online';
 const viewer=robustViewer(good,v=>v.viewerCount,resolver);if(viewer.value!==undefined)base.viewerCount=viewer.value;
 const winningWeight=Math.max(onlineWeight,offlineWeight),agreement=totalWeight?winningWeight/totalWeight:0;
 const status=single?'single-source':uncertain?'uncertain':'confirmed';const g=groups(good);
 return{data:base,confidence:confidence(good,agreement,totalWeight,status,resolver),source:p.provider,corroboratedBy:good.filter(x=>x.provider!==p.provider&&(!uncertain&&x.value.online===base.online)).map(x=>x.provider),observations:o,observedAt:new Date().toISOString(),consensus:{status,onlineState,agreement,totalWeight,winningWeight,sourceCount:good.length,implementationGroups:g.implementationGroups,upstreamFamilies:g.upstreamFamilies,reason:uncertain?'provider votes are too close to call safely':single?'only one provider returned usable data':undefined,outlierProviders:viewer.outliers}};
}

export function channelConsensus(o:ProviderObservation<ChannelSnapshot>[],resolver?:WeightResolver):UnifiedResult<ChannelSnapshot>{
 const good=o.filter(x=>x.ok&&x.value) as Array<ProviderObservation<ChannelSnapshot>&{value:ChannelSnapshot}>;
 if(!good.length)throw new Error('All channel providers failed');
 const p=sourcePick(o,resolver)!,base={...p.value!},viewer=robustViewer(good,v=>v.currentViewerCount,resolver);if(viewer.value!==undefined)base.currentViewerCount=viewer.value;
 const ranked=[...good].sort((a,b)=>weightOf(b as any,resolver)-weightOf(a as any,resolver));for(const key of['nickname','stationName','stationTitle','profileImage','explanation']as const)if(!base[key])base[key]=ranked.map(x=>x.value[key]).find(Boolean) as any;
 const totalWeight=good.reduce((s,x)=>s+weightOf(x as any,resolver),0),status=good.length===1?'single-source':'confirmed',g=groups(good),agreement=good.length>1?.96:.7;
 return{data:base,confidence:confidence(good,agreement,totalWeight,status,resolver),source:p.provider,corroboratedBy:good.filter(x=>x.provider!==p.provider).map(x=>x.provider),observations:o,observedAt:new Date().toISOString(),consensus:{status,agreement,totalWeight,winningWeight:totalWeight,sourceCount:good.length,implementationGroups:g.implementationGroups,upstreamFamilies:g.upstreamFamilies,reason:good.length===1?'only one provider returned usable data':undefined,outlierProviders:viewer.outliers}};
}
