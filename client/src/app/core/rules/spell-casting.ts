/**
 * What casting a spell actually rolls, read from the rules text.
 *
 * The spell database stores prose ("Each creature … takes 8d6 fire damage on a
 * failed save, or half as much damage on a successful one"), not structured
 * damage, so this extracts the parts a cast needs: dice, damage type, healing,
 * save ability (and whether a save halves it), spell attack, and how the dice
 * grow when upcast. Anything it can't read safely is left out rather than
 * guessed — the cast still spends its slot and just shows no roll.
 */

import { CharacterSchema } from '../models/character.model';
import { abilityModifierOf, is2024Edition } from './ability';

export type SaveAbility = 'STR' | 'DEX' | 'CON' | 'INT' | 'WIS' | 'CHA';

export interface SpellRulesText {
  name: string;
  level: string | number;
  description?: string;
  higherLevelSlot?: string | null;
  duration?: string;
  /** 2014 data stores "True"/"False", 2024 data stores booleans. */
  concentration?: boolean | string | null;
  ritual?: boolean | string | null;
}

export interface SpellCastProfile {
  baseLevel: number;
  /** Dice of one instance at the spell's own level, e.g. "8d6". */
  dice: string | null;
  /** Flat bonus per instance: Magic Missile's darts deal 1d4 + 1. */
  flatBonus: number;
  /** How many instances hit at once: Magic Missile's three darts. */
  instances: number;
  /** Extra instances per slot level above the base ("one more dart"). */
  instancesPerSlotLevel: number;
  /** Extra dice per slot level above the base, e.g. "1d6". */
  perSlotLevel: string | null;
  /** "fire", "radiant"… for damage; null for healing or "type you chose". */
  damageType: string | null;
  healing: boolean;
  /** Healing that adds the caster's spellcasting modifier (Cure Wounds). */
  addsAbilityModifier: boolean;
  spellAttack: boolean;
  save: { ability: SaveAbility; halfOnSuccess: boolean } | null;
  /**
   * The dice land when the spell is cast. False for effects that deal damage
   * later (Fire Shield's retaliation), which must not be rolled on casting.
   */
  rollsOnCast: boolean;
  /** Casting it starts concentration (and ends any other: only one at a time). */
  concentration: boolean;
  /** Spell has the ritual tag and can be cast in +10 minutes without spending a slot when eligible. */
  ritual: boolean;
}

const ABILITIES: Record<string, SaveAbility> = {
  strength: 'STR',
  dexterity: 'DEX',
  constitution: 'CON',
  intelligence: 'INT',
  wisdom: 'WIS',
  charisma: 'CHA',
};

const WORD_NUMBERS: Record<string, number> = { one: 1, two: 2, three: 3, four: 4, five: 5 };

/** The imported texts contain OCR slips: "ld8" for 1d8, "lO-foot". */
function cleanText(text: string | null | undefined): string {
  return (text || '')
    .replace(/\bl(d\d+)\b/gi, '1$1')
    .replace(/\b(\d+)l\b/g, '$11')
    .toLowerCase();
}

export function analyzeSpell(spell: SpellRulesText): SpellCastProfile {
  const text = cleanText(spell.description);
  const higher = cleanText(spell.higherLevelSlot === 'None' ? '' : spell.higherLevelSlot);
  const baseLevel = Number(spell.level) || 0;

  const diceMatch = /\b(\d+d\d+)\b(?:\s*\+\s*(\d+))?\s*([a-z]+)?\s*(damage)?/.exec(text);
  const healing =
    /regains?\b[^.]*\b\d+d\d+|\b\d+d\d+\b[^.]*hit points/.test(text) && !/damage/.test(text.slice(0, 200));
  const typeWord = diceMatch?.[3];
  const damageType = diceMatch && !healing && diceMatch[4] && typeWord && typeWord !== 'damage' ? typeWord : null;

  const perSlot = /increases? by (\d+d\d+)/.exec(higher);
  const save = /(?:make|succeed on) an? (strength|dexterity|constitution|intelligence|wisdom|charisma) saving throw/.exec(
    text
  );
  const darts = /creates? (\w+) glowing darts/.exec(text);
  const spellAttack = /spell attack/.test(text);
  const instantaneous = /instantaneous/i.test(spell.duration || '');

  return {
    baseLevel,
    dice: diceMatch ? diceMatch[1] : null,
    flatBonus: diceMatch?.[2] ? Number(diceMatch[2]) : 0,
    instances: darts ? WORD_NUMBERS[darts[1]] ?? (Number(darts[1]) || 1) : 1,
    instancesPerSlotLevel: darts && /one more dart/.test(higher) ? 1 : 0,
    perSlotLevel: perSlot ? perSlot[1] : null,
    damageType,
    healing,
    addsAbilityModifier: healing && /spellcasting ability modifier/.test(text),
    spellAttack,
    save: save ? { ability: ABILITIES[save[1]], halfOnSuccess: /half as much damage/.test(text) } : null,
    rollsOnCast: spellAttack || !!save || healing || instantaneous,
    concentration:
      String(spell.concentration).toLowerCase() === 'true' || /concentration/i.test(spell.duration || ''),
    ritual: spell.ritual === true || String(spell.ritual).toLowerCase() === 'true',
  };
}

