import { mapEvent } from './EventMapper.js';
import type { MatchTracker } from './MatchTracker.js';
import type { PushPayload } from './types.js';

/** Hub event -> tracker -> payload -> push; repeated identical states are not pushed */
export class EventPipeline {
  private lastStateKey: string | null = null;

  constructor(
    private readonly tracker: MatchTracker,
    private readonly push: (payload: PushPayload) => Promise<void>,
    private readonly now: () => Date = () => new Date(),
  ) {}

  async handle(event: { type: string; data: unknown }): Promise<void> {
    this.tracker.apply(event);
    const state = this.tracker.snapshot();
    const payload = mapEvent(event, state, this.now());
    if (!payload) return;

    const key = JSON.stringify(state);
    if (payload.type === 'state' && key === this.lastStateKey) return;
    this.lastStateKey = key;

    try {
      await this.push(payload);
    } catch {
      // The pusher logs its own failures; an event must never break the module
    }
  }
}
