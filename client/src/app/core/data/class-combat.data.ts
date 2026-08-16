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

type Resolver<T> = T | ((ctx: CombatContext) => T);

interface FeatureStep {
  level: number;
  notation: Resolver<string>;
}

interface FeatureBlueprint {
  id: string;
  name: Resolver<string>;
  icon: string;
  kind: CombatActionKind;
  hint: Resolver<string>;
  /** Highest step at or below the character's level wins. */
  steps: FeatureStep[];
  damageType?: string;
  /** Restricts the feature to one edition; omit when both share it. */
  edition?: '2014' | '2024';
  /** Case-insensitive substring the character's subclass must contain. */
  subclass?: string;
  rollable?: boolean;
  options?: (ctx: CombatContext) => CombatActionOption[];
}

const signed = (value: number): string => (value >= 0 ? `+${value}` : `${value}`);

/** `2d8`, and `1d8` reads better than `1d8` with an explicit 1 stripped. */
const dice = (count: number, sides: number): string => `${count}d${sides}`;

const ORDINALS = ['', '1st', '2nd', '3rd', '4th', '5th', '6th', '7th', '8th', '9th'];

/** Highest spell slot level a half caster (Paladin, Ranger) has unlocked. */
const halfCasterMaxSlot = (level: number): number => Math.min(5, Math.floor((level + 1) / 4) + 1);

/**
 * Damage cantrips gain a die at 5th, 11th and 17th *character* level. Used for the
 * reference chip casters get, not for a roll — the die size is the spell's, not the class's.
 */
export const cantripTierFor = (level: number): number =>
  level >= 17 ? 4 : level >= 11 ? 3 : level >= 5 ? 2 : 1;

const CASTER_CLASSES = new Set([
  'artificer',
  'bard',
  'cleric',
  'druid',
  'sorcerer',
  'warlock',
  'wizard',
]);

/** Fallback when the sheet has no `hit_dice` of its own. */
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

export const hitDieSidesFor = (charClass: string): number =>
  HIT_DICE[(charClass || '').toLowerCase().trim()] ?? 8;

export const isCaster = (charClass: string): boolean =>
  CASTER_CLASSES.has((charClass || '').toLowerCase().trim());

// --------------------------------------------------------------------------- //
// The tables                                                                    //
// --------------------------------------------------------------------------- //

