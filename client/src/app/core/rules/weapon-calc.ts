import { CharacterSchema, Weapon } from '../models/character.model';
import { abilityModifier } from './ability';

export interface WeaponAttackBreakdown {
  statName: string;
  statMod: number;
  proficient: boolean;
  profBonus: number;
  magicBonus: number;
  fightingStyleName?: string;
  fightingStyleBonus: number;
  miscBonus: number;
  total: number;
  formulaText: string;
}

export interface WeaponDamageBreakdown {
  dice: string;
  statName: string;
  statMod: number;
  magicBonus: number;
  fightingStyleName?: string;
  fightingStyleBonus: number;
  miscBonus: number;
  totalBonus: number;
  damageType: string;
  formulaText: string;
  notation: string;
}

export interface WeaponBreakdown {
  attack: WeaponAttackBreakdown;
  damage: WeaponDamageBreakdown;
}

/** Parses magic bonus from explicit field or from weapon name (e.g. "Longbow +1" -> 1). */
export function extractMagicBonus(weapon: Weapon): number {
  if (typeof weapon.magic_bonus === 'number' && weapon.magic_bonus !== 0) {
    return weapon.magic_bonus;
  }
  const match = /\+([1-9])\b/.exec(weapon.name || '');
  return match ? parseInt(match[1], 10) : 0;
}

/** Determines which ability modifier applies (DEX, STR, etc.). */
export function resolveWeaponStat(weapon: Weapon, char?: CharacterSchema | null): string {
  if (weapon.ability_modifier) {
    const explicit = String(weapon.ability_modifier).toUpperCase().trim();
    if (['STR', 'DEX', 'CON', 'INT', 'WIS', 'CHA', 'NONE'].includes(explicit)) {
      return explicit;
    }
  }

  const props = (weapon.properties || '').toLowerCase();
  const range = (weapon.range || '').toLowerCase();
  const name = (weapon.name || '').toLowerCase();

  const isRanged = range.includes('/') || /bow|crossbow|sling|dart|blowgun/.test(name);
  const isFinesse = props.includes('finesse') || /rapier|scimitar|dagger|shortsword|whip/.test(name);

  if (isRanged && !props.includes('thrown')) {
    return 'DEX';
  }

  if (isFinesse && char?.stats) {
    const str = char.stats.STR ?? 10;
    const dex = char.stats.DEX ?? 10;
    return dex >= str ? 'DEX' : 'STR';
  }

  return 'STR';
}

/** Checks for Fighting Style: Archery (+2 to ranged attack rolls). */
export function getArcheryBonus(weapon: Weapon, char?: CharacterSchema | null): number {
  if (!char?.features_traits) return 0;
  const hasArchery = char.features_traits.some((f) => {
    const name = (typeof f === 'string' ? f : f.name || '').toLowerCase();
    const desc = (typeof f === 'string' ? '' : f.description || '').toLowerCase();
    return name.includes('archery') || desc.includes('+2 bonus to attack rolls you make with ranged weapons');
  });

  if (!hasArchery) return 0;

  const range = (weapon.range || '').toLowerCase();
  const name = (weapon.name || '').toLowerCase();
  const props = (weapon.properties || '').toLowerCase();
  const isRanged = range.includes('/') || props.includes('ammunition') || /bow|crossbow|sling|dart|blowgun/.test(name);

  return isRanged ? 2 : 0;
}

/** Checks for Fighting Style: Dueling (+2 to melee damage rolls when wielding 1-handed). */
export function getDuelingBonus(weapon: Weapon, char?: CharacterSchema | null): number {
  if (!char?.features_traits) return 0;
  const hasDueling = char.features_traits.some((f) => {
    const name = (typeof f === 'string' ? f : f.name || '').toLowerCase();
    return name.includes('dueling');
  });

  if (!hasDueling) return 0;

  const props = (weapon.properties || '').toLowerCase();
  const isTwoHanded = props.includes('two-handed');
  const range = (weapon.range || '').toLowerCase();
  const isRanged = range.includes('/') && !props.includes('thrown');

  return !isTwoHanded && !isRanged ? 2 : 0;
}

