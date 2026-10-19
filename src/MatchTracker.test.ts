import { describe, it, expect } from 'vitest';
import { MAX_PLAYERS, MAX_STRING, MatchTracker, emptySnapshot } from './MatchTracker.js';

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
      { index: 0, name: 'Alice', score: 301, legsWon: 1, setsWon: 0, color: null },
      { index: 1, name: 'Bob', score: 241, legsWon: 0, setsWon: 0, color: null },
    ]);
    expect(s.currentPlayer).toEqual({ index: 1, name: 'Bob', score: 241, legsWon: 0, setsWon: 0, color: null });
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

  it('caps strings at 200 characters and players at 16, like the Home Assistant webhook schema', () => {
    const long = 'x'.repeat(500);
    const t = new MatchTracker();
    t.apply({ type: 'match.start', data: { matchId: long } });
    expect(t.snapshot().matchId).toHaveLength(MAX_STRING);
    const players = Array.from({ length: 20 }, (_, i) => ({ index: i, name: `${i}${long}` }));
    t.apply(matchState({ matchId: long, variant: long, players, gameScores: players.map(() => 501), player: 0 }));
    t.apply({ type: 'throw.detected', data: { segment: { name: long } } });
    t.apply({ type: 'match.finished', data: { winnerName: long } });
    const s = t.snapshot();
    expect(MAX_STRING).toBe(200);
    expect(MAX_PLAYERS).toBe(16);
    expect(s.players).toHaveLength(MAX_PLAYERS);
    expect(s.players.every((p) => p.name.length === MAX_STRING)).toBe(true);
    expect(s.currentPlayer?.name).toHaveLength(MAX_STRING);
    expect(s.matchId).toHaveLength(MAX_STRING);
    expect(s.variant).toHaveLength(MAX_STRING);
    expect(s.lastThrow).toHaveLength(MAX_STRING);
    expect(s.winnerName).toHaveLength(MAX_STRING);
  });

  it('caps the game variant fallback too', () => {
    const t = new MatchTracker();
    t.apply(matchState({ variant: undefined, game: { mode: 'x01', variant: 'v'.repeat(300) } }));
    expect(t.snapshot().variant).toHaveLength(MAX_STRING);
  });
});

describe('player colors', () => {
  const colored = (overrides: Record<string, unknown> = {}) =>
    matchState({
      players: [
        { index: 0, name: 'Alice', color: '#3B82F6' },
        { index: 1, name: 'Bob', color: '#ef4444' },
        { index: 2, name: 'Carol', color: 'red' },
      ],
      gameScores: [301, 241, 501],
      ...overrides,
    });

  it('takes valid hex colors in lower case and drops invalid ones', () => {
    const t = new MatchTracker();
    t.apply(colored());
    expect(t.snapshot().players.map((p) => p.color)).toEqual(['#3b82f6', '#ef4444', null]);
  });

  it('sets current and next player color in throw order', () => {
    const t = new MatchTracker();
    t.apply(colored({ player: 0 }));
    expect(t.snapshot().currentPlayerColor).toBe('#3b82f6');
    expect(t.snapshot().nextPlayerColor).toBe('#ef4444');
  });

  it('wraps around to the first player', () => {
    const t = new MatchTracker();
    t.apply(colored({ player: 1, players: [{ index: 0, name: 'Alice', color: '#3b82f6' }, { index: 1, name: 'Bob', color: '#ef4444' }], gameScores: [1, 2] }));
    expect(t.snapshot().nextPlayerColor).toBe('#3b82f6');
  });

  it('uses the same player as next in a single player game', () => {
    const t = new MatchTracker();
    t.apply(colored({ player: 0, players: [{ index: 0, name: 'Alice', color: '#3b82f6' }], gameScores: [501] }));
    expect(t.snapshot().nextPlayerColor).toBe('#3b82f6');
  });

  it('switches the current player on player.change before the next match.state', () => {
    const t = new MatchTracker();
    t.apply(colored({ player: 0, players: [{ index: 0, name: 'Alice', color: '#3b82f6' }, { index: 1, name: 'Bob', color: '#ef4444' }], gameScores: [1, 2] }));
    t.apply({ type: 'player.change', data: { currentPlayer: 1, playerIndex: 1, playerName: 'Bob' } });
    expect(t.snapshot().currentPlayer?.name).toBe('Bob');
    expect(t.snapshot().currentPlayerColor).toBe('#ef4444');
    expect(t.snapshot().nextPlayerColor).toBe('#3b82f6');
  });

  it('ignores a player.change with an out of range position', () => {
    const t = new MatchTracker();
    t.apply(colored({ player: 0 }));
    t.apply({ type: 'player.change', data: { currentPlayer: 7 } });
    expect(t.snapshot().currentPlayerColor).toBe('#3b82f6');
  });

  it('clears colors on match end', () => {
    const t = new MatchTracker();
    t.apply(colored({ player: 0 }));
    t.apply({ type: 'match.finish', data: { matchId: 'm1' } });
    expect(t.snapshot().currentPlayerColor).toBeNull();
    expect(t.snapshot().nextPlayerColor).toBeNull();
  });
});
