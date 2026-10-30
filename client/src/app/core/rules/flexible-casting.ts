import { CharacterSchema, ClassResource } from '../models/character.model';
import { SpellSlots, spellSlotKey } from './spell-slots';

/**
 * The Sorcerer's Font of Magic / Flexible Casting (same numbers in 2014 and 2024).
 *
 * - Slot → points: expend a slot, gain points equal to its level, never past the
 *   pool's max.
 * - Points → slot: pay the table's cost for a slot of 1st–5th level. A created
 *   slot can go beyond the level's normal max and vanishes on a long rest.
 *
 * A created slot is stored as a negative `used` (max 2, used -1 → 3 left): the
 * long rest already resets `used` to 0, which is exactly "it vanishes", and the
 * server keeps `used` as sent. Only levels the sheet records can be created,
 * which matches the 2024 minimum Sorcerer levels (2nd at 3, 3rd at 5, 4th at 7,
 * 5th at 9).
 */
export const SLOT_CREATION_COST: Readonly<Record<number, number>> = { 1: 2, 2: 3, 3: 5, 4: 6, 5: 7 };

const POOL_NAMES = ['sorcery points', 'sorcery point', 'font of magic'];

export function sorceryPointsPool(char: CharacterSchema | null | undefined): ClassResource | null {
  return (
    (char?.class_resources ?? []).find((r) => POOL_NAMES.includes((r.name || '').trim().toLowerCase())) ?? null
  );
}

export interface FlexibleCastingResult {
  spell_slots: SpellSlots;
  class_resources: ClassResource[];
}

function withPool(char: CharacterSchema, pool: ClassResource, current: number): ClassResource[] {
  return (char.class_resources ?? []).map((r) => (r === pool ? { ...r, current } : r));
}

/** Points a slot of `level` would give right now: its level, capped by the room left in the pool. */
export function pointsFromSlot(char: CharacterSchema | null | undefined, level: number): number {
  const pool = sorceryPointsPool(char);
  const slot = char?.spell_slots?.[spellSlotKey(level)];
  if (!pool || !slot || slot.max - slot.used <= 0) return 0;
  return Math.max(0, Math.min(level, pool.max - pool.current));
}

export function convertSlotToPoints(char: CharacterSchema, level: number): FlexibleCastingResult | null {
  const gain = pointsFromSlot(char, level);
  const pool = sorceryPointsPool(char);
  if (!gain || !pool) return null;

  const key = spellSlotKey(level);
  const slot = char.spell_slots![key];
  return {
    spell_slots: { ...char.spell_slots, [key]: { ...slot, used: slot.used + 1 } },
    class_resources: withPool(char, pool, pool.current + gain),
  };
}

export function canCreateSlot(char: CharacterSchema | null | undefined, level: number): boolean {
  const pool = sorceryPointsPool(char);
  const cost = SLOT_CREATION_COST[level];
  return !!pool && !!cost && !!char?.spell_slots?.[spellSlotKey(level)] && pool.current >= cost;
}

export function convertPointsToSlot(char: CharacterSchema, level: number): FlexibleCastingResult | null {
  if (!canCreateSlot(char, level)) return null;
  const pool = sorceryPointsPool(char)!;
  const key = spellSlotKey(level);
  const slot = char.spell_slots![key];
  return {
    spell_slots: { ...char.spell_slots, [key]: { ...slot, used: slot.used - 1 } },
    class_resources: withPool(char, pool, pool.current - SLOT_CREATION_COST[level]),
  };
}

/** Slots made with sorcery points still waiting at this level (they vanish on a long rest). */
export function createdSlots(char: CharacterSchema | null | undefined, level: number): number {
  return Math.max(0, -(char?.spell_slots?.[spellSlotKey(level)]?.used ?? 0));
}
