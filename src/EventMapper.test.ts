import { describe, it, expect } from 'vitest';
import { mapEvent } from './EventMapper.js';
import { emptySnapshot } from './MatchTracker.js';

const now = new Date('2026-10-19T12:00:00.000Z');
const state = { ...emptySnapshot(), active: true };
const x01 = { variant: 'X01', mode: 'x01', cutThroat: false };

describe('mapEvent', () => {
  it('maps a throw with tags and selected fields only', () => {
    const p = mapEvent(
      {
        type: 'throw.detected',
        data: {
          segment: { name: 'T20', number: 20, multiplier: 3, bed: 'Triple' },
          coords: { x: 0.1, y: 0.2 },
          boardId: 'secret-board',
          points: 60,
          turnPoints: 180,
          busted: false,
          game: x01,
        },
      },
      state,
      now,
    );
    expect(p).toEqual({
      v: 1,
      type: 'throw',
      ts: '2026-10-19T12:00:00.000Z',
      tags: ['180', 'triple'],
      data: { segment: 'T20', number: 20, multiplier: 3, points: 60, turnPoints: 180, busted: false },
      state,
    });
  });

  it('maps turn.finished with high finish tag', () => {
    const p = mapEvent(
      { type: 'turn.finished', data: { playerName: 'Alice', playerIndex: 0, turnScore: 121, remaining: 0, busted: false, round: 7, game: x01, throws: [] } },
      state,
      now,
    );
    expect(p?.type).toBe('turn_finished');
    expect(p?.tags).toEqual(['high_finish']);
    expect(p?.data).toEqual({ playerName: 'Alice', playerIndex: 0, turnScore: 121, remaining: 0, busted: false, round: 7 });
  });

  it.each([
    ['match.start', { matchId: 'm1', boardId: 'b' }, 'match_started', { matchId: 'm1' }],
    ['match.delete', { matchId: 'm1' }, 'match_cancelled', { matchId: 'm1' }],
    ['match.finish', { matchId: 'm1' }, 'match_closed', { matchId: 'm1' }],
    ['match.finished', { winnerName: 'Alice', winnerPlayerIndex: 0, players: [] }, 'match_finished', { winnerName: 'Alice', winnerPlayerIndex: 0 }],
    ['game.finished', { winnerName: 'Bob', winnerPlayerIndex: 1, leg: 2, set: 1, players: [] }, 'leg_finished', { winnerName: 'Bob', winnerPlayerIndex: 1, leg: 2, set: 1 }],
    ['player.change', { playerName: 'Bob', playerIndex: 1, remaining: 241, previousPlayer: 0, currentPlayer: 1 }, 'player_changed', { playerName: 'Bob', playerIndex: 1, remaining: 241, playerColor: null, nextPlayerColor: null }],
    ['cricket.closed', { field: '20', playerName: 'Alice', playerIndex: 0, matchId: 'm1' }, 'cricket_closed', { field: '20', playerName: 'Alice', playerIndex: 0 }],
    ['match.state', { matchId: 'm1' }, 'state', {}],
    ['cricket.state', { matchId: 'm1' }, 'state', {}],
  ])('maps %s to %s', (type, data, expectedType, expectedData) => {
    const p = mapEvent({ type, data }, state, now);
    expect(p?.type).toBe(expectedType);
    expect(p?.data).toEqual(expectedData);
    expect(p?.tags).toEqual([]);
  });

  it('drops non-scalar and oversized values', () => {
    const p = mapEvent({ type: 'player.change', data: { playerName: 'x'.repeat(500), playerIndex: { evil: true }, remaining: 3 } }, state, now);
    expect(p?.data).toEqual({ playerName: 'x'.repeat(200), playerIndex: null, remaining: 3, playerColor: null, nextPlayerColor: null });
  });

  it('adds the player colors to player_changed', () => {
    const colored = { ...state, currentPlayerColor: '#ef4444', nextPlayerColor: '#3b82f6' };
    const p = mapEvent({ type: 'player.change', data: { playerName: 'Bob', playerIndex: 1, remaining: 241 } }, colored, now);
    expect(p?.data).toEqual({ playerName: 'Bob', playerIndex: 1, remaining: 241, playerColor: '#ef4444', nextPlayerColor: '#3b82f6' });
  });

  it('ignores unknown events', () => {
    expect(mapEvent({ type: 'board.state', data: {} }, state, now)).toBeNull();
    expect(mapEvent({ type: 'takeout.started', data: {} }, state, now)).toBeNull();
  });
});
