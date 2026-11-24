import { CharacterSchema, FeatureTrait, MulticlassOption } from '../models/character.model';
import { hitDieSidesFor } from '../data/class-combat.data';
import { is2024Edition, proficiencyBonusForLevel } from './ability';

/** The slice of the server's level-up analysis that the sheet writes back. */
export interface LevelUpAnalysis {
  new_total_hp: number;
  new_features?: FeatureTrait[];
}

export interface LevelUpResult {
  char_level: number;
  /** Derived from the new level, not carried over from the old sheet. */
  proficiency_bonus: number;
  hp_max: number;
  /** Levelling up heals to full — what the sheet has always done. */
  hp_current: number;
  /**
   * Left `undefined` when the analysis brought no features, so the caller knows
   * to leave the existing list untouched rather than overwrite it with `[]`.
   */
  features_traits?: FeatureTrait[];
}

export const ALL_DND_CLASSES: readonly string[] = [
  'Artificer',
  'Barbarian',
  'Bard',
  'Cleric',
  'Druid',
  'Fighter',
  'Monk',
  'Paladin',
  'Ranger',
  'Rogue',
  'Sorcerer',
  'Warlock',
  'Wizard',
];

const MULTICLASS_PREREQS: Record<
  string,
  { summary: string; mode: 'all' | 'any'; stats: ('STR' | 'DEX' | 'CON' | 'INT' | 'WIS' | 'CHA')[] }
> = {
  artificer: { summary: 'INT 13', mode: 'all', stats: ['INT'] },
  barbarian: { summary: 'STR 13', mode: 'all', stats: ['STR'] },
  bard: { summary: 'CHA 13', mode: 'all', stats: ['CHA'] },
  cleric: { summary: 'WIS 13', mode: 'all', stats: ['WIS'] },
  druid: { summary: 'WIS 13', mode: 'all', stats: ['WIS'] },
  fighter: { summary: 'STR 13 or DEX 13', mode: 'any', stats: ['STR', 'DEX'] },
  monk: { summary: 'DEX 13 & WIS 13', mode: 'all', stats: ['DEX', 'WIS'] },
  paladin: { summary: 'STR 13 & CHA 13', mode: 'all', stats: ['STR', 'CHA'] },
  ranger: { summary: 'DEX 13 & WIS 13', mode: 'all', stats: ['DEX', 'WIS'] },
  rogue: { summary: 'DEX 13', mode: 'all', stats: ['DEX'] },
  sorcerer: { summary: 'CHA 13', mode: 'all', stats: ['CHA'] },
  warlock: { summary: 'CHA 13', mode: 'all', stats: ['CHA'] },
  wizard: { summary: 'INT 13', mode: 'all', stats: ['INT'] },
};

const MC_ARMOR_2014: Record<string, string[]> = {
  artificer: ['Light Armor', 'Medium Armor', 'Shields'],
  barbarian: ['Shields'],
  bard: ['Light Armor'],
  cleric: ['Light Armor', 'Medium Armor', 'Shields'],
  druid: ['Light Armor', 'Medium Armor', 'Shields'],
  fighter: ['Light Armor', 'Medium Armor', 'Shields'],
  monk: [],
  paladin: ['Light Armor', 'Medium Armor', 'Shields'],
  ranger: ['Light Armor', 'Medium Armor', 'Shields'],
  rogue: ['Light Armor'],
  sorcerer: [],
  warlock: ['Light Armor'],
  wizard: [],
};

const MC_ARMOR_2024: Record<string, string[]> = {
  ...MC_ARMOR_2014,
  druid: ['Light Armor', 'Shields'],
};

const MC_WEAPONS_2014: Record<string, string[]> = {
  artificer: [],
  barbarian: ['Simple Weapons', 'Martial Weapons'],
  bard: [],
  cleric: [],
  druid: [],
  fighter: ['Simple Weapons', 'Martial Weapons'],
  monk: ['Simple Weapons', 'Shortswords'],
  paladin: ['Simple Weapons', 'Martial Weapons'],
  ranger: ['Simple Weapons', 'Martial Weapons'],
  rogue: [],
  sorcerer: [],
  warlock: ['Simple Weapons'],
  wizard: [],
};

const MC_WEAPONS_2024: Record<string, string[]> = {
  ...MC_WEAPONS_2014,
  monk: [],
  warlock: [],
};

const MC_TOOLS: Record<string, string[]> = {
  artificer: ["Thieves' Tools", "Tinker's Tools"],
  bard: ['One Musical Instrument'],
  rogue: ["Thieves' Tools"],
};

