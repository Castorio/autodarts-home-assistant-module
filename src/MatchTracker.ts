import type { GameMode } from './types.js';
import type { MatchSnapshot, PlayerSnapshot } from './types.js';

type Obj = Record<string, unknown>;

function isObj(v: unknown): v is Obj {
  return typeof v === 'object' && v !== null;
}

function num(v: unknown): number | null {
  return typeof v === 'number' && Number.isFinite(v) ? v : null;
}

function str(v: unknown): string | null {
  return typeof v === 'string' ? v : null;
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
    this.state.players = d.players.filter(isObj).map((p, position): PlayerSnapshot => {
      const index = num(p.index) ?? position;
      const marksGame = mode === 'cricket' || mode === 'tactics';
      const score = marksGame && this.cricketPoints.has(index) ? this.cricketPoints.get(index)! : num(scores[position]);
      return {
        index,
        name: str(p.name) ?? `Player ${position + 1}`,
        score,
        legsWon: num(legsWon[index]) ?? 0,
        setsWon: num(setsWon[index]) ?? 0,
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
    const p = this.currentPosition === null ? undefined : this.state.players[this.currentPosition];
    this.state.currentPlayer = p ? { ...p } : null;
  }
}
