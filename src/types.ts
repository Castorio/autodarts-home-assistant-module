// NOTE: @autodarts-hub/module-sdk's built dist/ does not (yet) export `GameMode`,
// even though its src/index.ts defines one (`'x01' | 'cricket' | 'tactics' | 'other'`).
// Since the SDK is read-only here, GameMode is defined locally with the identical
// shape instead of imported, so this still matches the SDK's intended contract.
// Task 2+ should import GameMode from here, not from '@autodarts-hub/module-sdk'.
export type GameMode = 'x01' | 'cricket' | 'tactics' | 'other';

export type Tag = '180' | 'bust' | 'bullseye' | 'bull' | 'triple' | 'double' | 'miss' | 'high_finish';

export type PushType =
  | 'state'
  | 'match_started'
  | 'match_finished'
  | 'match_cancelled'
  | 'match_closed'
  | 'leg_finished'
  | 'player_changed'
  | 'throw'
  | 'turn_finished'
  | 'cricket_closed';

export interface PlayerSnapshot {
  index: number;
  name: string;
  /** x01: remaining points; Cricket/Tactics: points */
  score: number | null;
  legsWon: number;
  setsWon: number;
}

export interface MatchSnapshot {
  active: boolean;
  matchId: string | null;
  variant: string | null;
  mode: GameMode | null;
  round: number | null;
  currentPlayer: PlayerSnapshot | null;
  players: PlayerSnapshot[];
  lastThrow: string | null;
  lastTurnPoints: number | null;
  winnerName: string | null;
}

export type PushValue = string | number | boolean | null;

export interface PushPayload {
  v: 1;
  type: PushType;
  ts: string;
  tags: Tag[];
  data: Record<string, PushValue>;
  state: MatchSnapshot;
}

export const INTENT_SLOTS = 5;

export function intentId(slot: number): string {
  return `homeassistant.trigger_${slot}`;
}
