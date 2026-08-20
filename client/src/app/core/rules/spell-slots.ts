import { CharacterSchema } from '../models/character.model';

export type SpellSlots = NonNullable<CharacterSchema['spell_slots']>;

/**
 * The sheet's fallback when a slot level is spent that it has never recorded.
 *
 * This is what the code has always done, and it is almost certainly wrong — four
 * slots is not a rule, it is a guess. Pinned here rather than fixed, because this
 * extraction may not change what the rules compute (see the follow-up issue).
 */
export const ASSUMED_SPELL_SLOT_MAX = 4;

/** How the sheet keys its slots: level 3 is `level_3`. */
export function spellSlotKey(level: number): string {
  return `level_${level}`;
}

export function spellSlotMax(char: CharacterSchema | null | undefined, level: number): number {
  return char?.spell_slots?.[spellSlotKey(level)]?.max || 0;
}

export function spellSlotUsed(char: CharacterSchema | null | undefined, level: number): number {
  return char?.spell_slots?.[spellSlotKey(level)]?.used || 0;
}

/** Whether the sheet records this level at all — an unrecorded level cannot be regained. */
export function hasSpellSlotLevel(
  char: CharacterSchema | null | undefined,
  level: number
): boolean {
  return !!char?.spell_slots?.[spellSlotKey(level)];
}

/**
 * Spends one slot at `level` and returns the whole record, rebuilt.
 *
 * Spending can never push `used` past `max`; a level the sheet has not recorded
 * is created at {@link ASSUMED_SPELL_SLOT_MAX}.
 */
export function spendSpellSlot(slots: SpellSlots | undefined, level: number): SpellSlots {
  const key = spellSlotKey(level);
  const next: SpellSlots = { ...(slots ?? {}) };
  const slot = next[key] ?? { max: ASSUMED_SPELL_SLOT_MAX, used: 0 };

  next[key] = { ...slot, used: Math.min(slot.max, slot.used + 1) };
  return next;
}

/** Gives one slot back at `level`. Never goes below 0; an unknown level is a no-op. */
export function regainSpellSlot(slots: SpellSlots | undefined, level: number): SpellSlots {
  const key = spellSlotKey(level);
  const next: SpellSlots = { ...(slots ?? {}) };
  const slot = next[key];
  if (!slot) return next;

  next[key] = { ...slot, used: Math.max(0, slot.used - 1) };
  return next;
}

/** Every level back to full — what a long rest, and a warlock's short rest, grant. */
export function restoreAllSpellSlots(slots: SpellSlots | undefined): SpellSlots {
  const next: SpellSlots = {};
  for (const [key, slot] of Object.entries(slots ?? {})) {
    next[key] = { ...slot, used: 0 };
  }
  return next;
}