const MC_SKILL_GRANTS: Record<string, string> = {
  bard: '1 Skill (Any)',
  ranger: '1 Ranger Skill',
  rogue: '1 Rogue Skill',
};

function checkSingleClassPrereq(
  className: string,
  stats: Record<string, number>,
  prefix = ''
): string[] {
  const low = className.trim().toLowerCase();
  const rule = MULTICLASS_PREREQS[low];
  if (!rule) return [];
  const label = prefix ? `${prefix}${className}` : className;
  if (rule.mode === 'any') {
    if (rule.stats.some((k) => Number(stats[k] ?? 10) >= 13)) return [];
    const have = rule.stats.map((k) => `${k} ${Number(stats[k] ?? 10)}`).join(', ');
    return [`${label} requires ${rule.summary} (have ${have})`];
  }
  const missing = rule.stats.filter((k) => Number(stats[k] ?? 10) < 13);
  if (!missing.length) return [];
  const req = missing.map((k) => `${k} 13`).join(' & ');
  const have = missing.map((k) => `${k} ${Number(stats[k] ?? 10)}`).join(', ');
  return [`${label} requires ${req} (have ${have})`];
}

export function getMulticlassGrantedProficiencies(className: string, is2024: boolean): string[] {
  const low = (className || '').trim().toLowerCase();
  const armor = (is2024 ? MC_ARMOR_2024 : MC_ARMOR_2014)[low] || [];
  const weapons = (is2024 ? MC_WEAPONS_2024 : MC_WEAPONS_2014)[low] || [];
  const tools = MC_TOOLS[low] || [];
  const skill = MC_SKILL_GRANTS[low] ? [MC_SKILL_GRANTS[low]] : [];
  return [...armor, ...weapons, ...tools, ...skill];
}

export function getMulticlassEligibility(char: CharacterSchema | null | undefined): MulticlassOption[] {
  const stats = (
    char?.base_stats && Object.keys(char.base_stats).length > 0
      ? char.base_stats
      : char?.stats || {}
  ) as Record<string, number>;
  const is2024 = is2024Edition(char);
  const existingLevels = new Map<string, number>();

  const entries =
    char?.classes && char.classes.length > 0
      ? char.classes
      : char?.char_class
        ? [{ class_name: char.char_class, level: char.char_level || 1 }]
        : [];

  for (const entry of entries) {
    const cname = (entry.class_name || '').trim();
    if (!cname) continue;
    const low = cname.toLowerCase();
    existingLevels.set(low, (existingLevels.get(low) || 0) + Math.max(1, Number(entry.level || 1)));
  }

  const existingMissing: string[] = [];
  for (const [low] of existingLevels) {
    const canon = ALL_DND_CLASSES.find((c) => c.toLowerCase() === low) || low;
    existingMissing.push(...checkSingleClassPrereq(canon, stats, 'Current class '));
  }

  return ALL_DND_CLASSES.map((className) => {
    const low = className.toLowerCase();
    const curLvl = existingLevels.get(low) || 0;
    const summary = MULTICLASS_PREREQS[low]?.summary || '';
    const hitDie = hitDieSidesFor(className);
    if (curLvl > 0) {
      return {
        class_name: className,
        is_existing: true,
        current_level: curLvl,
        target_level: curLvl + 1,
        hit_die: hitDie,
        eligible: true,
        prerequisite_summary: summary,
        missing_prerequisites: [],
        granted_proficiencies: [],
      };
    }
    const missing = [...existingMissing, ...checkSingleClassPrereq(className, stats)];
    return {
      class_name: className,
      is_existing: false,
      current_level: 0,
      target_level: 1,
      hit_die: hitDie,
      eligible: missing.length === 0,
      prerequisite_summary: summary,
      missing_prerequisites: missing,
      granted_proficiencies: getMulticlassGrantedProficiencies(className, is2024),
    };
  });
}

/** What a level-up writes onto the sheet. */
export function levelUp(char: CharacterSchema, analysis: LevelUpAnalysis): LevelUpResult {
  const char_level = (char.char_level || 1) + 1;
  const result: LevelUpResult = {
    char_level,
    proficiency_bonus: proficiencyBonusForLevel(char_level),
    hp_max: analysis.new_total_hp,
    hp_current: analysis.new_total_hp,
  };

  if (analysis.new_features) {
    result.features_traits = [...(char.features_traits ?? []), ...analysis.new_features];
  }

  return result;
}