export const CLASS_COMBAT_FEATURES: Record<string, FeatureBlueprint[]> = {
  rogue: [
    {
      id: 'sneak-attack',
      name: 'Sneak Attack',
      icon: '🗡️',
      kind: 'rider',
      hint: 'Once per turn, with Advantage or an ally within 5 ft of the target. Finesse or ranged weapon only.',
      steps: [{ level: 1, notation: (ctx) => dice(Math.ceil(ctx.level / 2), 6) }],
    },
    {
      id: 'cunning-strike',
      name: 'Cunning Strike',
      icon: '🎯',
      kind: 'utility',
      edition: '2024',
      rollable: false,
      hint: 'Forgo Sneak Attack dice to add Poison, Trip or Withdraw. Two effects from 11th.',
      steps: [{ level: 5, notation: '−1d6 per effect' }],
    },
  ],

  monk: [
    {
      id: 'martial-arts-2014',
      name: 'Martial Arts Die',
      icon: '👊',
      kind: 'attack',
      edition: '2014',
      hint: 'Unarmed strikes and Monk weapons. Use DEX in place of STR.',
      steps: [
        { level: 1, notation: (ctx) => `1d4${signed(martialArtsMod(ctx))}` },
        { level: 5, notation: (ctx) => `1d6${signed(martialArtsMod(ctx))}` },
        { level: 11, notation: (ctx) => `1d8${signed(martialArtsMod(ctx))}` },
        { level: 17, notation: (ctx) => `1d10${signed(martialArtsMod(ctx))}` },
      ],
    },
    {
      id: 'martial-arts-2024',
      name: 'Martial Arts Die',
      icon: '👊',
      kind: 'attack',
      edition: '2024',
      hint: 'Unarmed strikes and Monk weapons. One extra unarmed strike as a Bonus Action.',
      steps: [
        { level: 1, notation: (ctx) => `1d6${signed(martialArtsMod(ctx))}` },
        { level: 5, notation: (ctx) => `1d8${signed(martialArtsMod(ctx))}` },
        { level: 11, notation: (ctx) => `1d10${signed(martialArtsMod(ctx))}` },
        { level: 17, notation: (ctx) => `1d12${signed(martialArtsMod(ctx))}` },
      ],
    },
    {
      id: 'deflect',
      name: (ctx) => (ctx.is2024 ? 'Deflect Attacks' : 'Deflect Missiles'),
      icon: '🌀',
      kind: 'defense',
      hint: 'Reaction. Reduces the damage taken by this much.',
      steps: [{ level: 3, notation: (ctx) => `1d10${signed(ctx.mods.DEX + ctx.level)}` }],
    },
  ],

  barbarian: [
    {
      id: 'rage-damage',
      name: 'Rage Damage',
      icon: '💢',
      kind: 'rider',
      hint: 'While Raging, on Strength-based melee attacks.',
      steps: [
        { level: 1, notation: '+2' },
        { level: 9, notation: '+3' },
        { level: 16, notation: '+4' },
      ],
    },
    {
      id: 'brutal-strike',
      name: 'Brutal Strike',
      icon: '🪓',
      kind: 'rider',
      edition: '2024',
      hint: 'On a Reckless Attack, forgo Advantage to add this and one debuff effect.',
      steps: [
        { level: 9, notation: '1d10' },
        { level: 13, notation: '2d10' },
        { level: 17, notation: '3d10' },
      ],
    },
    {
      id: 'brutal-critical',
      name: 'Brutal Critical',
      icon: '💥',
      kind: 'utility',
      edition: '2014',
      rollable: false,
      hint: 'Extra weapon damage dice on a melee crit — already folded into the Crit button.',
      steps: [
        { level: 9, notation: '+1 weapon die' },
        { level: 13, notation: '+2 weapon dice' },
        { level: 17, notation: '+3 weapon dice' },
      ],
    },
  ],

  paladin: [
    {
      id: 'divine-smite',
      name: 'Divine Smite',
      icon: '⚡',
      kind: 'rider',
      damageType: 'radiant',
      hint: '2d8 for a 1st-level slot, +1d8 per level above that, max 5d8. +1d8 against Undead and Fiends.',
      steps: [{ level: 2, notation: '2d8' }],
      options: (ctx) =>
        Array.from({ length: halfCasterMaxSlot(ctx.level) }, (_, index) => {
          const slot = index + 1;
          return {
            label: `${ORDINALS[slot]} slot`,
            notation: dice(Math.min(2 + index, 5), 8),
          };
        }),
    },
    {
      id: 'improved-divine-smite',
      name: (ctx) => (ctx.is2024 ? 'Radiant Strikes' : 'Improved Divine Smite'),
      icon: '✨',
      kind: 'rider',
      damageType: 'radiant',
      hint: 'Every melee weapon hit carries this, on top of any Divine Smite.',
      steps: [{ level: 11, notation: '1d8' }],
    },
    {
      id: 'lay-on-hands',
      name: 'Lay on Hands',
      icon: '🙌',
      kind: 'utility',
      rollable: false,
      hint: 'Healing pool, refreshed on a Long Rest. 5 points cures one disease or poison.',
      steps: [{ level: 1, notation: (ctx) => `${ctx.level * 5} HP` }],
    },
  ],

  fighter: [
    {
      id: 'second-wind',
      name: 'Second Wind',
      icon: '💚',
      kind: 'heal',
      hint: 'Bonus Action. Regain hit points, then take a rest to get it back.',
      steps: [{ level: 1, notation: (ctx) => `1d10${signed(ctx.level)}` }],
    },
    {
      id: 'superiority-dice',
      name: 'Superiority Die',
      icon: '⚔️',
      kind: 'rider',
      subclass: 'battle master',
      hint: 'Spend one on a maneuver. Pool of 4, rising to 5 at 7th and 6 at 15th.',
      steps: [
        { level: 3, notation: '1d8' },
        { level: 10, notation: '1d10' },
        { level: 18, notation: '1d12' },
      ],
    },
    {
      id: 'improved-critical',
      name: 'Improved Critical',
      icon: '🎲',
      kind: 'utility',
      subclass: 'champion',
      rollable: false,
      hint: 'Widened crit range — the Attack button already flags these as crits.',
      steps: [
        { level: 3, notation: 'crit on 19–20' },
        { level: 15, notation: 'crit on 18–20' },
      ],
    },
  ],

  bard: [
    {
      id: 'bardic-inspiration',
      name: 'Bardic Inspiration',
      icon: '🎵',
      kind: 'utility',
      hint: 'The ally adds this to one ability check, attack roll or saving throw.',
      steps: [
        { level: 1, notation: '1d6' },
        { level: 5, notation: '1d8' },
        { level: 10, notation: '1d10' },
        { level: 15, notation: '1d12' },
      ],
    },
    {
      id: 'song-of-rest',
      name: 'Song of Rest',
      icon: '🪕',
      kind: 'heal',
      edition: '2014',
      hint: 'Each ally who spends Hit Dice on a short rest regains this much extra.',
      steps: [
        { level: 2, notation: '1d6' },
        { level: 9, notation: '1d8' },
        { level: 13, notation: '1d10' },
        { level: 17, notation: '1d12' },
      ],
    },
  ],

  ranger: [
    {
      id: 'hunters-mark',
      name: "Hunter's Mark",
      icon: '🏹',
      kind: 'rider',
      hint: 'Extra damage on every hit against the marked creature.',
      steps: [{ level: 1, notation: '1d6' }],
    },
    {
      id: 'colossus-slayer',
      name: 'Colossus Slayer',
      icon: '🗡️',
      kind: 'rider',
      subclass: 'hunter',
      hint: 'Once per turn, against a creature already below its hit point maximum.',
      steps: [{ level: 3, notation: '1d8' }],
    },
  ],

  warlock: [
    {
      id: 'eldritch-blast',
      name: 'Eldritch Blast',
      icon: '🟣',
      kind: 'attack',
      damageType: 'force',
      hint: (ctx) =>
        `${eldritchBeams(ctx.level)} beam${eldritchBeams(ctx.level) === 1 ? '' : 's'}, each a separate attack roll. Agonizing Blast adds ${signed(ctx.mods.CHA)} to every beam.`,
      steps: [{ level: 1, notation: (ctx) => dice(eldritchBeams(ctx.level), 10) }],
    },
    {
      id: 'hex',
      name: 'Hex',
      icon: '👁️',
      kind: 'rider',
      damageType: 'necrotic',
      hint: 'Extra damage on every hit against the hexed creature.',
      steps: [{ level: 1, notation: '1d6' }],
    },
  ],

  cleric: [
    {
      id: 'divine-strike',
      name: (ctx) => (ctx.is2024 ? 'Blessed Strikes' : 'Divine Strike'),
      icon: '🔆',
      kind: 'rider',
      hint: 'Once per turn on a weapon hit. Damage type follows your domain.',
      steps: [
        { level: 8, notation: '1d8' },
        { level: 14, notation: '2d8' },
      ],
      edition: '2014',
    },
    {
      id: 'blessed-strikes',
      name: 'Blessed Strikes',
      icon: '🔆',
      kind: 'rider',
      damageType: 'radiant',
      hint: 'Divine Strike option — once per turn on a weapon hit. Radiant or Necrotic.',
      steps: [
        { level: 7, notation: '1d8' },
        { level: 14, notation: '2d8' },
      ],
      edition: '2024',
    },
  ],

  druid: [
    {
      id: 'primal-strike',
      name: 'Primal Strike',
      icon: '🌿',
      kind: 'rider',
      edition: '2024',
      hint: 'Elemental Fury option — once per turn. Cold, Fire, Lightning or Thunder.',
      steps: [
        { level: 7, notation: '1d8' },
        { level: 15, notation: '2d8' },
      ],
    },
  ],

  artificer: [
    {
      id: 'arcane-jolt',
      name: 'Arcane Jolt',
      icon: '🔧',
      kind: 'rider',
      damageType: 'force',
      subclass: 'battle smith',
      hint: 'Once per turn, on a magic weapon hit or your Steel Defender. Can heal instead.',
      steps: [
        { level: 9, notation: '2d6' },
        { level: 15, notation: '4d6' },
      ],
    },
  ],
};

