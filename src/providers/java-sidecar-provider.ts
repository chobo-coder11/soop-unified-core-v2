import type { ChannelSnapshot, LiveSnapshot, ProviderObservation, ProviderName } from '../types.js';
import { CircuitBreaker } from '../core/circuit-breaker.js';
import { PROVIDER_PROVENANCE } from '../core/provider-provenance.js';

export class JavaSidecarProvider {
  private breakers: { soopapi: CircuitBreaker; soop4j: CircuitBreaker };

  constructor(private baseUrl: string, private enabled: boolean, private timeoutMs: number) {
    this.breakers = {
      soopapi: new CircuitBreaker('soopapi', enabled),
      soop4j: new CircuitBreaker('soop4j', enabled),
    };
  }

  health() { return [this.breakers.soopapi.snapshot(), this.breakers.soop4j.snapshot()]; }

  private async fetchJson(path: string) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), this.timeoutMs);
    try {
      const response = await fetch(`${this.baseUrl}${path}`, { signal: controller.signal });
      if (!response.ok) throw new Error(`sidecar HTTP ${response.status}`);
      return await response.json();
    } finally { clearTimeout(timer); }
  }

  live(id: string) { return this.query<LiveSnapshot>('live', id); }
  channel(id: string) { return this.query<ChannelSnapshot>('channel', id); }

  private async query<T>(kind: string, id: string): Promise<ProviderObservation<T>[]> {
    const names = ['soopapi', 'soop4j'] as const;
    const observedAt = () => new Date().toISOString();
    if (!this.enabled) {
      return names.map(provider => ({ provider, ok: false, latencyMs: 0, observedAt: observedAt(), error: 'disabled', provenance: PROVIDER_PROVENANCE[provider] }));
    }

    // If both circuits are open, avoid pointlessly calling the sidecar.
    const runnable = names.filter(name => this.breakers[name].canRun());
    if (!runnable.length) {
      return names.map(provider => ({ provider, ok: false, latencyMs: 0, observedAt: observedAt(), error: 'circuit open', provenance: PROVIDER_PROVENANCE[provider] }));
    }

    const started = Date.now();
    const requestStartedAt = new Date(started).toISOString();
    try {
      const upstreamBudget=Math.max(500,Math.min(10_000,this.timeoutMs-500));
      const json: any = await this.fetchJson(`/v1/${kind}?id=${encodeURIComponent(id)}&timeoutMs=${upstreamBudget}`);
      return names.map(provider => {
        const breaker = this.breakers[provider];
        const item = json?.providers?.[provider];
        const now=Date.now(),latencyMs = Number(item?.latencyMs ?? now - started),responseAt=new Date(now).toISOString();
        if (!runnable.includes(provider)) {
          return { provider, ok: false, latencyMs, observedAt: responseAt, requestStartedAt, responseAt, sampleAgeMs:now-started, error: 'circuit open', provenance: PROVIDER_PROVENANCE[provider] };
        }
        if (item?.ok) breaker.recordSuccess(latencyMs);
        else breaker.recordFailure(item?.error ?? 'sidecar provider failed', latencyMs);
        return {
          provider: provider as ProviderName,
          ok: Boolean(item?.ok),
          latencyMs,
          observedAt: responseAt,
          requestStartedAt,
          responseAt,
          sampleAgeMs:now-started,
          value: item?.value as T | undefined,
          error: item?.error as string | undefined,
          provenance: PROVIDER_PROVENANCE[provider],
        };
      });
    } catch (error) {
      const ended=Date.now(),latencyMs = ended - started,responseAt=new Date(ended).toISOString();
      for (const provider of runnable) this.breakers[provider].recordFailure(error, latencyMs);
      return names.map(provider => ({
        provider: provider as ProviderName,
        ok: false,
        latencyMs,
        observedAt: responseAt,
        requestStartedAt,
        responseAt,
        sampleAgeMs:ended-started,
        error: runnable.includes(provider) ? (error instanceof Error ? error.message : String(error)) : 'circuit open',
        provenance: PROVIDER_PROVENANCE[provider],
      }));
    }
  }
}
