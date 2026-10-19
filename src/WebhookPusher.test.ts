import { describe, it, expect, vi } from 'vitest';
import { WebhookPusher } from './WebhookPusher.js';
import { emptySnapshot } from './MatchTracker.js';
import type { PushPayload } from './types.js';

const URL_ = 'http://ha:8123/api/webhook/abcdef0123456789';
const payload: PushPayload = { v: 1, type: 'state', ts: 't', tags: [], data: {}, state: emptySnapshot() };

describe('WebhookPusher', () => {
  it('does nothing without a registered URL', async () => {
    const fetchFn = vi.fn();
    const p = new WebhookPusher(() => null, { warn: vi.fn(), fetchFn });
    expect(await p.push(payload)).toBe(false);
    expect(fetchFn).not.toHaveBeenCalled();
  });

  it('posts JSON without following redirects', async () => {
    const fetchFn = vi.fn().mockResolvedValue({ ok: true, status: 200 });
    const p = new WebhookPusher(() => URL_, { warn: vi.fn(), fetchFn });
    expect(await p.push(payload)).toBe(true);
    const [url, init] = fetchFn.mock.calls[0];
    expect(url).toBe(URL_);
    expect(init.method).toBe('POST');
    expect(init.redirect).toBe('manual');
    expect(init.headers).toEqual({ 'Content-Type': 'application/json' });
    expect(JSON.parse(init.body)).toEqual(payload);
    expect(init.signal).toBeInstanceOf(AbortSignal);
  });

  it('reports non-2xx answers as failure with a masked URL', async () => {
    const warn = vi.fn();
    const fetchFn = vi.fn().mockResolvedValue({ ok: false, status: 404 });
    const p = new WebhookPusher(() => URL_, { warn, fetchFn });
    expect(await p.push(payload)).toBe(false);
    expect(warn).toHaveBeenCalledWith('Home Assistant webhook push failed', { url: 'http://ha:8123/api/webhook/abcd…', reason: 'HTTP 404' });
  });

  it('swallows network errors and throttles warnings to one per minute', async () => {
    const warn = vi.fn();
    let t = 0;
    const fetchFn = vi.fn().mockRejectedValue(new Error('ECONNREFUSED'));
    const p = new WebhookPusher(() => URL_, { warn, fetchFn, now: () => t });
    expect(await p.push(payload)).toBe(false);
    t = 30_000;
    await p.push(payload);
    expect(warn).toHaveBeenCalledTimes(1);
    t = 61_000;
    await p.push(payload);
    expect(warn).toHaveBeenCalledTimes(2);
  });

  it('cancels response body on success to release connection pool', async () => {
    const cancel = vi.fn().mockResolvedValue(undefined);
    const fetchFn = vi.fn().mockResolvedValue({ ok: true, status: 200, body: { cancel } });
    const p = new WebhookPusher(() => URL_, { warn: vi.fn(), fetchFn });
    expect(await p.push(payload)).toBe(true);
    expect(cancel).toHaveBeenCalledOnce();
  });

  it('cancels response body on non-2xx to release connection pool', async () => {
    const cancel = vi.fn().mockResolvedValue(undefined);
    const warn = vi.fn();
    const fetchFn = vi.fn().mockResolvedValue({ ok: false, status: 404, body: { cancel } });
    const p = new WebhookPusher(() => URL_, { warn, fetchFn });
    expect(await p.push(payload)).toBe(false);
    expect(cancel).toHaveBeenCalledOnce();
  });
});
