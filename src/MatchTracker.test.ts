import { describe, it, expect } from 'vitest';
import { MatchTracker, emptySnapshot } from './MatchTracker.js';

const game = { variant: 'X01', mode: 'x01', cutThroat: false };

function matchState(overrides: Record<string, unknown> = {}) {
  return {
    type: 'match.state',
    data: {
      matchId: 'm1',
      player: 1,
      playerName: 'Bob',
      gameScores: [301, 241],
      turnScore: 0,
      round: 3,
      finished: false,
      winner: null,
      leg: 1,
      set: 1,
      legsWon: { 0: 1, 1: 0 },
      setsWon: { 0: 0, 1: 0 },
      players: [{ index: 0, name: 'Alice' }, { index: 1, name: 'Bob' }],
      variant: 'X01',
      game,
      ...overrides,
    },
  };
}

describe('MatchTracker', () => {
  it('starts empty', () => {
    expect(new MatchTracker().snapshot()).toEqual(emptySnapshot());
  });

  it('builds players and the current player from match.state', () => {
    const t = new MatchTracker();
    t.apply({ type: 'match.start', data: { matchId: 'm1', boardId: 'b' } });
    t.apply(matchState());
    const s = t.snapshot();
    expect(s.active).toBe(true);
    expect(s.matchId).toBe('m1');
    expect(s.variant).toBe('X01');
    expect(s.mode).toBe('x01');
    expect(s.round).toBe(3);
    expect(s.players).toEqual([
      { index: 0, name: 'Alice', score: 301, legsWon: 1, setsWon: 0 },
      { index: 1, name: 'Bob', score: 241, legsWon: 0, setsWon: 0 },
    ]);
    expect(s.currentPlayer).toEqual({ index: 1, name: 'Bob', score: 241, legsWon: 0, setsWon: 0 });
  });

  it('records the last throw and the last turn', () => {
    const t = new MatchTracker();
    t.apply(matchState());
    t.apply({ type: 'throw.detected', data: { segment: { name: 'T20', number: 20, multiplier: 3, bed: 'Triple' } } });
    t.apply({ type: 'turn.finished', data: { turnScore: 100, remaining: 141, busted: false } });
    expect(t.snapshot().lastThrow).toBe('T20');
    expect(t.snapshot().lastTurnPoints).toBe(100);
  });

  it('uses cricket points as score in cricket', () => {
    const t = new MatchTracker();
    t.apply(matchState({ game: { variant: 'Cricket', mode: 'cricket', cutThroat: false }, gameScores: [0, 0], player: 0 }));
    t.apply({
      type: 'cricket.state',
      data: { players: [{ index: 0, name: 'Alice', points: 40, marks: {} }, { index: 1, name: 'Bob', points: 15, marks: {} }] },
    });
    expect(t.snapshot().players.map((p) => p.score)).toEqual([40, 15]);
    expect(t.snapshot().currentPlayer?.score).toBe(40);
  });

  it('keeps cricket points across later match.state updates', () => {
    const t = new MatchTracker();
    const cricketGame = { variant: 'Cricket', mode: 'cricket', cutThroat: false };
    t.apply(matchState({ game: cricketGame, gameScores: [0, 0] }));
    t.apply({ type: 'cricket.state', data: { players: [{ index: 0, name: 'Alice', points: 40, marks: {} }] } });
    t.apply(matchState({ game: cricketGame, gameScores: [0, 0], round: 4 }));
    expect(t.snapshot().players[0].score).toBe(40);
  });

  it('stores the match winner', () => {
    const t = new MatchTracker();
    t.apply(matchState());
    t.apply({ type: 'match.finished', data: { winnerName: 'Alice', winnerPlayerIndex: 0 } });
    expect(t.snapshot().winnerName).toBe('Alice');
    expect(t.snapshot().active).toBe(true);
  });

  it('resets on match.finish and match.delete', () => {
    for (const type of ['match.finish', 'match.delete']) {
      const t = new MatchTracker();
      t.apply(matchState());
      t.apply({ type, data: { matchId: 'm1' } });
      expect(t.snapshot()).toEqual(emptySnapshot());
    }
  });

  it('resets on match.start', () => {
    const t = new MatchTracker();
    t.apply(matchState());
    t.apply({ type: 'match.start', data: { matchId: 'm2' } });
    expect(t.snapshot()).toEqual({ ...emptySnapshot(), active: true, matchId: 'm2' });
  });

  it('returns copies, not internal state', () => {
    const t = new MatchTracker();
    t.apply(matchState());
    t.snapshot().players[0].name = 'Mallory';
    expect(t.snapshot().players[0].name).toBe('Alice');
  });

  it('ignores malformed payloads', () => {
    const t = new MatchTracker();
    t.apply({ type: 'match.state', data: null });
    t.apply({ type: 'throw.detected', data: {} });
    expect(t.snapshot()).toEqual(emptySnapshot());
  });
});
