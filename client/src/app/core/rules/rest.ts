import { CharacterSchema, ClassResource } from '../models/character.model';
import { hitDieSidesFor } from '../data/class-combat.data';
import { abilityModifierOf, is2024Edition, proficiencyBonus } from './ability';
import { currentHp } from './hit-points';
import { SpellSlots, regainSpellSlot } from './spell-slots';

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
  char: Pick<CharacterSchema, 'hit_dice' | 'char_class' | 'classes'> | null | undefined
): number {
  const isMulticlass =
    (char?.classes?.length ?? 0) > 1 || (char?.hit_dice || '').includes(',');
  if (isMulticlass) {
    return hitDieSidesFor(char?.char_class);
  }
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
    const isMulticlass = char.classes.length > 1;
    return char.classes.map((cls) => {
      const isMain = (cls.class_name || '').toLowerCase() === (char.char_class || '').toLowerCase();
      return {
        className: cls.class_name || 'Class',
        level: cls.level || 1,
        dieSize: !isMulticlass && isMain ? hitDieSize(char) : hitDieSidesFor(cls.class_name),
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
  const canRecoverSlots = !!pact || hasShortRestSlotRecovery(char);

  if (available <= 0 || requestedDice <= 0) {
    if (canRecoverSlots && (available <= 0 || requestedDice === 0)) {
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
  hpMax: number;
  /**
   * Hit dice recovered: all hit dice under 2024 Revision,
   * or half the hero's total hit dice (never fewer than one) under 2014 rules.
   */
  hitDiceRecovered: number;
  hitDiceUsed: number;
  exhaustionLevel: number;
}

/**
 * A long rest is unconditional: full HP, every spell slot back,
 * and Hit Point Dice recovery (all hit dice in 2024 Revision, half in 2014 rules).
 *
 * In 2024 Revision (PHB 2024, p. 370 "Long Rest"), the character recovers
 * all spent Hit Point Dice (`hitDiceRecovered = totalHitDice`, `hitDiceUsed = 0`).
 *
 * In 2014 edition, the character recovers up to half their total hit dice
 * (minimum of 1 die).
 */
export function resolveLongRest(char: CharacterSchema): LongRestOutcome {
  const is2024 = is2024Edition(char);
  const totalHitDice = char.char_level || 1;
  const hitDiceRecovered = is2024 ? totalHitDice : (Math.floor(totalHitDice / 2) || 1);
  const hitDiceUsed = is2024 ? 0 : Math.max(0, (char.hit_dice_used || 0) - hitDiceRecovered);
  const exhaustionLevel = Math.max(0, Math.floor(Number(char.exhaustion_level) || 0) - 1);
  const hpMax = !is2024 && exhaustionLevel < 4 && (char.exhaustion_level ?? 0) >= 4 && char.base_hp_max
    ? char.base_hp_max
    : char.hp_max;

  return {
    hpCurrent: hpMax,
    hpMax,
    hitDiceRecovered,
    hitDiceUsed,
    exhaustionLevel,
  };
}

/**
 * Recharges class resource pools on a Short Rest.
 * Under 2024 rules, Rage, Second Wind, Channel Divinity, and Wild Shape
 * regain 1 expended use on a Short Rest (all uses on a Long Rest), whereas
 * Focus/Ki Points, Action Surge, and 2014 short-rest pools recharge to full.
 */
/**
 * Resolves the 2014 PHB Bard Song of Rest extra healing die ('1d6'..'1d12'),
 * returning null for 2024 Bards or non-Bards below level 2.
 */
export function songOfRestDie(char: CharacterSchema | null | undefined): string | null {
  if (!char || is2024Edition(char)) return null;
  let bardLevel = 0;
  if (char.classes && char.classes.length > 0) {
    const bardEntry = char.classes.find(
      (c) => (c.class_name || '').trim().toLowerCase() === 'bard'
    );
    bardLevel = bardEntry?.level || 0;
  } else if ((char.char_class || '').trim().toLowerCase() === 'bard') {
    bardLevel = char.char_level || 1;
  }
  if (bardLevel < 2) return null;
  if (bardLevel >= 17) return '1d12';
  if (bardLevel >= 13) return '1d10';
  if (bardLevel >= 9) return '1d8';
  return '1d6';
}

export function rechargeShortRestResources(
  resources: ClassResource[] | undefined,
  edition?: string,
  char?: Pick<CharacterSchema, 'char_class' | 'char_level' | 'classes' | 'features_traits'> | null
): ClassResource[] {
  if (!resources) return [];
  const is2024 = String(edition || '').includes('2024');
  let sorcLevel = 0;
  if (char?.classes && char.classes.length > 0) {
    const sorcEntry = char.classes.find(
      (c) => (c.class_name || '').trim().toLowerCase() === 'sorcerer'
    );
    sorcLevel = sorcEntry?.level || 0;
  } else if ((char?.char_class || '').trim().toLowerCase() === 'sorcerer') {
    sorcLevel = char?.char_level || 1;
  }
  const hasSorcRestorationFeature = (char?.features_traits || []).some((f) => {
    const name = typeof f === 'string' ? f : f?.name || '';
    return name.toLowerCase().includes('sorcerous restoration');
  });
  const canRestore2014SorceryPoints = !is2024 && (sorcLevel >= 20 || hasSorcRestorationFeature);

  return resources.map((r) => {
    const nameClean = (r.name || '').trim().toLowerCase();
    if (is2024 && /^(rage|second wind|channel divinity|wild shape)$/i.test(nameClean)) {
      return { ...r, current: Math.min(r.max, (r.current ?? 0) + 1) };
    }
    if (
      canRestore2014SorceryPoints &&
      (nameClean === 'sorcery points' || nameClean === 'sorcery point' || nameClean === 'font of magic')
    ) {
      return { ...r, current: Math.min(r.max, (r.current ?? 0) + 4) };
    }
    if (r.recharge === 'short') {
      return { ...r, current: r.max };
    }
    return { ...r };
  });
}

function classLevelForRest(
  char: Pick<CharacterSchema, 'char_class' | 'char_level' | 'classes'> | null | undefined,
  target: string
): number {
  if (!char) return 0;
  let lvl = 0;
  for (const c of char.classes || []) {
    if ((c.class_name || '').trim().toLowerCase() === target) {
      lvl += Math.max(0, Number(c.level || 0));
    }
  }
  if (lvl === 0 && (char.char_class || '').trim().toLowerCase() === target) {
    lvl = Math.max(1, Number(char.char_level || 1));
  }
  return lvl;
}

function hasAvailableResourcePool(
  char: Pick<CharacterSchema, 'class_resources'> | null | undefined,
  poolName: string
): boolean {
  const target = poolName.trim().toLowerCase();
  return (char?.class_resources || []).some(
    (r) => (r.name || '').trim().toLowerCase() === target && Number(r.current ?? 0) >= 1
  );
}

/** Combined spell-level recovery budget (1..5th level slots only) for Arcane Recovery / Natural Recovery, or 0 if unavailable. */
export function shortRestRecoveryBudget(
  char: CharacterSchema | null | undefined,
  kind: 'arcane_recovery' | 'natural_recovery'
): number {
  if (!char) return 0;
  if (kind === 'arcane_recovery') {
    const wizLvl = classLevelForRest(char, 'wizard');
    if (wizLvl <= 0 || !hasAvailableResourcePool(char, 'Arcane Recovery')) return 0;
    return Math.ceil(wizLvl / 2);
  }
  const druidLvl = classLevelForRest(char, 'druid');
  if (druidLvl <= 0 || !hasAvailableResourcePool(char, 'Natural Recovery')) return 0;
  const hasLandSubclass =
    (char.classes || []).some(
      (c) =>
        (c.class_name || '').trim().toLowerCase() === 'druid' &&
        (c.subclass || '').toLowerCase().includes('land')
    ) || (char.subclass || '').toLowerCase().includes('land');
  const hasFeature = (char.features_traits || []).some((f) =>
    (typeof f === 'string' ? f : f?.name || '').toLowerCase().includes('natural recovery')
  );
  const minLvl = !is2024Edition(char) || hasFeature ? 2 : 6;
  if (!hasLandSubclass && !hasFeature) return 0;
  return druidLvl >= minLvl ? Math.ceil(druidLvl / 2) : 0;
}

/** Max spell slot level recoverable by Harness Divine Power (Cleric 2+ / Paladin 3+ with Channel Divinity), or 0 if unavailable. */
export function harnessDivinePowerMaxSlotLevel(char: CharacterSchema | null | undefined): number {
  if (!char) return 0;
  const clericLvl = classLevelForRest(char, 'cleric');
  const paladinLvl = classLevelForRest(char, 'paladin');
  if (clericLvl < 2 && paladinLvl < 3) return 0;
  if (!hasAvailableResourcePool(char, 'Channel Divinity')) return 0;
  return Math.ceil(proficiencyBonus(char) / 2);
}

export function hasShortRestSlotRecovery(char: CharacterSchema | null | undefined): boolean {
  return (
    shortRestRecoveryBudget(char, 'arcane_recovery') > 0 ||
    shortRestRecoveryBudget(char, 'natural_recovery') > 0 ||
    harnessDivinePowerMaxSlotLevel(char) > 0
  );
}

export function applyShortRestSlotRecovery(
  slots: SpellSlots | undefined,
  resources: ClassResource[] | undefined,
  selection: {
    arcaneRecoverySlots?: Record<number, number>;
    naturalRecoverySlots?: Record<number, number>;
    harnessDivinePowerSlot?: number | null;
  }
): { spell_slots: SpellSlots; class_resources: ClassResource[] } {
  let nextSlots: SpellSlots = { ...(slots ?? {}) };
  let nextResources: ClassResource[] = (resources ?? []).map((r) => ({ ...r }));

  const consumePool = (name: string) => {
    const target = name.trim().toLowerCase();
    const idx = nextResources.findIndex((r) => (r.name || '').trim().toLowerCase() === target);
    if (idx >= 0 && nextResources[idx].current > 0) {
      nextResources[idx] = { ...nextResources[idx], current: nextResources[idx].current - 1 };
    }
  };

  const applyMap = (map: Record<number, number> | undefined, poolName: string) => {
    if (!map) return;
    let spent = false;
    for (const [lvlStr, rawCount] of Object.entries(map)) {
      const lvl = Number(lvlStr);
      const count = Math.max(0, Math.trunc(Number(rawCount) || 0));
      if (!lvl || lvl >= 6 || count <= 0) continue;
      spent = true;
      for (let i = 0; i < count; i++) {
        nextSlots = regainSpellSlot(nextSlots, lvl);
      }
    }
    if (spent) consumePool(poolName);
  };

  applyMap(selection.arcaneRecoverySlots, 'Arcane Recovery');
  applyMap(selection.naturalRecoverySlots, 'Natural Recovery');

  if (selection.harnessDivinePowerSlot && selection.harnessDivinePowerSlot >= 1) {
    nextSlots = regainSpellSlot(nextSlots, selection.harnessDivinePowerSlot);
    consumePool('Channel Divinity');
  }

  return { spell_slots: nextSlots, class_resources: nextResources };
}
