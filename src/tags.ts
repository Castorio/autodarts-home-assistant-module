import type { Tag } from './types.js';

interface GameLike {
  mode?: string;
}

export interface ThrowLike {
  segment: { number: number; multiplier: number };
  points?: number;
  turnPoints?: number;
  busted?: boolean;
  game?: GameLike;
}

export interface TurnLike {
  turnScore: number;
  remaining: number;
  busted: boolean;
  game?: GameLike;
}

function isMarksGame(game?: GameLike): boolean {
  return game?.mode === 'cricket' || game?.mode === 'tactics';
}

/** Tags of one dart, same rules as the WLED reference (modules/wled/src/WledHandler.ts) */
export function throwTags(t: ThrowLike): Tag[] {
  const tags: Tag[] = [];
  const { number, multiplier } = t.segment;
  if (!isMarksGame(t.game) && t.turnPoints === 180) tags.push('180');
  if (t.busted === true) tags.push('bust');
  if (number === 25 && multiplier === 2) tags.push('bullseye');
  else if (number === 25 && multiplier === 1) tags.push('bull');
  else if (multiplier === 3) tags.push('triple');
  else if (multiplier === 2) tags.push('double');
  if (multiplier === 0 || t.points === 0) tags.push('miss');
  return tags;
}

/** A checkout of 100 or more in x01 */
export function turnTags(t: TurnLike): Tag[] {
  if (t.game?.mode !== 'x01' || t.busted || t.remaining !== 0 || t.turnScore < 100) return [];
  return ['high_finish'];
}
