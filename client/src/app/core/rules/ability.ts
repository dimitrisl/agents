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

/** Ability Check modifier including 2024 Exhaustion penalty, Luckstone/Gear check bonuses, and DM modifiers. */
export function abilityCheckModifier(
  char: CharacterSchema | null | undefined,
  ability: string
): number {
  if (!char?.stats) return 0;
  const dmCheck = char.dm_modifiers?.ability_checks_bonus ?? 0;
  return (
    abilityModifierOf(char, ability) +
    equipmentAbilityCheckBonus(char) -
    exhaustionD20Penalty(char) +
    dmCheck
  );
}

const SAVE_FULL_TO_CODE: Record<string, string> = {
  STRENGTH: 'STR',
  DEXTERITY: 'DEX',
  CONSTITUTION: 'CON',
  INTELLIGENCE: 'INT',
  WISDOM: 'WIS',
  CHARISMA: 'CHA',
};

function classLevelFor(char: CharacterSchema | null | undefined, className: string): number {
  if (!char) return 0;
  const target = className.toLowerCase();
  if (char.classes && char.classes.length > 0) {
    const entry = char.classes.find((c) => (c.class_name || '').trim().toLowerCase() === target);
    if (entry) return entry.level || 0;
  }
  return (char.char_class || '').trim().toLowerCase() === target ? char.char_level || 1 : 0;
}

export function isSaveProficient(
  char: CharacterSchema | null | undefined,
  ability: string
): boolean {
  if (!char) return false;
  const code = ability.trim().toUpperCase();
  const normalizedSaves = new Set(
    (char.saving_throws || []).map((s) => {
      const up = String(s || '').trim().toUpperCase();
      return SAVE_FULL_TO_CODE[up] ?? up;
    })
  );
  if (normalizedSaves.has(code)) return true;

  // Monk 14+ Diamond Soul grants proficiency in all saving throws
  const hasDiamondSoul =
    classLevelFor(char, 'monk') >= 14 ||
    (char.features_traits || []).some((f) =>
      (typeof f === 'string' ? f : f.name || '').toLowerCase().includes('diamond soul')
    );
  if (hasDiamondSoul) return true;

  // Rogue 15+ Slippery Mind grants WIS (and CHA in 2024 Revision) saving throw proficiency
  if (code === 'WIS' || (code === 'CHA' && is2024Edition(char))) {
    const hasSlipperyMind =
      classLevelFor(char, 'rogue') >= 15 ||
      (char.features_traits || []).some((f) =>
        (typeof f === 'string' ? f : f.name || '').toLowerCase().includes('slippery mind')
      );
    if (hasSlipperyMind) return true;
  }

  return false;
}

const CATALOG_SAVE_BONUS_ITEMS: Record<string, number> = {
  'cloak of protection': 1,
  'ring of protection': 1,
  'stone of good luck': 1,
  'luckstone': 1,
  'staff of power': 2,
  'robe of stars': 1,
  'scarab of protection': 1,
};

const CATALOG_ABILITY_CHECK_BONUS_ITEMS: Record<string, number> = {
  'stone of good luck': 1,
  'luckstone': 1,
};

function normalizeCatalogItemName(rawName: string | undefined): string {
  return String(rawName || '')
    .toLowerCase()
    .replace(/\([^)]*\)/g, ' ')
    .replace(/\+\s*\d+/g, ' ')
    .replace(/\barmou?r\b/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();
}

/**
 * Default flat saving-throw bonus implied by a catalog item's base name
 * (e.g. `Cloak of Protection`, `Ring of Protection`, `Stone of Good Luck`, `Staff of Power`)
 * when no explicit `SAVES`/`<STAT>_SAVE` modifier is configured on the item.
 */
export function catalogDefaultSaveBonus(itemName: string | undefined): number {
  return CATALOG_SAVE_BONUS_ITEMS[normalizeCatalogItemName(itemName)] ?? 0;
}

/**
 * Default flat ability-check / skill / initiative bonus implied by a catalog item's base name
 * (e.g. `Stone of Good Luck (Luckstone)` -> `+1`) when no explicit `CHECKS` modifier is configured.
 */
export function catalogDefaultAbilityCheckBonus(itemName: string | undefined): number {
  return CATALOG_ABILITY_CHECK_BONUS_ITEMS[normalizeCatalogItemName(itemName)] ?? 0;
}

function maxAttunementSlots(char: CharacterSchema | null | undefined): number {
  let slots = 3;
  for (const f of char?.features_traits || []) {
    const name = (typeof f === 'string' ? f : f?.name || '').toLowerCase();
    if (name.includes('magic item master')) slots = Math.max(slots, 6);
    else if (name.includes('magic item savant')) slots = Math.max(slots, 5);
    else if (name.includes('magic item adept')) slots = Math.max(slots, 4);
  }
  return slots;
}

/**
 * Ability check bonus (skills, ability checks, initiative, passives) contributed by equipped
 * (and attuned within slot cap) equipment, mirroring backend `stats_service.py`:
 * explicit `mod1`/`mod2` (`CHECKS`, `CHECK`, `ABILITY_CHECKS`, `SKILLS`) takes precedence over catalog defaults.
 */
