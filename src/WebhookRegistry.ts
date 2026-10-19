export type RegisterResult = { ok: true } | { ok: false; error: string };

const MAX_URL_LENGTH = 512;
const WEBHOOK_PATH = /^\/api\/webhook\/[A-Za-z0-9_-]{8,128}$/;

function normalizeHosts(hosts: string[]): string[] {
  return hosts.map((h) => h.trim().toLowerCase()).filter((h) => h.length > 0);
}

export function parseAllowedHosts(value: unknown): string[] {
  if (typeof value !== 'string') return [];
  return normalizeHosts(value.split(','));
}

export function maskWebhookUrl(url: string): string {
  return url.replace(/(\/api\/webhook\/)([A-Za-z0-9_-]*)/, (_match, prefix: string, id: string) => {
    const visible = id.length > 4 ? id.slice(0, 4) : '';
    return `${prefix}${visible}…`;
  });
}

/** Holds the Home Assistant webhook URL in memory only, after validating it */
export class WebhookRegistry {
  private current: string | null = null;
  private allowedHosts: string[];

  constructor(allowedHosts: string[] = []) {
    this.allowedHosts = normalizeHosts(allowedHosts);
  }

  setAllowedHosts(hosts: string[]): void {
    this.allowedHosts = normalizeHosts(hosts);
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
