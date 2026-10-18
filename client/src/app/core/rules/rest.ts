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

export interface HitDieOption {
  dieSize: number;
  className: string;
  level: number;
}

/**
 * Lists the hit die pool options available to the character.
 * For multiclass characters, lists each class with its level and hit die size.
 * Single class characters return a single option.
 */
export function availableHitDieOptions(
  char: Pick<CharacterSchema, 'classes' | 'char_class' | 'char_level' | 'hit_dice'> | null | undefined
): HitDieOption[] {
  if (!char) return [];

  if (char.classes && char.classes.length > 0) {
    return char.classes.map((cls) => {
      const isMain = (cls.class_name || '').toLowerCase() === (char.char_class || '').toLowerCase();
      return {
        className: cls.class_name || 'Class',
        level: cls.level || 1,
        dieSize: isMain ? hitDieSize(char) : hitDieSidesFor(cls.class_name),
      };
    });
  }

  return [
    {
      className: char.char_class || 'Class',
      level: char.char_level || 1,
      dieSize: hitDieSize(char),
    },
  ];
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
 * to spend (unless Warlock Pact Magic slots can be recovered), which is the
 * caller's cue to leave the sheet alone entirely.
 */
export function planShortRest(
  char: CharacterSchema | null | undefined,
  requestedDice: number,
  overrideDieSize?: number
): ShortRestPlan | null {
  if (!char) return null;
  const available = availableHitDice(char);
  const conMod = conModifier(char);
  const resolvedDieSize = overrideDieSize && overrideDieSize > 0 ? overrideDieSize : hitDieSize(char);
  const pact = warlockPactDetails(char);

  if (available <= 0 || requestedDice <= 0) {
    if (pact && (available <= 0 || requestedDice === 0)) {
      return {
        diceSpent: 0,
        dieSize: resolvedDieSize,
        conModifier: conMod,
        conBonus: 0,
      };
    }
    if (available <= 0) return null;
  }

  let maxForDie = available;
  if (overrideDieSize && overrideDieSize > 0 && char.classes && char.classes.length > 0) {
    const matchingLevels = availableHitDieOptions(char)
      .filter((opt) => opt.dieSize === overrideDieSize)
      .reduce((sum, opt) => sum + (opt.level || 0), 0);
    if (matchingLevels > 0) {
      maxForDie = Math.min(available, matchingLevels);
    }
  }

  const diceSpent = Math.min(maxForDie, Math.max(1, requestedDice));

  return {
    diceSpent,
    dieSize: resolvedDieSize,
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
  pactDetails?: WarlockPactDetails | null;
}

export interface WarlockPactDetails {
  pactSlotLevel: number;
  pactSlotCount: number;
}

export function warlockPactDetails(
  char: Pick<CharacterSchema, 'char_class' | 'char_level' | 'classes'> | null | undefined
): WarlockPactDetails | null {
  if (!char) return null;
  let wLevel = 0;
  const mainClass = (char.char_class || '').toLowerCase();
  if (mainClass.includes('warlock')) {
    wLevel = char.char_level || 1;
  }
  if (char.classes && char.classes.length > 0) {
    const wEntry = char.classes.find(c => (c.class_name || '').toLowerCase().includes('warlock'));
    if (wEntry) {
      wLevel = wEntry.level || 1;
    }
  }

  if (wLevel <= 0) return null;

  let slotLvl = 1;
  let slotCount = 1;
  if (wLevel === 1) {
    slotLvl = 1;
    slotCount = 1;
  } else if (wLevel === 2) {
    slotLvl = 1;
    slotCount = 2;
  } else if (wLevel <= 4) {
    slotLvl = 2;
    slotCount = 2;
  } else if (wLevel <= 6) {
    slotLvl = 3;
    slotCount = 2;
  } else if (wLevel <= 8) {
    slotLvl = 4;
    slotCount = 2;
  } else if (wLevel <= 10) {
    slotLvl = 5;
    slotCount = 2;
  } else if (wLevel <= 16) {
    slotLvl = 5;
    slotCount = 3;
  } else {
    slotLvl = 5;
    slotCount = 4;
  }

  return { pactSlotLevel: slotLvl, pactSlotCount: slotCount };
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

  const pact = warlockPactDetails(char);

  const outcome: ShortRestOutcome = {
    rolled,
    hpGained: hpAfter - hpBefore,
    hpBefore,
    hpAfter,
    hitDiceUsed: (char.hit_dice_used || 0) + plan.diceSpent,
    restoresPactSlots: !!pact,
  };
  if (pact) {
    outcome.pactDetails = pact;
  }
  return outcome;
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