export function equipmentAbilityCheckBonus(
  char: CharacterSchema | null | undefined
): number {
  if (!char || char.magic_items_suppressed) return 0;
  const maxAttuned = maxAttunementSlots(char);
  let attunedCount = 0;
  let total = 0;

  for (const eq of char.equipment || []) {
    if (!eq || !eq.equipped) continue;
    if (eq.attuned) {
      attunedCount++;
      if (attunedCount > maxAttuned) continue;
    }

    let hasExplicitCheck = false;
    for (const [modKey, valKey] of [
      ['mod1', 'val1'],
      ['mod2', 'val2'],
    ] as const) {
      const attr = String(eq[modKey] || '')
        .trim()
        .toUpperCase();
      const val = Math.trunc(Number(eq[valKey] ?? 0) || 0);
      if (!attr || attr === 'NONE' || val === 0) continue;
      if (attr === 'CHECKS' || attr === 'CHECK' || attr === 'ABILITY_CHECKS' || attr === 'SKILLS') {
        total += val;
        hasExplicitCheck = true;
      }
    }

    if (!hasExplicitCheck) {
      const catalogBonus = catalogDefaultAbilityCheckBonus(eq.name);
      const itemCheck = Number((eq as { ability_check_bonus?: number }).ability_check_bonus ?? 0) || 0;
      total += catalogBonus || itemCheck;
    }
  }
  return total;
}

/**
 * Saving throw bonus contributed by equipped (and attuned within slot cap) equipment,
 * mirroring backend `stats_service.py`: explicit `mod1`/`mod2` (`SAVES` or `<STAT>_SAVE`)
 * takes precedence over catalog defaults (`Cloak of Protection`, `Ring of Protection`).
 */
export function equipmentSaveBonusForAbility(
  char: CharacterSchema | null | undefined,
  ability: string
): number {
  if (!char || char.magic_items_suppressed) return 0;
  const targetCode = ability.trim().toUpperCase();
  const maxAttuned = maxAttunementSlots(char);
  let attunedCount = 0;
  let total = 0;

  for (const eq of char.equipment || []) {
    if (!eq || !eq.equipped) continue;
    if (eq.attuned) {
      attunedCount++;
      if (attunedCount > maxAttuned) continue;
    }

    let hasExplicitSave = false;
    for (const [modKey, valKey] of [
      ['mod1', 'val1'],
      ['mod2', 'val2'],
    ] as const) {
      const attr = String(eq[modKey] || '')
        .trim()
        .toUpperCase();
      const val = Math.trunc(Number(eq[valKey] ?? 0) || 0);
      if (!attr || attr === 'NONE' || val === 0) continue;
      if (attr === 'SAVES' || attr === 'SAVE') {
        total += val;
        hasExplicitSave = true;
      } else if (attr.endsWith('_SAVE') && attr.split('_')[0] === targetCode) {
        total += val;
      }
    }

    if (!hasExplicitSave) {
      const catalogBonus = catalogDefaultSaveBonus(eq.name);
      const itemSave = Number((eq as { save_bonus?: number }).save_bonus ?? 0) || 0;
      total += catalogBonus || itemSave;
    }
  }
  return total;
}

/** Ability modifier, plus proficiency when trained, minus exhaustion, plus Aura/Soul/Gear/DM save bonuses. */
export function savingThrowModifier(
  char: CharacterSchema | null | undefined,
  ability: string
): number {
  if (!char?.stats) return 0;
  const code = ability.trim().toUpperCase();

  // Prefer backend-computed values
  const cached = char.saving_throw_values?.[code] ?? char.saving_throw_values?.[ability];
  if (cached !== undefined) {
    return cached;
  }

  let extraSaveBonus = equipmentSaveBonusForAbility(char, code);
  // Paladin 6+ Aura of Protection: +CHA modifier (minimum +1)
  const hasAura =
    classLevelFor(char, 'paladin') >= 6 ||
    (char.features_traits || []).some((f) =>
      (typeof f === 'string' ? f : f.name || '').toLowerCase().includes('aura of protection')
    );
  if (hasAura) {
    extraSaveBonus += Math.max(1, abilityModifierOf(char, 'CHA'));
  }

  // Artificer 20 Soul of Artifice: +1 per attuned magic item (max +6), disabled when magic items are suppressed
  if (!char.magic_items_suppressed) {
    const hasSoulOfArtifice =
      classLevelFor(char, 'artificer') >= 20 ||
      (char.features_traits || []).some((f) =>
        (typeof f === 'string' ? f : f.name || '').toLowerCase().includes('soul of artifice')
      );
    if (hasSoulOfArtifice) {
      const attunedCount = (char.equipment || []).filter((e) => e && e.attuned).length;
      extraSaveBonus += Math.min(6, attunedCount);
    }
  }

  const dmSave = char.dm_modifiers?.saving_throws_bonus ?? 0;
  return (
    abilityModifierOf(char, code) +
    (isSaveProficient(char, code) ? proficiencyBonus(char) : 0) -
    exhaustionD20Penalty(char) +
    extraSaveBonus +
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
