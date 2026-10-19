import type { GameMode } from './types.js';
import type { MatchSnapshot, PlayerSnapshot } from './types.js';

type Obj = Record<string, unknown>;

function isObj(v: unknown): v is Obj {
  return typeof v === 'object' && v !== null;
}

function num(v: unknown): number | null {
  return typeof v === 'number' && Number.isFinite(v) ? v : null;
}

/** Same limits as PUSH_SCHEMA in custom_components/io_darts/schema.py;
 *  a longer string or more players would make Home Assistant reject every push. */
export const MAX_STRING = 200;
export const MAX_PLAYERS = 16;

function str(v: unknown): string | null {
  return typeof v === 'string' ? v.slice(0, MAX_STRING) : null;
}

const HEX_COLOR = /^#[0-9a-f]{6}$/i;

function color(v: unknown): string | null {
  return typeof v === 'string' && HEX_COLOR.test(v) ? v.toLowerCase() : null;
}

const MODES: GameMode[] = ['x01', 'cricket', 'tactics', 'other'];

export function emptySnapshot(): MatchSnapshot {
  return {
    active: false,
    matchId: null,
    variant: null,
    mode: null,
    round: null,
    currentPlayer: null,
    players: [],
    lastThrow: null,
    lastTurnPoints: null,
    winnerName: null,
    currentPlayerColor: null,
    nextPlayerColor: null,
  };
}

/** Match state for Home Assistant, built from the hub events */
export class MatchTracker {
  private state = emptySnapshot();
  private currentPosition: number | null = null;
  private cricketPoints = new Map<number, number>();

  snapshot(): MatchSnapshot {
    return structuredClone(this.state);
  }

  apply(event: { type: string; data: unknown }): void {
    const d = event.data;
    switch (event.type) {
      case 'match.start':
        this.reset();
        this.state.active = true;
        this.state.matchId = isObj(d) ? str(d.matchId) : null;
        return;
      case 'match.finish':
      case 'match.delete':
        this.reset();
        return;
      case 'match.state':
        if (isObj(d)) this.applyMatchState(d);
        return;
      case 'cricket.state':
        if (isObj(d)) this.applyCricketState(d);
        return;
      case 'throw.detected':
        if (isObj(d) && isObj(d.segment)) this.state.lastThrow = str(d.segment.name) ?? this.state.lastThrow;
        return;
      case 'turn.finished':
        if (isObj(d)) this.state.lastTurnPoints = num(d.turnScore) ?? this.state.lastTurnPoints;
        return;
      case 'match.finished':
        if (isObj(d)) this.state.winnerName = str(d.winnerName);
        return;
      case 'player.change':
        // The hub sends player.change before the match.state of the same update
        if (isObj(d)) {
          const position = num(d.currentPlayer);
          if (position !== null && Number.isInteger(position) && position >= 0 && position < this.state.players.length) {
            this.currentPosition = position;
            this.updateCurrentPlayer();
          }
        }
        return;
      default:
        return;
    }
  }

  private reset(): void {
    this.state = emptySnapshot();
    this.currentPosition = null;
    this.cricketPoints.clear();
  }

  private applyMatchState(d: Obj): void {
    if (!Array.isArray(d.players)) return;
    const scores = Array.isArray(d.gameScores) ? d.gameScores : [];
    const legsWon = isObj(d.legsWon) ? d.legsWon : {};
    const setsWon = isObj(d.setsWon) ? d.setsWon : {};
    const game = isObj(d.game) ? d.game : {};
    const mode = MODES.find((m) => m === game.mode) ?? null;

    this.state.active = true;
    this.state.matchId = str(d.matchId) ?? this.state.matchId;
    this.state.variant = str(d.variant) ?? str(game.variant);
    this.state.mode = mode;
    this.state.round = num(d.round);
    this.state.players = d.players.filter(isObj).slice(0, MAX_PLAYERS).map((p, position): PlayerSnapshot => {
      const index = num(p.index) ?? position;
      const marksGame = mode === 'cricket' || mode === 'tactics';
      const score = marksGame && this.cricketPoints.has(index) ? this.cricketPoints.get(index)! : num(scores[position]);
      return {
        index,
        name: str(p.name) ?? `Player ${position + 1}`,
        score,
        legsWon: num(legsWon[index]) ?? 0,
        setsWon: num(setsWon[index]) ?? 0,
        color: color(p.color),
      };
    });
    this.currentPosition = num(d.player);
    this.updateCurrentPlayer();
  }

  private applyCricketState(d: Obj): void {
    if (!Array.isArray(d.players)) return;
    for (const p of d.players.filter(isObj)) {
      const index = num(p.index);
      const points = num(p.points);
      if (index !== null && points !== null) this.cricketPoints.set(index, points);
    }
    for (const player of this.state.players) {
      if (this.cricketPoints.has(player.index)) player.score = this.cricketPoints.get(player.index)!;
    }
    this.updateCurrentPlayer();
  }

  private updateCurrentPlayer(): void {
    const players = this.state.players;
    const position = this.currentPosition;
    const current = position === null ? undefined : players[position];
    const next = current && players.length > 0 ? players[(position! + 1) % players.length] : undefined;
    this.state.currentPlayer = current ? { ...current } : null;
    this.state.currentPlayerColor = current?.color ?? null;
    this.state.nextPlayerColor = next?.color ?? null;
  }
}
