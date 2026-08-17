type Labels=Record<string,string|number|boolean>;
interface Series{value:number;labels:Labels}
interface Histogram{labels:Labels;buckets:number[];counts:number[];sum:number;count:number}
const key=(name:string,labels:Labels={})=>`${name}|${Object.entries(labels).sort(([a],[b])=>a.localeCompare(b)).map(([k,v])=>`${k}=${String(v)}`).join(',')}`;
const esc=(v:unknown)=>String(v).replace(/\\/g,'\\\\').replace(/"/g,'\\"').replace(/\n/g,'\\n');
const fmtLabels=(labels:Labels)=>{const e=Object.entries(labels);return e.length?`{${e.map(([k,v])=>`${k}="${esc(v)}"`).join(',')}}`:''};
const metricName=(n:string)=>n.replace(/[^a-zA-Z0-9_:]/g,'_');

export class Metrics{
 private counters=new Map<string,{name:string}&Series>();private gauges=new Map<string,{name:string}&Series>();private histograms=new Map<string,{name:string}&Histogram>();
 inc(n:string,by=1){this.incLabel(n,{},by)}
 incLabel(n:string,labels:Labels={},by=1){const k=key(n,labels),x=this.counters.get(k);if(x)x.value+=by;else this.counters.set(k,{name:n,labels:{...labels},value:by})}
 set(n:string,v:number){this.setLabel(n,{},v)}
 setLabel(n:string,labels:Labels={},v:number){this.gauges.set(key(n,labels),{name:n,labels:{...labels},value:v})}
 observe(n:string,v:number,labels:Labels={},buckets=[5,10,25,50,100,250,500,1000,2500,5000,10000]){if(!Number.isFinite(v))return;const k=key(n,labels);let h=this.histograms.get(k);if(!h){h={name:n,labels:{...labels},buckets:[...buckets].sort((a,b)=>a-b),counts:Array(buckets.length).fill(0),sum:0,count:0};this.histograms.set(k,h)}h.count++;h.sum+=v;for(let i=0;i<h.buckets.length;i++)if(v<=h.buckets[i])h.counts[i]++}
 json(){return{counters:Object.fromEntries([...this.counters].map(([k,v])=>[k,{value:v.value,labels:v.labels}])),gauges:Object.fromEntries([...this.gauges].map(([k,v])=>[k,{value:v.value,labels:v.labels}])),histograms:Object.fromEntries([...this.histograms].map(([k,v])=>[k,{count:v.count,sum:v.sum,buckets:v.buckets.map((le,i)=>({le,count:v.counts[i]})),labels:v.labels}]))}}
 prometheus(){const l:string[]=[];for(const x of this.counters.values())l.push(`${metricName(x.name)}${fmtLabels(x.labels)} ${x.value}`);for(const x of this.gauges.values())l.push(`${metricName(x.name)}${fmtLabels(x.labels)} ${x.value}`);for(const h of this.histograms.values()){for(let i=0;i<h.buckets.length;i++)l.push(`${metricName(h.name)}_bucket${fmtLabels({...h.labels,le:h.buckets[i]})} ${h.counts[i]}`);l.push(`${metricName(h.name)}_bucket${fmtLabels({...h.labels,le:'+Inf'})} ${h.count}`);l.push(`${metricName(h.name)}_sum${fmtLabels(h.labels)} ${h.sum}`);l.push(`${metricName(h.name)}_count${fmtLabels(h.labels)} ${h.count}`)}return l.join('\n')+'\n'}
}
