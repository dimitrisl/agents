import { CharacterSchema } from '../models/character.model';
import { hitDieSidesFor } from '../data/class-combat.data';
import { abilityModifierOf } from './ability';
import { currentHp } from './hit-points';

/**
 * Short and long rests: what a hero gets back, and what it costs them.
 *
 * The dice themselves are not thrown here. A rest is planned, rolled by the
 * caller's `DiceService`, then resolved — which is what keeps the arithmetic
 * testable without stubbing randomness.
 */

/**
 * The die a sheet actually spends: its own `hit_dice` entry wins, and the class
 * table only fills the gap. A malformed string (`"five"`, `"3"`, `""`) has no
 * `dN` in it and falls back the same way a missing one does.
 *
 * This is the *only* class → die lookup now. The player sheet used to carry a
 * second one that ignored `hit_dice` entirely, so a wizard whose sheet said d10
 * was told to roll a d10 by the action dock and then quietly handed a d6 by the
 * short rest.
 */
export function hitDieSize(
  char: Pick<CharacterSchema, 'hit_dice' | 'char_class'> | null | undefined
): number {
  const parsed = /d(\d+)/i.exec(char?.hit_dice || '');
  return parsed ? parseInt(parsed[1], 10) : hitDieSidesFor(char?.char_class);
}

export function conModifier(char: CharacterSchema | null | undefined): number {
  return abilityModifierOf(char, 'CON');
}

/** Hit dice left to spend. A sheet that over-reports its spent dice still has 0, never fewer. */
export function availableHitDice(char: CharacterSchema | null | undefined): number {
  if (!char) return 0;
  return Math.max(0, (char.char_level || 1) - (char.hit_dice_used || 0));
}

export interface ShortRestPlan {
  /** Dice actually spent — at least one, never more than are left. */
  diceSpent: number;
  dieSize: number;
  conModifier: number;
  /** CON applies once per die spent, so it is folded into a single roll modifier. */
  conBonus: number;
}

/**
 * Works out what the hero is about to throw. Returns `null` when there is nothing
 * to spend, which is the caller's cue to leave the sheet alone entirely.
 */
export function planShortRest(
  char: CharacterSchema | null | undefined,
  requestedDice: number
): ShortRestPlan | null {
  const available = availableHitDice(char);
  if (available <= 0) return null;

  const diceSpent = Math.min(available, Math.max(1, requestedDice));
  const conMod = conModifier(char);

  return {
    diceSpent,
    dieSize: hitDieSize(char),
    conModifier: conMod,
    conBonus: conMod * diceSpent,
  };
}

export interface ShortRestOutcome {
  /** What the dice came to, floored at 0. This is the number the roll display shows. */
  rolled: number;
  /** What the hero actually got — never more than the gap to `hp_max`. */
  hpGained: number;
  hpBefore: number;
  hpAfter: number;
  hitDiceUsed: number;
  /** Warlocks recharge their pact slots on a short rest, not a long one. */
  restoresPactSlots: boolean;
}

/**
 * Turns the rolled total into the sheet's new numbers.
 *
 * `rollTotal` already carries {@link ShortRestPlan.conBonus}, so a CON 6 hero
 * spending one die can hand a negative number in. A rest is never a wound: the
 * heal floors at 0, and healing can never carry past `hp_max`.
 *
 * `rolled` and `hpGained` are separate on purpose. A hero at 40/44 who rolls a
 * 24 rolled a 24 and gained 4, and the sheet used to report the 24 as HP healed.
 */
export function resolveShortRest(
  char: CharacterSchema,
  plan: ShortRestPlan,
  rollTotal: number
): ShortRestOutcome {
  const rolled = Math.max(0, rollTotal);
  const hpBefore = currentHp(char);
  const hpAfter = Math.min(char.hp_max, hpBefore + rolled);

  return {
    rolled,
    hpGained: hpAfter - hpBefore,
    hpBefore,
    hpAfter,
    hitDiceUsed: (char.hit_dice_used || 0) + plan.diceSpent,
    restoresPactSlots: (char.char_class || '').toLowerCase().includes('warlock'),
  };
}

export interface LongRestOutcome {
  hpCurrent: number;
  /** Half the hero's total hit dice, and never fewer than one. */
  hitDiceRecovered: number;
  hitDiceUsed: number;
}

/**
 * A long rest is unconditional: full HP, every spell slot back, half the hit dice.
 *
 * The `|| 1` on the recovery count is what stops a level 1 hero — `floor(1 / 2)`
 * is 0 — from getting nothing at all.
 */
export function resolveLongRest(char: CharacterSchema): LongRestOutcome {
  const totalHitDice = char.char_level || 1;
  const hitDiceRecovered = Math.floor(totalHitDice / 2) || 1;

  return {
    hpCurrent: char.hp_max,
    hitDiceRecovered,
    hitDiceUsed: Math.max(0, (char.hit_dice_used || 0) - hitDiceRecovered),
  };
}
