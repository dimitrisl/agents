import { CharacterSchema } from '../models/character.model';
import {
  convertPointsToSlot,
  convertSlotToPoints,
  createdSlots,
  pointsFromSlot,
  regainSpellSlot,
  restoreAllSpellSlots,
} from './index';

function sorcerer(points: number, max = 8): CharacterSchema {
  return {
    spell_slots: {
      level_1: { max: 4, used: 0 },
      level_2: { max: 3, used: 1 },
      level_3: { max: 3, used: 3 },
      level_4: { max: 2, used: 0 },
    },
    class_resources: [
      { name: 'Rage', current: 1, max: 1, recharge: 'long' },
      { name: 'Sorcery Points', current: points, max, recharge: 'long', auto: true },
    ],
  } as unknown as CharacterSchema;
}

describe('flexible casting', () => {
  it('buys a slot with the table cost, even past the level max', () => {
    const result = convertPointsToSlot(sorcerer(8), 1)!;
    expect(result.class_resources[1].current).toBe(6); // 1st level costs 2
    expect(result.spell_slots['level_1']).toEqual({ max: 4, used: -1 }); // 5 of 4 left
    expect(createdSlots({ spell_slots: result.spell_slots } as CharacterSchema, 1)).toBe(1);
    expect(result.class_resources[0]).toEqual({ name: 'Rage', current: 1, max: 1, recharge: 'long' });
  });

  it('refuses a slot it cannot pay for, above 5th, or at a level the sheet lacks', () => {
    expect(convertPointsToSlot(sorcerer(4), 3)).toBeNull(); // 3rd costs 5
    expect(convertPointsToSlot(sorcerer(8), 5)).toBeNull(); // no 5th-level slots yet
    expect(convertPointsToSlot(sorcerer(5), 3)!.class_resources[1].current).toBe(0);
  });

  it('turns a slot into points equal to its level, capped at the pool max', () => {
    expect(pointsFromSlot(sorcerer(0), 2)).toBe(2);
    expect(pointsFromSlot(sorcerer(7), 4)).toBe(1);
    expect(pointsFromSlot(sorcerer(8), 1)).toBe(0); // already full
    expect(pointsFromSlot(sorcerer(0), 3)).toBe(0); // no 3rd-level slot left
    const result = convertSlotToPoints(sorcerer(3), 2)!;
    expect(result.class_resources[1].current).toBe(5);
    expect(result.spell_slots['level_2']).toEqual({ max: 3, used: 2 });
  });

  it('lets a created slot vanish on a long rest and not be undone by the restore button', () => {
    const slots = convertPointsToSlot(sorcerer(8), 1)!.spell_slots;
    expect(regainSpellSlot(slots, 1)['level_1'].used).toBe(-1);
    expect(restoreAllSpellSlots(slots)['level_1'].used).toBe(0);
  });

  it('does nothing for a hero without sorcery points', () => {
    const fighter = { spell_slots: { level_1: { max: 2, used: 0 } }, class_resources: [] } as unknown as CharacterSchema;
    expect(convertPointsToSlot(fighter, 1)).toBeNull();
    expect(convertSlotToPoints(fighter, 1)).toBeNull();
  });
});
