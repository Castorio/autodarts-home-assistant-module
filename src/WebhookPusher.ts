import { maskWebhookUrl } from './WebhookRegistry.js';
import type { PushPayload } from './types.js';

export interface PusherOptions {
  warn: (message: string, context?: Record<string, unknown>) => void;
  fetchFn?: typeof fetch;
  timeoutMs?: number;
  now?: () => number;
}

const WARN_INTERVAL_MS = 60_000;

/** Posts payloads to the Home Assistant webhook; failures are logged (throttled) and dropped */
export class WebhookPusher {
  private readonly fetchFn: typeof fetch;
  private readonly timeoutMs: number;
  private readonly now: () => number;
  private lastWarn = -Infinity;

  constructor(
    private readonly getUrl: () => string | null,
    private readonly options: PusherOptions,
  ) {
    this.fetchFn = options.fetchFn ?? fetch;
    this.timeoutMs = options.timeoutMs ?? 3000;
    this.now = options.now ?? Date.now;
  }

  async push(payload: PushPayload): Promise<boolean> {
    const url = this.getUrl();
    if (!url) return false;
    try {
      const res = await this.fetchFn(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
        redirect: 'manual',
        signal: AbortSignal.timeout(this.timeoutMs),
      });
      if (res.ok) return true;
      this.warn(url, `HTTP ${res.status}`);
    } catch (err) {
      this.warn(url, err instanceof Error ? err.message : String(err));
    }
    return false;
  }

  private warn(url: string, reason: string): void {
    const t = this.now();
    if (t - this.lastWarn < WARN_INTERVAL_MS) return;
    this.lastWarn = t;
    this.options.warn('Home Assistant webhook push failed', { url: maskWebhookUrl(url), reason });
  }
}
