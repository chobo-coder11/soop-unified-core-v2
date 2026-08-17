import type { ProviderHealth, ProviderName } from '../types.js';

export class CircuitBreaker {
  private h: ProviderHealth;
  private halfOpenTrialInFlight=false;
  private openCount=0;
  private currentCooldownMs:number;

  constructor(
    name: ProviderName,
    enabled = true,
    private threshold = 3,
    private baseCooldownMs = 20_000,
    private maxCooldownMs = 5 * 60_000,
  ) {
    this.currentCooldownMs=baseCooldownMs;
    this.h = {
      name,
      state: enabled ? 'healthy' : 'disabled',
      enabled,
      successes: 0,
      failures: 0,
      consecutiveFailures: 0,
      openCount:0,
      currentCooldownMs:baseCooldownMs,
      halfOpenTrialInFlight:false,
    };
  }

  snapshot(): ProviderHealth {
    return { ...this.h,openCount:this.openCount,currentCooldownMs:this.currentCooldownMs,halfOpenTrialInFlight:this.halfOpenTrialInFlight };
  }

  private open(error?:unknown,latencyMs=0){
    this.h.state='open';
    this.h.latencyMs=latencyMs;
    this.halfOpenTrialInFlight=false;
    this.openCount++;
    const multiplier=2**Math.max(0,this.openCount-1);
    this.currentCooldownMs=Math.min(this.maxCooldownMs,this.baseCooldownMs*multiplier);
    this.h.openUntil=new Date(Date.now()+this.currentCooldownMs).toISOString();
    if(error!==undefined)this.h.lastError=error instanceof Error?error.message:String(error);
  }

  canRun(): boolean {
    if (!this.h.enabled) return false;
    if (this.h.state==='open') {
      if(this.h.openUntil&&Date.now()<Date.parse(this.h.openUntil))return false;
      this.h.state='half-open';
      this.h.openUntil=undefined;
    }
    if(this.h.state==='half-open'){
      if(this.halfOpenTrialInFlight)return false;
      this.halfOpenTrialInFlight=true;
      return true;
    }
    return true;
  }

  recordSuccess(latencyMs = 0): void {
    this.h.successes++;
    this.h.consecutiveFailures = 0;
    this.h.latencyMs = latencyMs;
    this.h.lastSuccessAt = new Date().toISOString();
    this.h.state = 'healthy';
    this.h.lastError = undefined;
    this.h.openUntil = undefined;
    this.halfOpenTrialInFlight=false;
    this.openCount=0;
    this.currentCooldownMs=this.baseCooldownMs;
  }

  recordFailure(error: unknown, latencyMs = 0): void {
    this.h.failures++;
    this.h.consecutiveFailures++;
    this.h.latencyMs = latencyMs;
    this.h.lastFailureAt = new Date().toISOString();
    this.h.lastError = error instanceof Error ? error.message : String(error);
    const wasHalfOpen=this.h.state==='half-open';
    this.halfOpenTrialInFlight=false;
    if (wasHalfOpen||this.h.consecutiveFailures >= this.threshold) this.open(error,latencyMs);
    else this.h.state = 'degraded';
  }

  async run<T>(fn: () => Promise<T>): Promise<T> {
    if (!this.h.enabled) throw new Error(`${this.h.name} disabled`);
    if (!this.canRun()) throw new Error(`${this.h.name} circuit open`);
    const started = Date.now();
    try {
      const value = await fn();
      this.recordSuccess(Date.now() - started);
      return value;
    } catch (error) {
      this.recordFailure(error, Date.now() - started);
      throw error;
    }
  }
}