/** Damage cantrips gain a die at character levels 5, 11 and 17. */
export function cantripDiceMultiplier(characterLevel: number): number {
  return characterLevel >= 17 ? 4 : characterLevel >= 11 ? 3 : characterLevel >= 5 ? 2 : 1;
}

/**
 * The dice for this cast, as notation: cantrips scale with character level,
 * leveled spells add `perSlotLevel` (or another instance) for every slot level
 * above their own. Fireball at 4th → "9d6"; Magic Missile at 2nd → "4d4+4".
 */
export function diceForCast(profile: SpellCastProfile, slotLevel: number, characterLevel: number): string | null {
  if (!profile.dice) return null;
  const [count, sides] = profile.dice.split('d').map(Number);
  const extraLevels = profile.baseLevel === 0 ? 0 : Math.max(0, slotLevel - profile.baseLevel);

  const instances = profile.instances + profile.instancesPerSlotLevel * extraLevels;
  let diceCount = count * instances;
  if (profile.baseLevel === 0) diceCount *= cantripDiceMultiplier(characterLevel);

  let extra = '';
  if (extraLevels && profile.perSlotLevel) {
    const [perCount, perSides] = profile.perSlotLevel.split('d').map(Number);
    if (perSides === sides) diceCount += perCount * extraLevels;
    else extra = ` + ${perCount * extraLevels}d${perSides}`;
  }

  const flat = profile.flatBonus * instances;
  return `${diceCount}d${sides}${flat ? `+${flat}` : ''}${extra}`;
}

export const RITUAL_SPELLS_2014 = new Set([
  'alarm',
  'animal messenger',
  'augury',
  'beast sense',
  'commune',
  'commune with nature',
  'comprehend languages',
  'contact other plane',
  'detect magic',
  'detect poison and disease',
  'divination',
  'feign death',
  'find familiar',
  'floating disk',
  'forbiddance',
  'gentle repose',
  'identify',
  'illusory script',
  'instant summons',
  'locate animals or plants',
  'magic mouth',
  'meld into stone',
  'phantom steed',
  'purify food and drink',
  'silence',
  'skywrite',
  'speak with animals',
  'telepathic bond',
  'tiny hut',
  'unseen servant',
  'water breathing',
  'water walk',
]);

export const RITUAL_SPELLS_2024 = new Set([
  'alarm',
  'animal messenger',
  'augury',
  'beast sense',
  'commune',
  'commune with nature',
  'comprehend languages',
  'contact other plane',
  'detect magic',
  'detect poison and disease',
  'divination',
  'find familiar',
  'floating disk',
  'forbiddance',
  'gentle repose',
  'identify',
  'illusory script',
  'instant summons',
  'locate animals or plants',
  'magic mouth',
  'meld into stone',
  'phantom steed',
  'purify food and drink',
  'silence',
  'speak with animals',
  'telepathic bond',
  'tiny hut',
  'unseen servant',
  'water breathing',
  'water walk',
]);

