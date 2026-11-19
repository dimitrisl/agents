import { CharacterSchema } from '../models/character.model';

/**
 * The numbers every roll on the sheet starts from.
 *
 * Nothing in this folder may import from `@angular/*`: these are the rules, not
 * the screen that shows them, and they have to be testable without a TestBed.
 */

/**
 * D&D's one universal formula. It had four separate copies inside
 * `player.component`, plus one in `character-state.service` and one in
 * `class-combat.service` — six chances for the same arithmetic to drift.
 *
 * It deliberately takes a bare score and nothing else. Every call site has its
 * own idea of what a *missing* score means, and baking one of them in here would
 * quietly change the others.
 */
export function abilityModifier(score: number): number {
  return Math.floor((score - 10) / 2);
}

/** `+3`, `-1`, `+0` — a modifier on a sheet is never shown as a bare number. */
export function formatModifier(value: number): string {
  return value >= 0 ? `+${value}` : `${value}`;
}

/** The score written on the sheet, or the 10 an unfilled line is assumed to be. */
export function abilityScore(char: CharacterSchema | null | undefined, ability: string): number {
  return char?.stats?.[ability] || 10;
}

export function abilityModifierOf(
  char: CharacterSchema | null | undefined,
  ability: string
): number {
  return abilityModifier(abilityScore(char, ability));
}

/** Proficiency is +2 at level 1, and +2 again for any sheet that forgot to say. */
export function proficiencyBonus(char: CharacterSchema | null | undefined): number {
  return char?.proficiency_bonus || 2;
}

/**
 * The proficiency bonus a character of this level is entitled to: +2 from level
 * 1, then +1 every four levels — +3 at 5, +4 at 9, +5 at 13, +6 at 17.
 *
 * The sheet stores the bonus rather than deriving it, so this is what a level-up
 * has to write back. It never did, which left every hero who crossed level 5
 * rolling a stale +2 on every proficient skill, save and attack.
 */
export function proficiencyBonusForLevel(level: number): number {
  return Math.floor((Math.max(1, level) - 1) / 4) + 2;
}

export function is2024Edition(char: CharacterSchema | null | undefined): boolean {
  return (
    String(char?.dnd_edition || '').includes('2024') ||
    String(char?.ruleset_version || '').includes('2024')
  );
}

/** Effective exhaustion level (0 when DM Bypass is enabled). */
export function effectiveExhaustionLevel(
  char: Pick<CharacterSchema, 'exhaustion_level' | 'exhaustion_bypass'> | null | undefined
): number {
  if (!char || char.exhaustion_bypass) return 0;
  return Math.max(0, Math.min(6, Math.floor(Number(char.exhaustion_level) || 0)));
}

/** True when a hero is killed by Exhaustion Level 6 (and NOT waived by DM Bypass). */
export function isDeceasedByExhaustion(
  char: Pick<CharacterSchema, 'exhaustion_level' | 'exhaustion_bypass'> | null | undefined
): boolean {
  return effectiveExhaustionLevel(char) >= 6;
}

/** 2024 PHB Exhaustion gives -2 per level to all D20 Tests (checks, saves, attacks) unless bypassed. */
export function exhaustionD20Penalty(char: CharacterSchema | null | undefined): number {
  if (!char || !is2024Edition(char)) return 0;
  return effectiveExhaustionLevel(char) * 2;
}

export type ExhaustionRollKind = 'check' | 'save' | 'attack' | 'initiative';

/** True under 2014 PHB rules when Exhaustion forces Disadvantage on this roll kind. */
export function hasExhaustionDisadvantage(
  char: CharacterSchema | null | undefined,
  kind: ExhaustionRollKind
): boolean {
  if (!char || is2024Edition(char)) return false;
  const eff = effectiveExhaustionLevel(char);
  if (eff <= 0) return false;
  if (kind === 'save' || kind === 'attack') {
    return eff >= 3;
  }
  // 2014 L1 Exhaustion imposes Disadvantage on Ability Checks (including Skills & Initiative).
  return eff >= 1;
}

export type RollModeResolution = {
  mode: 'normal' | 'advantage' | 'disadvantage';
  cancelled: boolean;
};

/**
 * Resolves final d20 mode per 5e Advantage/Disadvantage cancellation rules:
 * any source of Advantage + any source of Disadvantage cancel to Normal.
 */
