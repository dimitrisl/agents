const fs = require('fs');
let code = fs.readFileSync('client/src/app/core/rules/skills.ts', 'utf8');

const replacement = `export function skillModifier(
  char: CharacterSchema | null | undefined,
  skill: SkillDefinition
): number {
  if (!char?.stats) return 0;

  // Prefer backend-computed values
  if (char.skills && char.skills[skill.name] !== undefined) {
    return char.skills[skill.name];
  }

  const profBonus = proficiencyBonus(char);
  let bonus = 0;

  if (hasExpertiseIn(char, skill.name)) {
    bonus = profBonus * 2;
  } else if (isProficientIn(char, skill.name)) {
    bonus = profBonus;
  }

  return abilityModifier(abilityScore(char, skill.ability)) + bonus;
}`;

code = code.replace(
  /export function skillModifier\([\s\S]*?return abilityModifier\(abilityScore\(char, skill\.ability\)\) \+ bonus;\n\}/m,
  replacement
);

fs.writeFileSync('client/src/app/core/rules/skills.ts', code);
