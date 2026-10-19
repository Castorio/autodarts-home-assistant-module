import { describe, it, expect, vi } from 'vitest';
import { EventPipeline, MAX_PENDING } from './EventPipeline.js';
import { MatchTracker } from './MatchTracker.js';

const now = () => new Date('2026-10-19T12:00:00.000Z');
const state = (round: number) => ({
  type: 'match.state',
  data: { matchId: 'm1', player: 0, gameScores: [501], round, players: [{ index: 0, name: 'Alice' }], game: { mode: 'x01' } },
});

describe('EventPipeline', () => {
  it('pushes events with the updated state', async () => {
    const push = vi.fn().mockResolvedValue(undefined);
    const p = new EventPipeline(new MatchTracker(), push, now);
    await p.handle(state(1));
    await p.handle({ type: 'throw.detected', data: { segment: { name: 'S20', number: 20, multiplier: 1 }, points: 20 } });
    expect(push).toHaveBeenCalledTimes(2);
    expect(push.mock.calls[1][0].type).toBe('throw');
    expect(push.mock.calls[1][0].state.lastThrow).toBe('S20');
  });

  it('skips state pushes when nothing changed', async () => {
    const push = vi.fn().mockResolvedValue(undefined);
    const p = new EventPipeline(new MatchTracker(), push, now);
    await p.handle(state(1));
    await p.handle(state(1));
    await p.handle(state(2));
    expect(push).toHaveBeenCalledTimes(2);
  });

  it('does not push unknown events', async () => {
    const push = vi.fn().mockResolvedValue(undefined);
    await new EventPipeline(new MatchTracker(), push, now).handle({ type: 'board.state', data: {} });
    expect(push).not.toHaveBeenCalled();
  });

  it('swallows push errors', async () => {
    const push = vi.fn().mockRejectedValue(new Error('down'));
    const p = new EventPipeline(new MatchTracker(), push, now);
    await expect(p.handle(state(1))).resolves.toBeUndefined();
  });

  it('keeps pushes in call order even when the first push settles later than the second would', async () => {
    const order: string[] = [];
    let releaseFirst: (() => void) | undefined;
    const push = vi.fn().mockImplementation((payload: { type: string }) => {
      if (push.mock.calls.length === 1) {
        // First push stays pending until explicitly released below, while
        // the second push (if it were allowed to run concurrently) would
        // resolve immediately.
        return new Promise<void>((resolve) => {
          releaseFirst = () => {
            order.push(payload.type);
            resolve();
          };
        });
      }
      order.push(payload.type);
      return Promise.resolve();
    });
    const p = new EventPipeline(new MatchTracker(), push, now);

    const first = p.handle(state(1));
    const second = p.handle({ type: 'throw.detected', data: { segment: { name: 'S20', number: 20, multiplier: 1 }, points: 20 } });

    // Let pending microtasks run: the second event must still be queued
    // behind the first one, so push must not have been called a second time.
    await Promise.resolve();
    await Promise.resolve();
    await Promise.resolve();
    expect(push).toHaveBeenCalledTimes(1);

    releaseFirst?.();
    await first;
    await second;

    expect(push).toHaveBeenCalledTimes(2);
    expect(order).toEqual(['state', 'throw']);
  });

  it('drops events beyond the pending limit instead of buffering them unboundedly', async () => {
    const push = vi.fn().mockImplementation(() => new Promise<void>(() => {
      // never resolves: simulates an unreachable Home Assistant webhook
    }));
    const p = new EventPipeline(new MatchTracker(), push, now);

    const pending: Promise<void>[] = [];
    for (let i = 0; i < MAX_PENDING + 1; i++) {
      pending.push(p.handle({ type: 'throw.detected', data: { segment: { name: 'S20', number: 20, multiplier: 1 }, points: 20 } }));
    }
    // The (MAX_PENDING + 2)th call (the 22nd overall) must be dropped and
    // resolve immediately, instead of queueing behind the stuck backlog.
    const overflow = p.handle({ type: 'throw.detected', data: { segment: { name: 'S20', number: 20, multiplier: 1 }, points: 20 } });
    await expect(overflow).resolves.toBeUndefined();

    // Only the head of the queue actually ran (push never resolves, so the
    // rest stay queued); the point is that the backlog did not grow further.
    const callsAfterOverflow = push.mock.calls.length;
    const overflow2 = p.handle({ type: 'throw.detected', data: { segment: { name: 'S20', number: 20, multiplier: 1 }, points: 20 } });
    await expect(overflow2).resolves.toBeUndefined();
    expect(push.mock.calls.length).toBe(callsAfterOverflow);
  });
});
