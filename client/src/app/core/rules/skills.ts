import { CharacterSchema } from '../models/character.model';
import { abilityModifier, abilityScore, formatModifier, proficiencyBonus } from './ability';

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

/**
 * Ability modifier, plus the proficiency bonus (or double for expertise) when the hero is trained in it.
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
  }

  return abilityModifier(abilityScore(char, skill.ability)) + bonus;
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
