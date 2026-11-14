import { CharacterSchema } from '../models/character.model';
import {
  abilityModifier,
  abilityScore,
  exhaustionD20Penalty,
  formatModifier,
  is2024Edition,
  proficiencyBonus,
} from './ability';

export type SkillAbility = 'STR' | 'DEX' | 'CON' | 'INT' | 'WIS' | 'CHA';

export interface SkillDefinition {
  name: string;
  ability: SkillAbility;
}

/** The eighteen skills the player sheet lists, in the order it lists them. */
export const ALL_SKILLS: readonly SkillDefinition[] = [
  { name: 'Athletics', ability: 'STR' },
  { name: 'Acrobatics', ability: 'DEX' },
  { name: 'Sleight of Hand', ability: 'DEX' },
  { name: 'Stealth', ability: 'DEX' },
  { name: 'Arcana', ability: 'INT' },
  { name: 'History', ability: 'INT' },
  { name: 'Investigation', ability: 'INT' },
  { name: 'Nature', ability: 'INT' },
  { name: 'Religion', ability: 'INT' },
  { name: 'Animal Handling', ability: 'WIS' },
  { name: 'Insight', ability: 'WIS' },
  { name: 'Medicine', ability: 'WIS' },
  { name: 'Perception', ability: 'WIS' },
  { name: 'Survival', ability: 'WIS' },
  { name: 'Deception', ability: 'CHA' },
  { name: 'Intimidation', ability: 'CHA' },
  { name: 'Performance', ability: 'CHA' },
  { name: 'Persuasion', ability: 'CHA' },
];

export function isProficientIn(
  char: CharacterSchema | null | undefined,
  skillName: string
): boolean {
  return char?.skill_proficiencies?.includes(skillName) || false;
}

export function hasExpertiseIn(
  char: CharacterSchema | null | undefined,
  skillName: string
): boolean {
  return char?.skill_expertise?.includes(skillName) || false;
}

export function hasJackOfAllTrades(char: CharacterSchema | null | undefined): boolean {
  if (!char) return false;
  if (char.features_traits?.some((f) => (f.name || '').toLowerCase().includes('jack of all trades'))) {
    return true;
  }
  if (char.classes?.some((c) => (c.class_name || '').toLowerCase() === 'bard' && (c.level || 0) >= 2)) {
    return true;
  }
  if ((char.char_class || '').toLowerCase() === 'bard' && (char.char_level || 1) >= 2) {
    return true;
  }
  return false;
}

export function hasRemarkableAthlete(char: CharacterSchema | null | undefined): boolean {
  if (!char) return false;
  if (char.features_traits?.some((f) => (f.name || '').toLowerCase().includes('remarkable athlete'))) {
    return true;
  }
  const minLevel = is2024Edition(char) ? 3 : 7;
  if (
    char.classes?.some(
      (c) =>
        (c.class_name || '').toLowerCase() === 'fighter' &&
        (c.subclass || '').toLowerCase() === 'champion' &&
        (c.level || 0) >= minLevel
    )
  ) {
    return true;
  }
  if (
    (char.char_class || '').toLowerCase() === 'fighter' &&
    (char.subclass || '').toLowerCase() === 'champion' &&
    (char.char_level || 1) >= minLevel
  ) {
    return true;
  }
  return false;
}

export function hasInitiativeAdvantage(char: CharacterSchema | null | undefined): boolean {
  if (!char) return false;
  if (char.initiative_advantage) return true;
  if (is2024Edition(char) && hasRemarkableAthlete(char)) return true;
  return false;
}

export function hasAthleticsAdvantage(char: CharacterSchema | null | undefined): boolean {
  if (!char) return false;
  if (char.athletics_advantage) return true;
  if (is2024Edition(char) && hasRemarkableAthlete(char)) return true;
  return false;
}

/**
 * Ability modifier, plus the proficiency bonus (or double for expertise) when the hero is trained in it,
 * or half proficiency bonus for Jack of All Trades (all skills) or Remarkable Athlete (physical skills).
 *
 * A sheet with no stat block scores 0 flat: the old code bailed before it ever
 * read the proficiency list, and adding a lone `+3` beside a blank ability would
 * be a worse answer than nothing.
 */
export function skillModifier(
  char: CharacterSchema | null | undefined,
  skill: SkillDefinition
): number {
  if (!char?.stats) return 0;

  const profBonus = proficiencyBonus(char);
  let bonus = 0;

  if (hasExpertiseIn(char, skill.name)) {
    bonus = profBonus * 2;
  } else if (isProficientIn(char, skill.name)) {
    bonus = profBonus;
  } else {
    const halfProfDown = Math.floor(profBonus / 2);
    const halfProfUp = Math.ceil(profBonus / 2);
    const isPhysical = skill.ability === 'STR' || skill.ability === 'DEX' || skill.ability === 'CON';
    // 2014 RAW: Remarkable Athlete adds +ceil(PB/2) to physical checks.
    // 2024 RAW: Remarkable Athlete gives Advantage on Athletics (no flat numerical bonus).
    if (!is2024Edition(char) && hasRemarkableAthlete(char) && isPhysical) {
      bonus = halfProfUp;
    } else if (hasJackOfAllTrades(char)) {
      bonus = halfProfDown;
    }
  }

  return abilityModifier(abilityScore(char, skill.ability)) + bonus - exhaustionD20Penalty(char);
}

export function skillModifierString(
  char: CharacterSchema | null | undefined,
  skill: SkillDefinition
): string {
  return formatModifier(skillModifier(char, skill));
}

/**
 * Finds a skill by the name the DM typed. The match ignores case because a roll
 * request carries whatever was in the DM's text box, not a picked identifier.
 */
export function findSkill(
  skills: readonly SkillDefinition[],
  name: string
): SkillDefinition | undefined {
  return skills.find((skill) => skill.name.toLowerCase() === name.toLowerCase());
}
