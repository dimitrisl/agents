import { CharacterSchema } from '../models/character.model';

/** A sheet that never wrote a current HP is at full health. */
export function currentHp(char: CharacterSchema): number {
  return char.hp_current ?? char.hp_max;
}

/** HP lives between 0 and the maximum — the sheet has no negatives and no overheal. */
export function clampHp(hp: number, hpMax: number): number {
  return Math.max(0, Math.min(hpMax, hp));
}

/** Where the HP stepper lands after one click, damage or healing. */
export function adjustedHp(char: CharacterSchema, delta: number): number {
  return clampHp(currentHp(char) + delta, char.hp_max);
}