/** A Monk may swap DEX in for STR, so the better of the two is what actually gets rolled. */
function martialArtsMod(ctx: CombatContext): number {
  return Math.max(ctx.mods.DEX, ctx.mods.STR);
}

function eldritchBeams(level: number): number {
  return level >= 17 ? 4 : level >= 11 ? 3 : level >= 5 ? 2 : 1;
}

// --------------------------------------------------------------------------- //
// Resolution                                                                    //
// --------------------------------------------------------------------------- //

const resolve = <T>(value: Resolver<T>, ctx: CombatContext): T =>
  typeof value === 'function' ? (value as (ctx: CombatContext) => T)(ctx) : value;

/** The step in effect at this level, or null when the feature has not come online. */
function activeStep(blueprint: FeatureBlueprint, ctx: CombatContext): FeatureStep | null {
  let current: FeatureStep | null = null;
  for (const step of blueprint.steps) {
    if (ctx.level >= step.level && (!current || step.level > current.level)) {
      current = step;
    }
  }
  return current;
}

function applies(blueprint: FeatureBlueprint, ctx: CombatContext): boolean {
  if (blueprint.edition && blueprint.edition !== (ctx.is2024 ? '2024' : '2014')) return false;
  if (blueprint.subclass && !ctx.subclass.toLowerCase().includes(blueprint.subclass)) return false;
  return true;
}

