import { throwTags, turnTags, type ThrowLike, type TurnLike } from './tags.js';
import type { MatchSnapshot, PushPayload, PushType, PushValue, Tag } from './types.js';

type Obj = Record<string, unknown>;

const MAX_STRING = 200;

const MAPPING: Record<string, { type: PushType; fields: string[] }> = {
  'match.start': { type: 'match_started', fields: ['matchId'] },
  'match.delete': { type: 'match_cancelled', fields: ['matchId'] },
  'match.finish': { type: 'match_closed', fields: ['matchId'] },
  'match.finished': { type: 'match_finished', fields: ['winnerName', 'winnerPlayerIndex'] },
  'game.finished': { type: 'leg_finished', fields: ['winnerName', 'winnerPlayerIndex', 'leg', 'set'] },
  'player.change': { type: 'player_changed', fields: ['playerName', 'playerIndex', 'remaining'] },
  'turn.finished': { type: 'turn_finished', fields: ['playerName', 'playerIndex', 'turnScore', 'remaining', 'busted', 'round'] },
  'cricket.closed': { type: 'cricket_closed', fields: ['field', 'playerName', 'playerIndex'] },
  'match.state': { type: 'state', fields: [] },
  'cricket.state': { type: 'state', fields: [] },
};

function scalar(v: unknown): PushValue {
  if (typeof v === 'string') return v.slice(0, MAX_STRING);
  if (typeof v === 'boolean') return v;
  if (typeof v === 'number' && Number.isFinite(v)) return v;
  return null;
}

function pick(d: Obj, fields: string[]): Record<string, PushValue> {
  const out: Record<string, PushValue> = {};
  for (const f of fields) out[f] = scalar(d[f]);
  return out;
}

function isObj(v: unknown): v is Obj {
  return typeof v === 'object' && v !== null;
}

/** Hub event -> slim payload for the Home Assistant webhook (null = not forwarded) */
export function mapEvent(event: { type: string; data: unknown }, state: MatchSnapshot, now: Date): PushPayload | null {
  const d: Obj = isObj(event.data) ? event.data : {};
  let type: PushType;
  let data: Record<string, PushValue>;
  let tags: Tag[] = [];

  if (event.type === 'throw.detected') {
    if (!isObj(d.segment)) return null;
    const seg = d.segment;
    type = 'throw';
    data = {
      segment: scalar(seg.name),
      number: scalar(seg.number),
      multiplier: scalar(seg.multiplier),
      points: scalar(d.points),
      turnPoints: scalar(d.turnPoints),
      busted: d.busted === true,
    };
    tags = throwTags(d as unknown as ThrowLike);
  } else {
    const m = MAPPING[event.type];
    if (!m) return null;
    type = m.type;
    data = pick(d, m.fields);
    if (event.type === 'turn.finished') tags = turnTags(d as unknown as TurnLike);
  }

  return { v: 1, type, ts: now.toISOString(), tags, data, state };
}
