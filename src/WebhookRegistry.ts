export type RegisterResult = { ok: true } | { ok: false; error: string };

const MAX_URL_LENGTH = 512;
const WEBHOOK_PATH = /^\/api\/webhook\/[A-Za-z0-9_-]{8,128}$/;

export function parseAllowedHosts(value: unknown): string[] {
  if (typeof value !== 'string') return [];
  return value
    .split(',')
    .map((h) => h.trim().toLowerCase())
    .filter((h) => h.length > 0);
}

export function maskWebhookUrl(url: string): string {
  return url.replace(/(\/api\/webhook\/)([A-Za-z0-9_-]{4})[A-Za-z0-9_-]*/, '$1$2…');
}

/** Holds the Home Assistant webhook URL in memory only, after validating it */
export class WebhookRegistry {
  private current: string | null = null;

  constructor(private allowedHosts: string[] = []) {}

  setAllowedHosts(hosts: string[]): void {
    this.allowedHosts = hosts;
  }

  get url(): string | null {
    return this.current;
  }

  clear(): void {
    this.current = null;
  }

  register(raw: unknown): RegisterResult {
    const error = this.validate(raw);
    if (error) return { ok: false, error };
    this.current = raw as string;
    return { ok: true };
  }

  private validate(raw: unknown): string | null {
    if (typeof raw !== 'string') return 'url must be a string';
    if (raw.length > MAX_URL_LENGTH) return 'url too long';
    let url: URL;
    try {
      url = new URL(raw);
    } catch {
      return 'invalid url';
    }
    if (url.protocol !== 'http:' && url.protocol !== 'https:') return 'only http and https are allowed';
    if (url.username || url.password) return 'credentials in url are not allowed';
    if (url.search || url.hash) return 'query and fragment are not allowed';
    // The raw string must already be canonical, so "/../" tricks (including
    // their %2e/backslash variants, which the URL parser normalizes away)
    // are rejected too.
    if (!WEBHOOK_PATH.test(url.pathname) || !raw.endsWith(url.pathname)) return 'path must be /api/webhook/<id>';
    if (this.allowedHosts.length > 0 && !this.allowedHosts.includes(url.hostname.toLowerCase())) return 'host not allowed';
    return null;
  }
}
