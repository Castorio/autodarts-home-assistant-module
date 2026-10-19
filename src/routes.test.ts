import { describe, it, expect, vi } from 'vitest';
import { ROUTES, createRouteHandlers } from './routes.js';
import { WebhookRegistry } from './WebhookRegistry.js';
import { emptySnapshot } from './MatchTracker.js';
import type { RouteRequest } from '@autodarts-hub/module-sdk';

const GOOD = 'http://ha:8123/api/webhook/abcdef0123456789';

function req(handlerId: string, body: unknown = undefined): RouteRequest {
  return { handlerId, method: 'POST', path: '/', params: {}, query: {}, body, headers: {} };
}

function setup() {
  const registry = new WebhookRegistry();
  const emitIntent = vi.fn();
  const handlers = createRouteHandlers({ registry, getState: () => ({ ...emptySnapshot(), active: true }), emitIntent });
  return { registry, emitIntent, handlers };
}

describe('routes', () => {
  it('declares every handler and keeps hub auth on', () => {
    const { handlers } = setup();
    for (const r of ROUTES) {
      expect(handlers[r.handlerId]).toBeTypeOf('function');
      expect(r.requireAuth).not.toBe(false);
    }
    expect(ROUTES.map((r) => `${r.method} ${r.path}`)).toEqual([
      'POST /webhook', 'GET /webhook', 'DELETE /webhook', 'GET /state', 'POST /intent',
    ]);
  });

  it('registers, reports and removes the webhook', async () => {
    const { handlers } = setup();
    expect(await handlers.webhookStatus(req('webhookStatus'))).toEqual({ statusCode: 200, body: { registered: false } });
    expect(await handlers.registerWebhook(req('registerWebhook', { url: GOOD }))).toEqual({ statusCode: 200, body: { registered: true, changed: true } });
    expect(await handlers.webhookStatus(req('webhookStatus'))).toEqual({ statusCode: 200, body: { registered: true } });
    expect(await handlers.unregisterWebhook(req('unregisterWebhook'))).toEqual({ statusCode: 200, body: { registered: false } });
  });

  it('reports whether a registration changed the stored url, without revealing it', async () => {
    const { handlers } = setup();
    const other = 'http://ha:8123/api/webhook/zzzzzzzz01234567';
    expect((await handlers.registerWebhook(req('registerWebhook', { url: GOOD }))).body).toEqual({ registered: true, changed: true });
    expect((await handlers.registerWebhook(req('registerWebhook', { url: GOOD }))).body).toEqual({ registered: true, changed: false });
    expect((await handlers.registerWebhook(req('registerWebhook', { url: other }))).body).toEqual({ registered: true, changed: true });
    const status = await handlers.webhookStatus(req('webhookStatus'));
    expect(JSON.stringify(status)).not.toContain('webhook/');
    await handlers.unregisterWebhook(req('unregisterWebhook'));
    expect((await handlers.registerWebhook(req('registerWebhook', { url: other }))).body).toEqual({ registered: true, changed: true });
  });

  it('rejects an invalid webhook with 400', async () => {
    const { handlers } = setup();
    expect(await handlers.registerWebhook(req('registerWebhook', { url: 'ftp://x' }))).toEqual({ statusCode: 400, body: { error: 'only http and https are allowed' } });
    expect(await handlers.registerWebhook(req('registerWebhook', null))).toEqual({ statusCode: 400, body: { error: 'url must be a string' } });
  });

  it('treats an array body as not-an-object, even one carrying its own url property', async () => {
    const { handlers } = setup();
    const arrayWithUrl = Object.assign([], { url: GOOD }) as unknown;
    expect(await handlers.registerWebhook(req('registerWebhook', arrayWithUrl))).toEqual({ statusCode: 400, body: { error: 'url must be a string' } });
  });

  it('returns the match state', async () => {
    const { handlers } = setup();
    expect(await handlers.getState(req('getState'))).toEqual({ statusCode: 200, body: { ...emptySnapshot(), active: true } });
  });

  it('emits a declared intent slot', async () => {
    const { handlers, emitIntent } = setup();
    expect(await handlers.triggerIntent(req('triggerIntent', { slot: 2, data: 'party' }))).toEqual({ statusCode: 200, body: { emitted: 'homeassistant.trigger_2' } });
    expect(emitIntent).toHaveBeenCalledWith('homeassistant.trigger_2', { slot: 2, data: 'party' });
    await handlers.triggerIntent(req('triggerIntent', { slot: 5 }));
    expect(emitIntent).toHaveBeenLastCalledWith('homeassistant.trigger_5', { slot: 5, data: null });
  });

  it.each([
    [{ slot: 0 }, 'slot must be an integer from 1 to 5'],
    [{ slot: 6 }, 'slot must be an integer from 1 to 5'],
    [{ slot: 1.5 }, 'slot must be an integer from 1 to 5'],
    [{ slot: '1' }, 'slot must be an integer from 1 to 5'],
    [{ slot: 1, data: 5 }, 'data must be a string of at most 200 characters'],
    [{ slot: 1, data: 'x'.repeat(201) }, 'data must be a string of at most 200 characters'],
    [null, 'slot must be an integer from 1 to 5'],
  ])('rejects intent body %j', async (body, error) => {
    const { handlers, emitIntent } = setup();
    expect(await handlers.triggerIntent(req('triggerIntent', body))).toEqual({ statusCode: 400, body: { error } });
    expect(emitIntent).not.toHaveBeenCalled();
  });
});
