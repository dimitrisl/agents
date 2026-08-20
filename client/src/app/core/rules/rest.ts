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
 * The player sheet's own class → hit die table.
 *
 * It matches on a substring, so `Eldritch Knight Fighter` still finds its d10.
 * That is deliberately *not* the same lookup as {@link hitDieSize}: the exact
 * table in `class-combat.data` would give that same fighter a d8. Both are
 * preserved as-is here; reconciling them is a rules change, not a refactor.
 */
export function classHitDieSize(charClass: string | undefined): number {
  const c = (charClass || '').toLowerCase();
  if (c.includes('barbarian')) return 12;
  if (c.includes('fighter') || c.includes('paladin') || c.includes('ranger')) return 10;
  if (c.includes('sorcerer') || c.includes('wizard')) return 6;
  return 8; // Bard, Cleric, Druid, Monk, Rogue, Warlock
}

/**
 * The die a sheet actually spends: its own `hit_dice` entry wins, and the class
 * default only fills the gap. A malformed string (`"five"`, `"3"`, `""`) has no
 * `dN` in it and falls back the same way a missing one does.
 */
export function hitDieSize(char: Pick<CharacterSchema, 'hit_dice' | 'char_class'>): number {
  const parsed = /d(\d+)/i.exec(char.hit_dice || '');
  return parsed ? parseInt(parsed[1], 10) : hitDieSidesFor(char.char_class);
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
    dieSize: classHitDieSize(char?.char_class),
    conModifier: conMod,
    conBonus: conMod * diceSpent,
  };
}

export interface ShortRestOutcome {
  /** Never negative — see below. */
  healed: number;
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
 */
export function resolveShortRest(
  char: CharacterSchema,
  plan: ShortRestPlan,
  rollTotal: number
): ShortRestOutcome {
  const healed = Math.max(0, rollTotal);
  const hpBefore = currentHp(char);

  return {
    healed,
    hpBefore,
    hpAfter: Math.min(char.hp_max, hpBefore + healed),
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