const PREPARED_2024_TABLES: Record<string, number[]> = {
  wizard: [4, 5, 6, 7, 9, 10, 11, 12, 14, 15, 16, 16, 17, 18, 19, 21, 22, 23, 24, 25],
  cleric: [4, 5, 6, 7, 9, 10, 11, 12, 14, 15, 16, 16, 17, 17, 18, 18, 19, 20, 21, 22],
  druid: [4, 5, 6, 7, 9, 10, 11, 12, 14, 15, 16, 16, 17, 17, 18, 18, 19, 20, 21, 22],
  bard: [4, 5, 6, 7, 9, 10, 11, 12, 14, 15, 16, 16, 17, 17, 18, 18, 19, 20, 21, 22],
  sorcerer: [4, 5, 6, 7, 9, 10, 11, 12, 14, 15, 16, 16, 17, 17, 18, 18, 19, 20, 21, 22],
  warlock: [2, 3, 4, 5, 6, 7, 8, 9, 10, 10, 11, 11, 12, 12, 13, 13, 14, 14, 15, 15],
  paladin: [2, 3, 4, 5, 6, 6, 7, 7, 9, 9, 10, 10, 11, 11, 12, 12, 14, 14, 15, 15],
  ranger: [2, 3, 4, 5, 6, 6, 7, 7, 9, 9, 10, 10, 11, 11, 12, 12, 14, 14, 15, 15],
  eldritch_knight: [0, 0, 3, 4, 4, 4, 5, 6, 6, 7, 8, 8, 9, 10, 10, 11, 11, 11, 12, 13],
  arcane_trickster: [0, 0, 3, 4, 4, 4, 5, 6, 6, 7, 8, 8, 9, 10, 10, 11, 11, 11, 12, 13],
};

export function normalizeSpellKey(name: string | null | undefined): string {
  return String(name || '')
    .trim()
    .toLowerCase()
    .replace(/[\u2018\u2019]/g, "'");
}

export function isAlwaysPreparedSpell(
  char: CharacterSchema | null | undefined,
  spellName: string
): boolean {
  const key = normalizeSpellKey(spellName);
  if (!key || !char?.always_prepared_spells?.length) return false;
  return char.always_prepared_spells.some((s) => normalizeSpellKey(s) === key);
}

export function maxPreparedSpells(char: CharacterSchema | null | undefined): number | null {
  if (!char) return null;
  if (char.max_prepared_spells !== undefined) {
    return char.max_prepared_spells;
  }

  const is2024 = is2024Edition(char);
  const entries =
    char.classes && char.classes.length > 0
      ? char.classes.map((c) => ({
          name: (c.class_name || '').trim().toLowerCase(),
          subclass: (
            c.subclass ||
            ((c.class_name || '').trim().toLowerCase() === (char.char_class || '').trim().toLowerCase()
              ? char.subclass
              : '') ||
            ''
          )
            .trim()
            .toLowerCase(),
          level: Math.max(1, Math.min(20, Number(c.level || 1))),
        }))
      : char.char_class
        ? [
            {
              name: char.char_class.trim().toLowerCase(),
              subclass: (char.subclass || '').trim().toLowerCase(),
              level: Math.max(1, Math.min(20, Number(char.char_level || 1))),
            },
          ]
        : [];

  const intMod = abilityModifierOf(char, 'INT');
  const wisMod = abilityModifierOf(char, 'WIS');
  const chaMod = abilityModifierOf(char, 'CHA');

  let total = 0;
  let hasPrepared = false;
  for (const cls of entries) {
    if (is2024) {
      if (cls.name in PREPARED_2024_TABLES) {
        total += PREPARED_2024_TABLES[cls.name][cls.level - 1];
        hasPrepared = true;
      } else if (cls.name === 'artificer') {
        total += Math.max(1, Math.floor(cls.level / 2) + intMod);
        hasPrepared = true;
      } else if (cls.name === 'fighter' && cls.subclass.includes('eldritch knight') && cls.level >= 3) {
        total += PREPARED_2024_TABLES['eldritch_knight'][cls.level - 1];
        hasPrepared = true;
      } else if (cls.name === 'rogue' && cls.subclass.includes('arcane trickster') && cls.level >= 3) {
        total += PREPARED_2024_TABLES['arcane_trickster'][cls.level - 1];
        hasPrepared = true;
      }
    } else {
      if (cls.name === 'cleric' || cls.name === 'druid') {
        total += Math.max(1, cls.level + wisMod);
        hasPrepared = true;
      } else if (cls.name === 'wizard') {
        total += Math.max(1, cls.level + intMod);
        hasPrepared = true;
      } else if (cls.name === 'paladin' && cls.level >= 2) {
        total += Math.max(1, Math.floor(cls.level / 2) + chaMod);
        hasPrepared = true;
      } else if (cls.name === 'artificer') {
        total += Math.max(1, Math.floor(cls.level / 2) + intMod);
        hasPrepared = true;
      }
    }
  }

  return hasPrepared ? total : null;
}

