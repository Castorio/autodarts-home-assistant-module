import { mapEvent } from './EventMapper.js';
import type { MatchTracker } from './MatchTracker.js';
import type { PushPayload } from './types.js';

/** Max pushes allowed to be pending (queued or in flight) at once.
 *  The hub's dispatch loop does not await each event handler, so without this
 *  bound an unreachable webhook (each push can take up to its own timeout)
 *  would let the backlog grow without limit. */
export const MAX_PENDING = 20;

/**
 * Hub event -> tracker -> payload -> push; repeated identical states are not pushed.
 *
 * The tracker is updated and the payload built synchronously in `handle`, so the
 * match state is always current (also for `GET /state`) even when pushes back up.
 * Only the push itself is queued: each push chains onto an internal tail promise,
 * keeping webhook pushes in the order the hub emitted the events. When
 * MAX_PENDING pushes are already pending, further pushes are dropped; their
 * state still reaches Home Assistant with the next push that goes through.
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
    this.tracker.apply(event);
    const state = this.tracker.snapshot();
    const payload = mapEvent(event, state, this.now());
    if (!payload) return Promise.resolve();

    const key = JSON.stringify(state);
    if (payload.type === 'state' && key === this.lastStateKey) return Promise.resolve();
    if (this.pendingCount >= MAX_PENDING) return Promise.resolve();
    this.lastStateKey = key;

    this.pendingCount++;
    const run = this.tail.then(() => this.send(payload));
    this.tail = run;
    return run.finally(() => {
      this.pendingCount--;
    });
  }

  private async send(payload: PushPayload): Promise<void> {
    try {
      await this.push(payload);
    } catch {
      // The pusher logs its own failures; an event must never break the module
    }
  }
}
