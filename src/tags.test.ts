import { describe, it, expect } from 'vitest';
import { throwTags, turnTags } from './tags.js';

const x01 = { mode: 'x01' };
const cricket = { mode: 'cricket' };

describe('throwTags', () => {
  it('marks a triple 20 completing 180 in x01', () => {
    expect(throwTags({ segment: { number: 20, multiplier: 3 }, points: 60, turnPoints: 180, game: x01 }))
      .toEqual(['180', 'triple']);
  });

  it('does not mark 180 in cricket', () => {
    expect(throwTags({ segment: { number: 20, multiplier: 3 }, points: 60, turnPoints: 180, game: cricket }))
      .toEqual(['triple']);
  });

  it('marks bullseye but not double for 50', () => {
    expect(throwTags({ segment: { number: 25, multiplier: 2 }, points: 50, game: x01 })).toEqual(['bullseye']);
  });

  it('marks single bull', () => {
    expect(throwTags({ segment: { number: 25, multiplier: 1 }, points: 25, game: x01 })).toEqual(['bull']);
  });

  it('marks double and bust together', () => {
    expect(throwTags({ segment: { number: 16, multiplier: 2 }, points: 32, busted: true, game: x01 }))
      .toEqual(['bust', 'double']);
  });

  it('marks a miss', () => {
    expect(throwTags({ segment: { number: 5, multiplier: 0 }, points: 0, game: x01 })).toEqual(['miss']);
  });

  it('returns no tags for a single', () => {
    expect(throwTags({ segment: { number: 7, multiplier: 1 }, points: 7, game: x01 })).toEqual([]);
  });
});

describe('turnTags', () => {
  it('marks a checkout of 100 or more in x01', () => {
    expect(turnTags({ turnScore: 121, remaining: 0, busted: false, game: x01 })).toEqual(['high_finish']);
  });

  it('ignores a checkout below 100', () => {
    expect(turnTags({ turnScore: 40, remaining: 0, busted: false, game: x01 })).toEqual([]);
  });

  it('ignores a high turn that is not a checkout', () => {
    expect(turnTags({ turnScore: 140, remaining: 81, busted: false, game: x01 })).toEqual([]);
  });

  it('ignores busts and non-x01 games', () => {
    expect(turnTags({ turnScore: 120, remaining: 0, busted: true, game: x01 })).toEqual([]);
    expect(turnTags({ turnScore: 120, remaining: 0, busted: false, game: cricket })).toEqual([]);
  });
});
