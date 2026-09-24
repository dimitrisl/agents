/**
 * Level-scaling combat dice, per class and edition.
 *
 * This table exists because `data/rules/classes/{2014,2024}/*.json` stores feature
 * *prose* but not the tables the prose refers to: the Rogue entry says the extra
 * damage grows "as shown in the Sneak Attack column of the Rogue table" and that
 * column is nowhere in the file. There is also no endpoint that would serve class
 * progression to the client. Until both of those are fixed (see
 * `docs/BACKEND_COMBAT_RULES_TODO.md`) the numbers live here.
 *
 * Keep this file free of Angular: it is the data seam. When the backend starts
 * serving scaling tables, only `ClassCombatService` has to change.
 */

export type CombatActionKind = 'rider' | 'attack' | 'heal' | 'defense' | 'utility';

/** Everything a blueprint is allowed to look at when it resolves its numbers. */
export interface CombatContext {
  charClass: string;
  subclass: string;
  level: number;
  is2024: boolean;
  mods: Record<'STR' | 'DEX' | 'CON' | 'INT' | 'WIS' | 'CHA', number>;
  profBonus: number;
}

export interface CombatActionOption {
  label: string;
  notation: string;
}

/** A class feature resolved down to the dice this particular character rolls. */
export interface ClassCombatAction {
  id: string;
  name: string;
  icon: string;
  kind: CombatActionKind;
  /** Dice notation, already resolved for the character's level. */
  notation: string;
  hint: string;
  /** `Rogue 10` — makes it obvious where the number came from. */
  source: string;
  damageType?: string;
  /** False for reference-only entries such as a Lay on Hands pool. */
  rollable: boolean;
  /** Alternative notations the card offers, e.g. Divine Smite per slot level. */
  options?: CombatActionOption[];
}

export interface CombatProfile {
  actions: ClassCombatAction[];
  /** Extra weapon damage dice on a crit — Barbarian's Brutal Critical. */
  extraCritDice: number;
  /** Lowest d20 face that crits — Champion's Improved Critical. */
  critThreshold: number;
  /** How many dice a damage cantrip rolls at this level (1–4). */
  cantripTier: number;
}

export function extraCritDiceFor(ctx: CombatContext): number {
  if (ctx.charClass.toLowerCase().trim() !== 'barbarian' || ctx.is2024) return 0;
  if (ctx.level >= 17) return 3;
  if (ctx.level >= 13) return 2;
  if (ctx.level >= 9) return 1;
  return 0;
}

/** Improved Critical, expressed as the lowest d20 face that still crits. */
export function critThresholdFor(ctx: CombatContext): number {
  const isChampion =
    ctx.charClass.toLowerCase().trim() === 'fighter' &&
    ctx.subclass.toLowerCase().includes('champion');
  if (!isChampion) return 20;
  if (ctx.level >= 15) return 18;
  if (ctx.level >= 3) return 19;
  return 20;
}

function titleCase(value: string): string {
  return value ? value.charAt(0).toUpperCase() + value.slice(1).toLowerCase() : value;
}

const HIT_DICE: Record<string, number> = {
  artificer: 8,
  barbarian: 12,
  bard: 8,
  cleric: 8,
  druid: 8,
  fighter: 10,
  monk: 8,
  paladin: 10,
  ranger: 10,
  rogue: 8,
  sorcerer: 6,
  warlock: 8,
  wizard: 6,
};

export const hitDieSidesFor = (charClass: string | undefined): number => {
  const name = (charClass || '').toLowerCase().trim();
  if (!name) return 8;

  const exact = HIT_DICE[name];
  if (exact) return exact;

  const matched = Object.keys(HIT_DICE).find((known) => name.includes(known));
  return matched ? HIT_DICE[matched] : 8;
};

const CASTER_CLASSES = new Set([
  'artificer',
  'bard',
  'cleric',
  'druid',
  'sorcerer',
  'warlock',
  'wizard',
]);

export const isCaster = (charClass: string): boolean =>
  CASTER_CLASSES.has((charClass || '').toLowerCase().trim());
