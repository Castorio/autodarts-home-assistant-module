/**
 * Cross-language contract fixture: tests/fixtures/push_payloads.json holds what
 * the mapper produces for a representative set of hub events; the Python tests
 * (tests/test_contract.py) validate every payload with PUSH_SCHEMA.
 *
 * Regenerate after an intended mapper change:
 *   UPDATE_CONTRACT=1 npx vitest run src/contract.test.ts
 */
import { readFileSync, writeFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';
import { mapEvent } from './EventMapper.js';
import { MatchTracker } from './MatchTracker.js';
import type { PushPayload } from './types.js';

const FIXTURE = fileURLToPath(new URL('../tests/fixtures/push_payloads.json', import.meta.url));
const NOW = new Date('2026-10-19T12:00:00.000Z');

const x01 = { variant: 'X01', mode: 'x01' };
const cricket = { variant: 'Cricket', mode: 'cricket' };
const players = [{ index: 0, name: 'Alice', color: '#3B82F6' }, { index: 1, name: 'Bob', color: '#ef4444' }];

const EVENTS: { type: string; data: unknown }[] = [
  { type: 'match.start', data: { matchId: 'm1', boardId: 'b1' } },
  {
    type: 'match.state',
    data: { matchId: 'm1', player: 0, gameScores: [501, 501], round: 1, legsWon: { 0: 0, 1: 0 }, setsWon: { 0: 0, 1: 0 }, players, variant: 'X01', game: x01 },
  },
  {
    type: 'throw.detected',
    data: { segment: { name: 'T20', number: 20, multiplier: 3 }, points: 60, turnPoints: 180, busted: false, game: x01 },
  },
  { type: 'turn.finished', data: { playerName: 'Alice', playerIndex: 0, turnScore: 121, remaining: 0, busted: false, round: 7, game: x01 } },
  { type: 'player.change', data: { playerName: 'Bob', playerIndex: 1, remaining: 301, currentPlayer: 1 } },
  { type: 'game.finished', data: { winnerName: 'Alice', winnerPlayerIndex: 0, leg: 1, set: 1 } },
  { type: 'match.finished', data: { winnerName: 'Alice', winnerPlayerIndex: 0 } },
  { type: 'match.finish', data: { matchId: 'm1' } },
  { type: 'match.start', data: { matchId: 'm2' } },
  {
    type: 'match.state',
    data: { matchId: 'm2', player: 1, gameScores: [0, 0], round: 2, players, variant: 'Cricket', game: cricket },
  },
  { type: 'cricket.state', data: { players: [{ index: 0, points: 40 }, { index: 1, points: 15 }] } },
  { type: 'cricket.closed', data: { field: 20, playerName: 'Bob', playerIndex: 1 } },
  { type: 'match.delete', data: { matchId: 'm2' } },
];

function buildPayloads(): PushPayload[] {
  const tracker = new MatchTracker();
  const out: PushPayload[] = [];
  for (const event of EVENTS) {
    tracker.apply(event);
    const payload = mapEvent(event, tracker.snapshot(), NOW);
    if (payload) out.push(payload);
  }
  return out;
}

describe('push payload contract fixture', () => {
  it('matches what the mapper produces', () => {
    const payloads = buildPayloads();
    if (process.env.UPDATE_CONTRACT) writeFileSync(FIXTURE, `${JSON.stringify(payloads, null, 2)}\n`);
    expect(JSON.parse(readFileSync(FIXTURE, 'utf8'))).toEqual(payloads);
  });
});