/** Computes full breakdown for a weapon's to-hit and damage. */
export function calculateWeaponBreakdown(weapon: Weapon, char?: CharacterSchema | null): WeaponBreakdown {
  const stats = char?.stats || { STR: 10, DEX: 10, CON: 10, INT: 10, WIS: 10, CHA: 10 };
  const pb = char?.proficiency_bonus || 2;

  // 1. Ability Mod
  const statName = resolveWeaponStat(weapon, char);
  const statScore = statName === 'NONE' ? 10 : (stats[statName as keyof typeof stats] ?? 10);
  const statMod = statName === 'NONE' ? 0 : abilityModifier(statScore);

  // 2. Proficiency
  const isProficient = weapon.proficient !== false;
  const profBonus = isProficient ? pb : 0;

  // 3. Magic Bonus
  const magicBonus = extractMagicBonus(weapon);

  // 4. Fighting Styles
  const archery = getArcheryBonus(weapon, char);
  const dueling = getDuelingBonus(weapon, char);

  // 5. Misc
  const miscAttack = weapon.misc_attack_bonus ?? 0;
  const miscDamage = weapon.misc_damage_bonus ?? 0;

  // Attack Breakdown
  const totalAttack = statMod + profBonus + magicBonus + archery + miscAttack;
  const attackParts: string[] = [];
  if (statName !== 'NONE') attackParts.push(`${statName} (${statMod >= 0 ? '+' + statMod : statMod})`);
  if (profBonus > 0) attackParts.push(`Prof (+${profBonus})`);
  if (magicBonus > 0) attackParts.push(`Magic (+${magicBonus})`);
  if (archery > 0) attackParts.push(`Archery (+${archery})`);
  if (miscAttack !== 0) attackParts.push(`Misc (${miscAttack > 0 ? '+' + miscAttack : miscAttack})`);

  const attackFormula =
    attackParts.length > 0
      ? `${attackParts.join(' + ')} = ${totalAttack >= 0 ? '+' + totalAttack : totalAttack}`
      : `${totalAttack >= 0 ? '+' + totalAttack : totalAttack}`;

  // Damage Breakdown
  const rawDice = weapon.damage_dice || weapon.damage || '1d4';
  const diceMatch = /(\d+d\d+)/.exec(rawDice);
  const baseDice = diceMatch ? diceMatch[1] : '1d4';

  const typeMatch = /\d\s*([a-zA-Z][a-zA-Z ]*)$/.exec(rawDice);
  const damageType = weapon.damage_type || (typeMatch ? typeMatch[1].trim() : '');

  const totalDamageBonus = statMod + magicBonus + dueling + miscDamage;
  const damageParts: string[] = [baseDice];
  if (statName !== 'NONE' && statMod !== 0) damageParts.push(`${statMod >= 0 ? '+' + statMod : statMod} (${statName})`);
  if (magicBonus > 0) damageParts.push(`+${magicBonus} (Magic)`);
  if (dueling > 0) damageParts.push(`+${dueling} (Dueling)`);
  if (miscDamage !== 0) damageParts.push(`${miscDamage > 0 ? '+' + miscDamage : miscDamage} (Misc)`);

  const bonusString = totalDamageBonus !== 0 ? (totalDamageBonus > 0 ? `+${totalDamageBonus}` : `${totalDamageBonus}`) : '';
  const damageFormula =
    damageParts.length > 1
      ? `${damageParts.join(' ')} = ${baseDice}${bonusString} ${damageType}`.trim()
      : `${baseDice}${bonusString} ${damageType}`.trim();

  const notation = `${baseDice}${bonusString}`;

  return {
    attack: {
      statName,
      statMod,
      proficient: isProficient,
      profBonus,
      magicBonus,
      fightingStyleName: archery > 0 ? 'Archery' : undefined,
      fightingStyleBonus: archery,
      miscBonus: miscAttack,
      total: totalAttack,
      formulaText: attackFormula,
    },
    damage: {
      dice: baseDice,
      statName,
      statMod,
      magicBonus,
      fightingStyleName: dueling > 0 ? 'Dueling' : undefined,
      fightingStyleBonus: dueling,
      miscBonus: miscDamage,
      totalBonus: totalDamageBonus,
      damageType,
      formulaText: damageFormula,
      notation,
    },
  };
}
