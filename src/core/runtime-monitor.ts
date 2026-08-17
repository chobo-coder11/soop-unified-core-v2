import type{Metrics}from'./metrics.js';
export class RuntimeMonitor{
 private timer?:NodeJS.Timeout;private expected=Date.now()+1000;private lastCpu=process.cpuUsage();private lastWall=process.hrtime.bigint();
 constructor(private metrics:Metrics,private intervalMs=1000){this.expected=Date.now()+intervalMs;this.timer=setInterval(()=>this.tick(),intervalMs);this.timer.unref?.()}
 private tick(){const now=Date.now(),lag=Math.max(0,now-this.expected);this.expected=now+this.intervalMs;const mem=process.memoryUsage();this.metrics.set('soop_runtime_event_loop_lag_ms',lag);this.metrics.set('soop_runtime_rss_bytes',mem.rss);this.metrics.set('soop_runtime_heap_used_bytes',mem.heapUsed);this.metrics.set('soop_runtime_external_bytes',mem.external);const wall=process.hrtime.bigint(),cpu=process.cpuUsage(this.lastCpu),wallUs=Number(wall-this.lastWall)/1000;this.lastCpu=process.cpuUsage();this.lastWall=wall;if(wallUs>0)this.metrics.set('soop_runtime_cpu_percent',Math.min(1000,((cpu.user+cpu.system)/wallUs)*100))}
 close(){if(this.timer)clearInterval(this.timer);this.timer=undefined}
}
