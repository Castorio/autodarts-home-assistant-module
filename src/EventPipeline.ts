import { mapEvent } from './EventMapper.js';
import type { MatchTracker } from './MatchTracker.js';
import type { PushPayload } from './types.js';

/** Max events allowed to be queued (accepted but not yet processed) at once.
 *  The hub's dispatch loop does not await each event handler, so without this
 *  bound an unreachable webhook (each push can take up to its own timeout)
 *  would let the backlog grow without limit. */
export const MAX_PENDING = 20;

/**
 * Hub event -> tracker -> payload -> push; repeated identical states are not pushed.
 *
 * `handle` serializes processing: each call chains onto an internal tail promise,
 * so event N's tracker.apply + mapEvent + push fully completes before event N+1
 * starts, keeping webhook pushes in the same order the hub emitted the events
 * (the SDK base class does not await handlers per event, so without this,
 * concurrent onEvent calls could push out of order).
 */
export class EventPipeline {
  private lastStateKey: string | null = null;
  private tail: Promise<void> = Promise.resolve();
  private pendingCount = 0;

  constructor(
    private readonly tracker: MatchTracker,
    private readonly push: (payload: PushPayload) => Promise<void>,
    private readonly now: () => Date = () => new Date(),
  ) {}

  handle(event: { type: string; data: unknown }): Promise<void> {
    if (this.pendingCount > MAX_PENDING) {
      // Backlog already full: drop the event (never applied) instead of
      // buffering it unboundedly while Home Assistant is unreachable.
      return Promise.resolve();
    }
    this.pendingCount++;
    const run = this.tail.then(() => this.process(event));
    // Keep the chain alive even if this event's processing rejects, so a
    // single bad event can't stall every event after it.
    this.tail = run.catch(() => undefined);
    return run.finally(() => {
      this.pendingCount--;
    });
  }

  private async process(event: { type: string; data: unknown }): Promise<void> {
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
