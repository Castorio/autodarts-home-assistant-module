import { describe, it, expect } from 'vitest';
import { WebhookRegistry, parseAllowedHosts, maskWebhookUrl } from './WebhookRegistry.js';

const GOOD = 'http://192.168.41.10:8123/api/webhook/abcdef0123456789abcdef0123456789';

describe('WebhookRegistry', () => {
  it('accepts a Home Assistant webhook URL', () => {
    const r = new WebhookRegistry();
    expect(r.register(GOOD)).toEqual({ ok: true });
    expect(r.url).toBe(GOOD);
  });

  it.each([
    [123, 'url must be a string'],
    ['not a url', 'invalid url'],
    ['ftp://ha/api/webhook/abcdef0123', 'only http and https are allowed'],
    ['http://user:pw@ha/api/webhook/abcdef0123', 'credentials in url are not allowed'],
    ['http://ha/api/other/abcdef0123', 'path must be /api/webhook/<id>'],
    ['http://ha/api/webhook/short', 'path must be /api/webhook/<id>'],
    ['http://ha/api/webhook/abcdef0123/../x', 'path must be /api/webhook/<id>'],
    ['http://ha/api/webhook/abcdef0123?x=1', 'query and fragment are not allowed'],
    ['http://ha/api/webhook/' + 'a'.repeat(600), 'url too long'],
    // Regression: %2e%2e-encoded ".." normalizes to a path that satisfies the
    // id-length regex on its own, but must still be rejected because the raw
    // string does not literally end with the normalized pathname.
    ['http://ha/api/webhook/abcdef0123456789/%2e%2e/abcdef01', 'path must be /api/webhook/<id>'],
    // Regression: backslash is a path separator for special schemes in the
    // WHATWG URL parser, so "\\..\\" must be caught the same way as "/../".
    ['http://ha/api/webhook/abcdef0123456789\\..\\abcdef01', 'path must be /api/webhook/<id>'],
  ])('rejects %s', (url, error) => {
    const r = new WebhookRegistry();
    expect(r.register(url)).toEqual({ ok: false, error });
    expect(r.url).toBeNull();
  });

  it('keeps the previous URL when a registration is rejected', () => {
    const r = new WebhookRegistry();
    r.register(GOOD);
    r.register('ftp://x/api/webhook/abcdef0123');
    expect(r.url).toBe(GOOD);
  });

  it('enforces the host allowlist', () => {
    const r = new WebhookRegistry(['ha.local']);
    expect(r.register(GOOD)).toEqual({ ok: false, error: 'host not allowed' });
    expect(r.register('http://HA.local:8123/api/webhook/abcdef0123456789')).toEqual({ ok: true });
  });

  it('clears the URL', () => {
    const r = new WebhookRegistry();
    r.register(GOOD);
    r.clear();
    expect(r.url).toBeNull();
  });
});

describe('parseAllowedHosts', () => {
  it('splits, trims and lowercases', () => {
    expect(parseAllowedHosts(' HA.local, 192.168.1.5 ,,')).toEqual(['ha.local', '192.168.1.5']);
  });
  it('returns an empty list for non-strings', () => {
    expect(parseAllowedHosts(undefined)).toEqual([]);
  });
});

describe('maskWebhookUrl', () => {
  it('keeps only the first 4 characters of the webhook id', () => {
    expect(maskWebhookUrl(GOOD)).toBe('http://192.168.41.10:8123/api/webhook/abcd…');
  });
});
