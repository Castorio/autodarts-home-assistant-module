import { describe, it, expect, vi } from 'vitest';
import { EventPipeline } from './EventPipeline.js';
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
});
