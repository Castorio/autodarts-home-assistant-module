import { describe, it, expect, vi } from 'vitest';
import { EventPipeline, MAX_PENDING } from './EventPipeline.js';
import { MatchTracker } from './MatchTracker.js';
import type { PushPayload } from './types.js';

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

  it('drops pushes beyond the pending limit instead of buffering them unboundedly', async () => {
    const push = vi.fn().mockImplementation(() => new Promise<void>(() => {
      // never resolves: simulates an unreachable Home Assistant webhook
    }));
    const p = new EventPipeline(new MatchTracker(), push, now);
    for (let i = 0; i < MAX_PENDING + 5; i++) void p.handle(throwEvent(`S${i}`));
    // Only the head of the queue is running; the rest wait behind it
    await flush();
    expect(push).toHaveBeenCalledTimes(1);
    const overflow = p.handle(throwEvent('S1'));
    await expect(overflow).resolves.toBeUndefined();
  });

  it('keeps exactly MAX_PENDING pushes pending and still applies the state of dropped ones', async () => {
    const held = heldPush();
    const tracker = new MatchTracker();
    const p = new EventPipeline(tracker, held.push, now);
    for (let i = 0; i < MAX_PENDING; i++) void p.handle(throwEvent(`S${i}`));
    // The (MAX_PENDING + 1)th push is dropped, but its throw still updates the match state
    let dropped = false;
    void p.handle(throwEvent('T20')).then(() => {
      dropped = true;
    });
    await flush();
    expect(dropped).toBe(true);
    expect(tracker.snapshot().lastThrow).toBe('T20');

    await held.releaseAll();
    expect(held.sent.map((x) => x.data.segment)).toEqual(Array.from({ length: MAX_PENDING }, (_, i) => `S${i}`));

    void p.handle({ type: 'turn.finished', data: { turnScore: 60, remaining: 441, busted: false } });
    await held.releaseAll();
    const last = held.sent[held.sent.length - 1];
    expect(last.type).toBe('turn_finished');
    expect(last.state.lastThrow).toBe('T20');
  });

  it('applies the tracker synchronously, before earlier pushes settle', () => {
    const held = heldPush();
    const tracker = new MatchTracker();
    const p = new EventPipeline(tracker, held.push, now);
    void p.handle(throwEvent('S1'));
    void p.handle(throwEvent('D16'));
    expect(tracker.snapshot().lastThrow).toBe('D16');
  });

  it('pushes each event with the state as of that event, in order', async () => {
    const held = heldPush();
    const p = new EventPipeline(new MatchTracker(), held.push, now);
    void p.handle(throwEvent('S1'));
    void p.handle(throwEvent('D16'));
    void p.handle(throwEvent('T20'));
    await held.releaseAll();
    expect(held.sent.map((x) => [x.data.segment, x.state.lastThrow])).toEqual([
      ['S1', 'S1'],
      ['D16', 'D16'],
      ['T20', 'T20'],
    ]);
  });
});

function throwEvent(name: string) {
  return { type: 'throw.detected', data: { segment: { name, number: 20, multiplier: 1 }, points: 20 } };
}

async function flush() {
  for (let i = 0; i < 10; i++) await Promise.resolve();
}

/** A push whose calls stay pending until released; records payloads in call order */
function heldPush() {
  const sent: PushPayload[] = [];
  const waiting: (() => void)[] = [];
  const push = vi.fn().mockImplementation((payload: PushPayload) => {
    sent.push(payload);
    return new Promise<void>((resolve) => waiting.push(resolve));
  });
  async function releaseAll() {
    // Each release lets the next queued push start, so keep going until idle
    for (let rounds = 0; rounds < 1000; rounds++) {
      await flush();
      const next = waiting.shift();
      if (!next) return;
      next();
    }
  }
  return { push, sent, releaseAll };
}
