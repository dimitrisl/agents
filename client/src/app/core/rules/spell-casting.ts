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

export type SaveAbility = 'STR' | 'DEX' | 'CON' | 'INT' | 'WIS' | 'CHA';

export interface SpellRulesText {
  name: string;
  level: string | number;
  description?: string;
  higherLevelSlot?: string | null;
  duration?: string;
  /** 2014 data stores "True"/"False", 2024 data stores booleans. */
  concentration?: boolean | string | null;
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
