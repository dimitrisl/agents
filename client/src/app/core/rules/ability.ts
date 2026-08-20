import { CharacterSchema } from '../models/character.model';

/**
 * The numbers every roll on the sheet starts from.
 *
 * Nothing in this folder may import from `@angular/*`: these are the rules, not
 * the screen that shows them, and they have to be testable without a TestBed.
 */

/**
 * D&D's one universal formula. It had four separate copies inside
 * `player.component`, plus one in `character-state.service` and one in
 * `class-combat.service` — six chances for the same arithmetic to drift.
 *
 * It deliberately takes a bare score and nothing else. Every call site has its
 * own idea of what a *missing* score means, and baking one of them in here would
 * quietly change the others.
 */
export function abilityModifier(score: number): number {
  return Math.floor((score - 10) / 2);
}

/** `+3`, `-1`, `+0` — a modifier on a sheet is never shown as a bare number. */
export function formatModifier(value: number): string {
  return value >= 0 ? `+${value}` : `${value}`;
}

/** The score written on the sheet, or the 10 an unfilled line is assumed to be. */
export function abilityScore(char: CharacterSchema | null | undefined, ability: string): number {
  return char?.stats?.[ability] || 10;
}

export function abilityModifierOf(
  char: CharacterSchema | null | undefined,
  ability: string
): number {
  return abilityModifier(abilityScore(char, ability));
}

/** Proficiency is +2 at level 1, and +2 again for any sheet that forgot to say. */
export function proficiencyBonus(char: CharacterSchema | null | undefined): number {
  return char?.proficiency_bonus || 2;
}

export function isSaveProficient(
  char: CharacterSchema | null | undefined,
  ability: string
): boolean {
  return char?.saving_throws?.includes(ability) || false;
}

/** Ability modifier, plus proficiency when the class is trained in that save. */
export function savingThrowModifier(
  char: CharacterSchema | null | undefined,
  ability: string
): number {
  return (
    abilityModifierOf(char, ability) +
    (isSaveProficient(char, ability) ? proficiencyBonus(char) : 0)
  );
}
