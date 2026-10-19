import type { ModuleRouteDefinition, RouteHandler } from '@autodarts-hub/module-sdk';
import type { WebhookRegistry } from './WebhookRegistry.js';
import { INTENT_SLOTS, intentId, type MatchSnapshot } from './types.js';

export interface RouteDeps {
  registry: WebhookRegistry;
  getState: () => MatchSnapshot;
  emitIntent: (id: string, payload: Record<string, unknown>) => void;
}

const MAX_INTENT_DATA = 200;

// requireAuth stays at the hub default (true): only a hub session may call these
export const ROUTES: ModuleRouteDefinition[] = [
  { method: 'POST', path: '/webhook', handlerId: 'registerWebhook', description: 'Register the Home Assistant webhook URL' },
  { method: 'GET', path: '/webhook', handlerId: 'webhookStatus', description: 'Whether a webhook is registered' },
  { method: 'DELETE', path: '/webhook', handlerId: 'unregisterWebhook', description: 'Remove the webhook' },
  { method: 'GET', path: '/state', handlerId: 'getState', description: 'Current match state' },
  { method: 'POST', path: '/intent', handlerId: 'triggerIntent', description: 'Emit homeassistant.trigger_<slot>' },
];

function body(raw: unknown): Record<string, unknown> {
  return typeof raw === 'object' && raw !== null ? (raw as Record<string, unknown>) : {};
}

export function createRouteHandlers(deps: RouteDeps): Record<string, RouteHandler> {
  return {
    registerWebhook: (req) => {
      const result = deps.registry.register(body(req.body).url);
      return result.ok
        ? { statusCode: 200, body: { registered: true } }
        : { statusCode: 400, body: { error: result.error } };
    },
    webhookStatus: () => ({ statusCode: 200, body: { registered: deps.registry.url !== null } }),
    unregisterWebhook: () => {
      deps.registry.clear();
      return { statusCode: 200, body: { registered: false } };
    },
    getState: () => ({ statusCode: 200, body: deps.getState() }),
    triggerIntent: (req) => {
      const { slot, data } = body(req.body);
      if (typeof slot !== 'number' || !Number.isInteger(slot) || slot < 1 || slot > INTENT_SLOTS) {
        return { statusCode: 400, body: { error: `slot must be an integer from 1 to ${INTENT_SLOTS}` } };
      }
      if (data !== undefined && (typeof data !== 'string' || data.length > MAX_INTENT_DATA)) {
        return { statusCode: 400, body: { error: `data must be a string of at most ${MAX_INTENT_DATA} characters` } };
      }
      const id = intentId(slot);
      deps.emitIntent(id, { slot, data: data ?? null });
      return { statusCode: 200, body: { emitted: id } };
    },
  };
}
