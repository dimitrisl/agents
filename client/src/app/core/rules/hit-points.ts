import { CharacterSchema } from '../models/character.model';

/** A sheet that never wrote a current HP is at full health. */
export function currentHp(char: CharacterSchema): number {
  return char.hp_current ?? char.hp_max ?? 0;
}

/** HP lives between 0 and the maximum — the sheet has no negatives and no overheal. */
export function clampHp(hp: number, hpMax: number): number {
  return Math.max(0, Math.min(hpMax, hp));
}

/** Where the HP stepper lands after one click, damage or healing. */
export function adjustedHp(char: CharacterSchema, delta: number): number {
  return clampHp(currentHp(char) + delta, char.hp_max);
}

const INCAPACITATING_CONDITIONS = new Set([
  'incapacitated',
  'unconscious',
  'paralyzed',
  'petrified',
  'stunned',
]);

/**
 * RAW 5e / 2024: A character is incapacitated if at 0 HP or afflicted by an incapacitating condition.
 * A healthy character with hp_current undefined (full health) is NOT incapacitated.
 */
export function isIncapacitated(char: CharacterSchema): boolean {
  if (currentHp(char) <= 0) return true;
  if (!char.conditions || !Array.isArray(char.conditions)) return false;
  return char.conditions.some((c) =>
    INCAPACITATING_CONDITIONS.has(String(c || '').trim().toLowerCase())
  );
}
