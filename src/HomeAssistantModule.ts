import { AutodartsModule, type ParsedEvent } from '@autodarts-hub/module-sdk';
import { EventPipeline } from './EventPipeline.js';
import { MatchTracker } from './MatchTracker.js';
import { ROUTES, createRouteHandlers } from './routes.js';
import { WebhookPusher } from './WebhookPusher.js';
import { WebhookRegistry, parseAllowedHosts } from './WebhookRegistry.js';

/** SDK glue: hub events go to Home Assistant, Home Assistant calls the module routes */
export class HomeAssistantModule extends AutodartsModule {
  private readonly tracker = new MatchTracker();
  private readonly registry = new WebhookRegistry();
  private pipeline: EventPipeline | null = null;

  protected async onInit(config: Record<string, unknown>): Promise<void> {
    this.config = config;
    this.registry.setAllowedHosts(parseAllowedHosts(config.allowedHosts));

    const pusher = new WebhookPusher(() => this.registry.url, {
      warn: (message, context) => this.log('warn', message, context),
    });
    this.pipeline = new EventPipeline(this.tracker, async (payload) => {
      await pusher.push(payload);
    });

    this.registerRoutes(ROUTES);
    const handlers = createRouteHandlers({
      registry: this.registry,
      getState: () => this.tracker.snapshot(),
      emitIntent: (id, payload) => this.emitIntent(id, payload),
    });
    for (const [id, handler] of Object.entries(handlers)) this.setRouteHandler(id, handler);

    this.log('info', 'Home Assistant module ready, waiting for the integration to register its webhook');
  }

  protected async onEvent(event: ParsedEvent): Promise<void> {
    await this.pipeline?.handle(event);
  }

  protected async onConfigUpdate(config: Record<string, unknown>): Promise<void> {
    this.config = config;
    this.registry.setAllowedHosts(parseAllowedHosts(config.allowedHosts));
  }

  protected async onShutdown(): Promise<void> {
    this.registry.clear();
  }
}