/**
 * A feature is only rollable if its number actually contains a die. Flat riders
 * such as Rage Damage `+2` stack onto a weapon's damage roll (see the Damage
 * Riders toggles) — rolling them on their own would always return the modifier.
 */
const hasDie = (notation: string): boolean => /\d*d\d+/i.test(notation);

export function resolveClassActions(ctx: CombatContext): ClassCombatAction[] {
  const blueprints = CLASS_COMBAT_FEATURES[ctx.charClass.toLowerCase().trim()] ?? [];
  const actions: ClassCombatAction[] = [];

  for (const blueprint of blueprints) {
    if (!applies(blueprint, ctx)) continue;

    const step = activeStep(blueprint, ctx);
    if (!step) continue;

    const notation = resolve(step.notation, ctx);
    const options = blueprint.options?.(ctx);

    actions.push({
      id: blueprint.id,
      name: resolve(blueprint.name, ctx),
      icon: blueprint.icon,
      kind: blueprint.kind,
      notation,
      hint: resolve(blueprint.hint, ctx),
      source: `${titleCase(ctx.charClass)} ${step.level}`,
      damageType: blueprint.damageType,
      rollable:
        blueprint.rollable ??
        (hasDie(notation) || (options?.some((option) => hasDie(option.notation)) ?? false)),
      options,
    });
  }

  return actions;
}

/** Brutal Critical, expressed as the number of extra weapon dice a crit adds. */
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