/** Counts daily prepared leveled spells excluding cantrips and locked always-prepared spells. */
export function preparedSpellsCount(char: CharacterSchema | null | undefined): number {
  if (!char?.prepared_spells?.length) return 0;
  const cantrips = new Set((char.spells?.cantrips || []).map((s) => normalizeSpellKey(s)));
  const always = new Set((char.always_prepared_spells || []).map((s) => normalizeSpellKey(s)));
  const unique = new Set<string>();
  for (const s of char.prepared_spells) {
    const key = normalizeSpellKey(s);
    if (!key || cantrips.has(key) || always.has(key)) continue;
    unique.add(key);
  }
  return unique.size;
}

export function isRitualSpell(
  spellName: string,
  edition?: string | null,
  profile?: SpellCastProfile | null
): boolean {
  if (profile) return !!profile.ritual;
  const key = normalizeSpellKey(spellName);
  if (!key) return false;
  return String(edition || '').includes('2024')
    ? RITUAL_SPELLS_2024.has(key)
    : RITUAL_SPELLS_2014.has(key);
}

/**
 * Checks D&D 5e (2014) vs 2024 Revision eligibility to cast `spellName` as a Ritual:
 * - Always requires the spell to carry the Ritual tag (and not be a cantrip).
 * - 2024 PHB: any character with the spell prepared/always-prepared can cast it as a ritual;
 *   Wizard (*Ritual Adept*), *Ritual Caster*, or *Book of Ancient Secrets* can also cast directly from the spellbook.
 * - 2014 PHB: Wizard casts from spellbook even if unprepared; Bard casts from known spells;
 *   Cleric / Druid / Artificer must have it prepared; *Ritual Caster* / *Book of Ancient Secrets* grants ritual casting for known/scribed rituals.
 */
export function canCastAsRitual(
  char: CharacterSchema | null | undefined,
  spellName: string,
  profile?: SpellCastProfile | null
): boolean {
  if (!char || !isRitualSpell(spellName, char.dnd_edition, profile)) return false;
  const key = normalizeSpellKey(spellName);
  if (!key) return false;

  const spells = char.spells;
  const isCantrip = (spells?.cantrips || []).some((s) => normalizeSpellKey(s) === key);
  if (isCantrip) return false;

  const isAlways = isAlwaysPreparedSpell(char, spellName);
  const isPrepared =
    isAlways || (char.prepared_spells || []).some((s) => normalizeSpellKey(s) === key);
  let hasInLeveledSpells = false;
  if (spells) {
    for (const lvlKey of [
      'level_1',
      'level_2',
      'level_3',
      'level_4',
      'level_5',
      'level_6',
      'level_7',
      'level_8',
      'level_9',
    ] as const) {
      if ((spells[lvlKey] || []).some((s) => normalizeSpellKey(s) === key)) {
        hasInLeveledSpells = true;
        break;
      }
    }
  }
  const knowsOrHasSpell = isPrepared || hasInLeveledSpells;
  if (!knowsOrHasSpell) return false;

  const classNames = new Set<string>();
  for (const c of char.classes || []) {
    const cname = (c.class_name || '').trim().toLowerCase();
    if (cname) classNames.add(cname);
  }
  if (char.char_class) classNames.add(char.char_class.trim().toLowerCase());

  const featureNames = (char.features_traits || []).map((f) =>
    (typeof f === 'string' ? f : f?.name || '').toLowerCase()
  );
  const hasBookOrFeat = featureNames.some(
    (fn) =>
      fn.includes('ritual caster') ||
      fn.includes('book of ancient secrets') ||
      fn.includes('ritual adept') ||
      fn.includes('ritual casting')
  );

  if (is2024Edition(char)) {
    if (isPrepared) return true;
    return (classNames.has('wizard') || hasBookOrFeat) && hasInLeveledSpells;
  }

  // 2014 Edition
  if (classNames.has('wizard') || hasBookOrFeat) return knowsOrHasSpell;
  if (classNames.has('bard') && hasInLeveledSpells) return true;
  if (classNames.has('cleric') || classNames.has('druid') || classNames.has('artificer')) {
    return isPrepared;
  }
  return false;
}