export function resolveRollMode(
  requestedMode: 'normal' | 'advantage' | 'disadvantage',
  hasAutoDisadvantage: boolean,
  hasAutoAdvantage = false
): RollModeResolution {
  const hasAdv = requestedMode === 'advantage' || hasAutoAdvantage;
  const hasDis = requestedMode === 'disadvantage' || hasAutoDisadvantage;
  if (hasAdv && hasDis) {
    return { mode: 'normal', cancelled: true };
  }
  if (hasAdv) {
    return { mode: 'advantage', cancelled: false };
  }
  if (hasDis) {
    return { mode: 'disadvantage', cancelled: false };
  }
  return { mode: 'normal', cancelled: false };
}

/** Ability Check modifier including 2024 Exhaustion penalty and DM ability-check modifier. */
export function abilityCheckModifier(
  char: CharacterSchema | null | undefined,
  ability: string
): number {
  if (!char?.stats) return 0;
  const dmCheck = char.dm_modifiers?.ability_checks_bonus ?? 0;
  return abilityModifierOf(char, ability) - exhaustionD20Penalty(char) + dmCheck;
}

export function isSaveProficient(
  char: CharacterSchema | null | undefined,
  ability: string
): boolean {
  return char?.saving_throws?.includes(ability) || false;
}

/** Ability modifier, plus proficiency when trained, minus exhaustion, plus DM saves bonus. */
export function savingThrowModifier(
  char: CharacterSchema | null | undefined,
  ability: string
): number {
  if (!char?.stats) return 0;

  // Prefer backend-computed values
  if (char.saving_throw_values && char.saving_throw_values[ability] !== undefined) {
    return char.saving_throw_values[ability];
  }

  const dmSave = char.dm_modifiers?.saving_throws_bonus ?? 0;
  return (
    abilityModifierOf(char, ability) +
    (isSaveProficient(char, ability) ? proficiencyBonus(char) : 0) -
    exhaustionD20Penalty(char) +
    dmSave
  );
}

/** Human-readable list of active DM custom modifiers (excluding empty note). */
export function describeDmModifiers(
  mods: CharacterSchema['dm_modifiers'] | null | undefined
): string[] {
  if (!mods) return [];
  const entries: [keyof NonNullable<CharacterSchema['dm_modifiers']>, string][] = [
    ['attack_bonus', 'Atk'],
    ['damage_bonus', 'Dmg'],
    ['ac_bonus', 'AC'],
    ['speed_bonus', 'Spd'],
    ['hp_max_bonus', 'Max HP'],
    ['initiative_bonus', 'Init'],
    ['saving_throws_bonus', 'Saves'],
    ['ability_checks_bonus', 'Checks'],
    ['spell_save_dc_bonus', 'Spell DC'],
    ['passive_perception_bonus', 'Passive Perc'],
  ];
  const parts: string[] = [];
  for (const [key, label] of entries) {
    const val = Number(mods[key] ?? 0);
    if (val) {
      const suffix = key === 'speed_bonus' ? 'ft' : '';
      parts.push(`${val > 0 ? '+' + val : val}${suffix} ${label}`);
    }
  }
  return parts;
}

/**
 * Formats a character's class breakdown uniformly for headers and cards.
 * Returns e.g. "Paladin 5 / Sorcerer 3" when multiclassed, or the single-class
 * label in either "long" ("Paladin • Level 5") or "compact" ("Paladin Lv 5") style.
 */
export function formatClassSummary(
  char: Pick<CharacterSchema, 'char_class' | 'char_level' | 'classes'> | null | undefined,
  variant: 'long' | 'compact' = 'long'
): string {
  const classes = char?.classes || [];
  if (classes.length > 1) {
    return classes
      .map((c) => `${c.class_name || 'Class'} ${c.level ?? 1}`)
      .join(' / ');
  }
  const className = classes[0]?.class_name || char?.char_class || 'Adventurer';
  const level = classes[0]?.level ?? char?.char_level ?? 1;
  return variant === 'compact'
    ? `${className} Lv ${level}`
    : `${className} • Level ${level}`;
}

/**
 * Formats subclass label(s), joining multiple multiclass subclasses with " / "
 * and falling back to top-level `char.subclass` for single-class heroes.
 */
export function formatSubclassSummary(
  char: Pick<CharacterSchema, 'subclass' | 'classes'> | null | undefined
): string {
  const fromClasses = (char?.classes || [])
    .map((c) => (c.subclass || '').trim())
    .filter(Boolean);
  if (fromClasses.length > 0) {
    return fromClasses.join(' / ');
  }
  return (char?.subclass || '').trim();
}
