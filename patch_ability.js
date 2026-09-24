const fs = require('fs');
let code = fs.readFileSync('client/src/app/core/rules/ability.ts', 'utf8');

const replacement = `export function savingThrowModifier(
  char: CharacterSchema | null | undefined,
  ability: string
): number {
  if (!char?.stats) return 0;

  // Prefer backend-computed values
  if (char.saving_throw_values && char.saving_throw_values[ability] !== undefined) {
    return char.saving_throw_values[ability];
  }

  return (
    abilityModifierOf(char, ability) +
    (isSaveProficient(char, ability) ? proficiencyBonus(char) : 0)
  );
}`;

code = code.replace(
  /export function savingThrowModifier\([\s\S]*?return \([\s\S]*?\);\n\}/m,
  replacement
);

fs.writeFileSync('client/src/app/core/rules/ability.ts', code);
