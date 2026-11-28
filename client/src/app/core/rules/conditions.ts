import type { CharacterSchema, ClassEntry, FeatureTrait } from '../models/character.model';
import { effectiveExhaustionLevel, is2024Edition, isDeceasedByExhaustion } from './ability';

export type ConditionRollKind = 'attack' | 'check' | 'save' | 'initiative';
export type CountermeasureKind = 'immune' | 'advantage' | 'action_end' | 'sense_mitigation';
export type DamageMitigationMode = 'raw' | 'resist' | 'vuln' | 'immune';

export interface ConditionCountermeasure {
  condition: string;
  source: string;
  kind: CountermeasureKind;
  detail: string;
}

export interface ConditionRollState {
  hasAdvantage: boolean;
  hasDisadvantage: boolean;
  advReasons: string[];
  disReasons: string[];
}

export interface ConditionEffectsSummary {
  normalizedConditions: string[];
  speedZeroConditions: string[];
  autoFailSaveAbilities: Set<'STR' | 'DEX'>;
  dexSaveDisadvantage: boolean;
  roll: Record<ConditionRollKind, ConditionRollState>;
}

export interface DamageDefensePill {
  label: string;
  mode: DamageMitigationMode;
}

export type RuleSheetLike = {
  char_class?: string;
  subclass?: string;
  char_level?: number;
  level?: number;
  classes?: ClassEntry[];
  race?: string;
  dnd_edition?: string;
  ruleset_version?: string;
  conditions?: string[];
  senses?: string[];
  features_traits?: FeatureTrait[];
  speed?: number;
  base_speed?: number;
  heavy_armor_speed_penalty?: number;
  exhaustion_level?: number;
  exhaustion_bypass?: boolean;
  dm_modifiers?: { speed_bonus?: number };
  damage_resistances?: string[];
  damage_immunities?: string[];
  damage_vulnerabilities?: string[];
};

export const SPEED_ZERO_CONDITIONS = new Set([
  'grappled',
  'restrained',
  'paralyzed',
  'stunned',
  'unconscious',
  'petrified',
]);

/**
 * 2014 Stunned says "can't move"; 2024 Stunned only applies Incapacitated (no Speed 0).
 * Mirrors `backend/services/condition_rules.py::has_speed_zero_condition`.
 */
export function isSpeedZeroCondition(condition: string, is2024: boolean): boolean {
  const low = String(condition || '').trim().toLowerCase();
  if (is2024 && low === 'stunned') return false;
  return SPEED_ZERO_CONDITIONS.has(low);
}

export const AUTO_FAIL_STR_DEX_CONDITIONS = new Set([
  'paralyzed',
  'stunned',
  'unconscious',
  'petrified',
]);

export const INCAPACITATING_CONDITIONS = new Set([
  'incapacitated',
  'unconscious',
  'paralyzed',
  'petrified',
  'stunned',
]);

function normalizeConditionNames(conditions: string[] | null | undefined): string[] {
  if (!Array.isArray(conditions)) return [];
  const seen = new Set<string>();
  const out: string[] = [];
  for (const raw of conditions) {
    const trimmed = String(raw || '').trim();
    const low = trimmed.toLowerCase();
    if (trimmed && !seen.has(low)) {
      seen.add(low);
      out.push(trimmed);
    }
  }
  return out;
}

function classLevel(char: RuleSheetLike | null | undefined, className: string): number {
  if (!char) return 0;
  const target = className.trim().toLowerCase();
  let best = 0;
  for (const cls of char.classes || []) {
    if ((cls?.class_name || '').trim().toLowerCase() === target) {
      best = Math.max(best, Number(cls?.level || 0) || 0);
    }
  }
  if (best === 0 && (char.char_class || '').trim().toLowerCase() === target) {
    best = Math.max(best, Number(char.char_level ?? char.level ?? 1) || 1);
  }
  return best;
}

function hasSubclass(
  char: RuleSheetLike | null | undefined,
  className: string,
  subclassFrag: string,
  minLevel = 1
): boolean {
  if (!char) return false;
  const targetCls = className.trim().toLowerCase();
  const frag = subclassFrag.trim().toLowerCase();
  for (const cls of char.classes || []) {
    if (
      (cls?.class_name || '').trim().toLowerCase() === targetCls &&
      (cls?.subclass || '').trim().toLowerCase().includes(frag) &&
      (Number(cls?.level || 0) || 0) >= minLevel
    ) {
      return true;
    }
  }
  return (
    (char.char_class || '').trim().toLowerCase() === targetCls &&
    (char.subclass || '').trim().toLowerCase().includes(frag) &&
    (Number(char.char_level ?? char.level ?? 1) || 1) >= minLevel
  );
}

function featureNamesLower(char: RuleSheetLike | null | undefined): string[] {
  if (!char?.features_traits) return [];
  return char.features_traits
    .map((f) => (typeof f === 'string' ? f : f?.name || '').trim().toLowerCase())
    .filter(Boolean);
}

function findSense(char: RuleSheetLike | null | undefined, keyword: string): string | null {
  const kw = keyword.trim().toLowerCase();
  for (const s of char?.senses || []) {
    const clean = String(s || '').trim();
    if (clean.toLowerCase().includes(kw)) return clean;
  }
  return null;
}

export function evaluateConditionEffects(
  char: RuleSheetLike | null | undefined,
  overrideConditions?: string[]
): ConditionEffectsSummary {
  const normalized = normalizeConditionNames(overrideConditions ?? char?.conditions);
  const lowSet = new Set(normalized.map((c) => c.toLowerCase()));
  const is2024 = is2024Edition(char as CharacterSchema);

  const speedZeroConditions = normalized.filter((c) => isSpeedZeroCondition(c, is2024));
  const autoFailSaveAbilities = new Set<'STR' | 'DEX'>();
  for (const c of lowSet) {
    if (AUTO_FAIL_STR_DEX_CONDITIONS.has(c)) {
      autoFailSaveAbilities.add('STR');
      autoFailSaveAbilities.add('DEX');
      break;
    }
  }
  const dexSaveDisadvantage = lowSet.has('restrained');

  const roll: Record<ConditionRollKind, ConditionRollState> = {
    attack: { hasAdvantage: false, hasDisadvantage: false, advReasons: [], disReasons: [] },
    check: { hasAdvantage: false, hasDisadvantage: false, advReasons: [], disReasons: [] },
    save: { hasAdvantage: false, hasDisadvantage: false, advReasons: [], disReasons: [] },
    initiative: { hasAdvantage: false, hasDisadvantage: false, advReasons: [], disReasons: [] },
  };

  if (lowSet.has('invisible')) {
    roll.attack.hasAdvantage = true;
    roll.attack.advReasons.push('Invisible');
    if (is2024) {
      roll.initiative.hasAdvantage = true;
      roll.initiative.advReasons.push('Invisible (2024)');
    }
  }

  for (const cond of normalized) {
    const low = cond.toLowerCase();
    if (is2024 && INCAPACITATING_CONDITIONS.has(low)) {
      roll.initiative.hasDisadvantage = true;
      roll.initiative.disReasons.push(cond);
    }
    if (low === 'poisoned' || low === 'frightened') {
      roll.attack.hasDisadvantage = true;
      roll.attack.disReasons.push(cond);
      roll.check.hasDisadvantage = true;
      roll.check.disReasons.push(cond);
      roll.initiative.hasDisadvantage = true;
      roll.initiative.disReasons.push(cond);
    } else if (low === 'blinded' || low === 'restrained' || low === 'prone') {
      roll.attack.hasDisadvantage = true;
      roll.attack.disReasons.push(cond);
    }
  }

  return {
    normalizedConditions: normalized,
    speedZeroConditions,
    autoFailSaveAbilities,
    dexSaveDisadvantage,
    roll,
  };
}

export function isAutoFailSave(
  char: RuleSheetLike | null | undefined,
  ability: string
): boolean {
  const code = String(ability || '').trim().toUpperCase().slice(0, 3);
  if (code !== 'STR' && code !== 'DEX') return false;
  return evaluateConditionEffects(char).autoFailSaveAbilities.has(code);
}

export function hasConditionDisadvantage(
  char: RuleSheetLike | null | undefined,
  kind: ConditionRollKind,
  stat = ''
): boolean {
  const summary = evaluateConditionEffects(char);
  if (kind === 'save') {
    const up = String(stat || '').trim().toUpperCase();
    return (up === 'DEX' || up === 'DEXTERITY') && summary.dexSaveDisadvantage;
  }
  return summary.roll[kind].hasDisadvantage;
}

export function hasConditionAdvantage(
  char: RuleSheetLike | null | undefined,
  kind: ConditionRollKind
): boolean {
  return evaluateConditionEffects(char).roll[kind].hasAdvantage;
}

/**
 * Non-destructive effective speed: returns 0 when deceased/Exhaustion-stopped or
 * affected by Grappled/Restrained/Paralyzed/Stunned/Unconscious/Petrified. When unlocked,
 * restores from `base_speed` if `speed` still holds a stale 0 before backend sync completes.
 */
export function effectiveSpeed(char: RuleSheetLike | null | undefined): number {
  if (!char) return 0;
  if (isDeceasedByExhaustion(char)) return 0;
  const effExh = effectiveExhaustionLevel(char);
  const is2024 = is2024Edition(char as CharacterSchema);
  if (!is2024 && effExh >= 5) return 0;
  if (evaluateConditionEffects(char).speedZeroConditions.length > 0) return 0;

  if (typeof char.speed === 'number' && char.speed > 0) {
    return char.speed;
  }
  if (typeof char.base_speed === 'number' && char.base_speed > 0) {
    const armorPenalty = char.heavy_armor_speed_penalty ?? 0;
    const dmSpeed = char.dm_modifiers?.speed_bonus ?? 0;
    const raw = Math.max(0, char.base_speed - armorPenalty + dmSpeed);
    if (is2024) return Math.max(0, raw - effExh * 5);
    return effExh >= 2 ? Math.floor(raw / 2) : raw;
  }
  return char.speed ?? 0;
}

export function speedLockReason(char: RuleSheetLike | null | undefined): string | null {
  if (!char) return null;
  if (isDeceasedByExhaustion(char)) return 'Exhaustion 6';
  const effExh = effectiveExhaustionLevel(char);
  if (!is2024Edition(char as CharacterSchema) && effExh >= 5) {
    return `Exhaustion ${effExh}`;
  }
  const lockedBy = evaluateConditionEffects(char).speedZeroConditions;
  return lockedBy.length > 0 ? lockedBy.join(', ') : null;
}

/**
 * Mirrors `backend/services/condition_rules.py::detect_condition_countermeasures`.
 * Non-blocking: surfaces class/subclass/species/sense protections as alerts.
 */
export function getConditionCountermeasures(
  char: RuleSheetLike | null | undefined
): ConditionCountermeasure[] {
  if (!char) return [];
  const is2024 = is2024Edition(char as CharacterSchema);
  const ftNames = featureNamesLower(char);
  const race = String(char.race || '').trim().toLowerCase();
  const out: ConditionCountermeasure[] = [];

  const add = (condition: string, source: string, kind: CountermeasureKind, detail: string) => {
    out.push({ condition, source, kind, detail });
  };

  if (ftNames.some((fn) => fn.includes('mindless rage')) || hasSubclass(char, 'barbarian', 'berserker', 6)) {
    add('Charmed', 'Mindless Rage', 'immune', 'Immune to Charmed while Raging');
    add('Frightened', 'Mindless Rage', 'immune', 'Immune to Frightened while Raging');
  }

  if (ftNames.some((fn) => fn.includes('aura of courage')) || classLevel(char, 'paladin') >= 10) {
    add('Frightened', 'Aura of Courage', 'immune', 'Immune to Frightened');
  }

  if (ftNames.some((fn) => fn.includes('aura of devotion')) || hasSubclass(char, 'paladin', 'devotion', 7)) {
    add('Charmed', 'Aura of Devotion', 'immune', 'Immune to Charmed');
  }

  const monkLvl = classLevel(char, 'monk');
  if (is2024) {
    if (ftNames.some((fn) => fn.includes('self-restoration')) || monkLvl >= 10) {
      for (const cond of ['Charmed', 'Frightened', 'Poisoned']) {
        add(cond, 'Self-Restoration', 'action_end', `Bonus Action (no Focus cost) to end ${cond}`);
      }
    }
  } else {
    if (ftNames.some((fn) => fn.includes('stillness of mind')) || monkLvl >= 7) {
      for (const cond of ['Charmed', 'Frightened']) {
        add(cond, 'Stillness of Mind', 'action_end', `Use your Action to end ${cond}`);
      }
    }
    if (ftNames.some((fn) => fn.includes('purity of body')) || monkLvl >= 10) {
      add('Poisoned', 'Purity of Body', 'immune', 'Immune to disease and poison (2014 Monk L10)');
    }
  }

  if (ftNames.some((fn) => fn.includes("nature's ward")) || hasSubclass(char, 'druid', 'land', 10)) {
    add(
      'Poisoned',
      "Nature's Ward",
      'immune',
      is2024
        ? "Immune to the Poisoned condition (2024 Nature's Ward)"
        : 'Immune to poison & disease (2014 Land Druid)'
    );
  }

  const hasFeyAncestry =
    ftNames.some((fn) => fn.includes('fey ancestry')) ||
    ['elf', 'eladrin', 'drow', 'shadar-kai', 'astral'].some((k) => race.includes(k));
  if (hasFeyAncestry) {
    add(
      'Charmed',
      'Fey Ancestry',
      'advantage',
      is2024 ? 'Advantage on saving throws to avoid or end Charmed' : 'Advantage on saving throws against being Charmed'
    );
  }

  if (ftNames.some((fn) => fn === 'brave' || fn.includes('brave (')) || race.includes('halfling')) {
    add('Frightened', 'Brave', 'advantage', 'Advantage on saving throws against being Frightened');
  }

  if (ftNames.some((fn) => fn.includes('stout resilience')) || (race.includes('stout') && race.includes('halfling'))) {
    add('Poisoned', 'Stout Resilience', 'advantage', 'Advantage on saving throws against poison (+ Poison Resistance)');
  }

  if (ftNames.some((fn) => fn.includes('dwarven resilience')) || race.includes('dwarf')) {
    add(
      'Poisoned',
      'Dwarven Resilience',
      'advantage',
      is2024
        ? 'Advantage on saves to avoid or end Poisoned (+ Poison Resistance)'
        : 'Advantage on saving throws against poison (+ Poison Resistance)'
    );
  }

  if (ftNames.some((fn) => fn.includes('constructed resilience')) || race.includes('warforged')) {
    add(
      'Poisoned',
      'Constructed Resilience',
      'advantage',
      'Advantage on saving throws vs poisoned/poison (+ Poison Resistance)'
    );
  }

  const blindSense =
    findSense(char, 'blindsight') ||
    (ftNames.some((fn) => fn.includes('blind fighting'))
      ? 'Blindsight 10 ft.'
      : is2024 && ftNames.some((fn) => fn.includes('blindsight'))
        ? 'Blindsight 30 ft.'
        : null);
  if (blindSense) {
    add('Blinded', blindSense, 'sense_mitigation', `${blindSense}: perceives targets within range without sight`);
  }

  const trueSense = findSense(char, 'truesight');
  if (trueSense) {
    add('Blinded', trueSense, 'sense_mitigation', `${trueSense}: sees normally within range and penetrates darkness/invisibility`);
  }

  const seen = new Set<string>();
  return out.filter((item) => {
    const key = `${item.condition.toLowerCase()}::${item.source.toLowerCase()}`;
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}

export function detectConditionWarnings(
  char: RuleSheetLike | null | undefined,
  selectedConditions: Iterable<string>
): ConditionCountermeasure[] {
  const activeSet = new Set(Array.from(selectedConditions, (c) => String(c || '').trim().toLowerCase()).filter(Boolean));
  if (activeSet.size === 0) return [];
  return getConditionCountermeasures(char).filter((cm) => activeSet.has(cm.condition.toLowerCase()));
}

export function describeConditionImpact(
  condition: string,
  char: RuleSheetLike | null | undefined
): string[] {
  const low = condition.trim().toLowerCase();
  const is2024 = is2024Edition(char as CharacterSchema);
  const tags: string[] = [];
  if (low === 'poisoned') tags.push('DIS Atk & Checks');
  if (low === 'frightened') tags.push('DIS Atk & Checks (in LOS)');
  if (low === 'blinded' || low === 'prone') tags.push('DIS Atk');
  if (low === 'restrained') tags.push('DIS Atk & DEX Save');
  if (low === 'petrified') tags.push('Resist All Damage');
  if (low === 'invisible') {
    tags.push('ADV Atk');
    if (is2024) tags.push('ADV Init (2024)');
  }
  if (isSpeedZeroCondition(low, is2024)) tags.push('Speed 0 ft');
  if (AUTO_FAIL_STR_DEX_CONDITIONS.has(low)) tags.push('Auto-Fail STR/DEX');
  if (is2024 && INCAPACITATING_CONDITIONS.has(low)) tags.push('DIS Init (2024)');
  return tags;
}

/** D&D 5e damage mitigation math (resistance rounds down). */
export function computeAdjustedDamage(rawAmount: number, mode: DamageMitigationMode): number {
  const safe = Math.max(0, Math.floor(Number(rawAmount) || 0));
  if (mode === 'immune') return 0;
  if (mode === 'resist') return Math.floor(safe / 2);
  if (mode === 'vuln') return safe * 2;
  return safe;
}

/** Match a damage label against Immunity -> Vulnerability -> Resistance precedence. */
export function inferDamageMitigation(
  damageType: string,
  resistances: string[] = [],
  immunities: string[] = [],
  vulnerabilities: string[] = []
): DamageMitigationMode {
  const needle = String(damageType || '').trim().toLowerCase();
  if (!needle) return 'raw';
  const matches = (list: string[]) =>
    list.some((entry) => {
      const e = String(entry || '').trim().toLowerCase();
      return !!e && (e === needle || e.includes(needle) || needle.includes(e));
    });
  if (matches(immunities)) return 'immune';
  if (matches(vulnerabilities)) return 'vuln';
  if (matches(resistances)) return 'resist';
  return 'raw';
}

export function buildDamageDefensePills(
  resistances: string[] = [],
  immunities: string[] = [],
  vulnerabilities: string[] = []
): DamageDefensePill[] {
  const pills: DamageDefensePill[] = [];
  const immuneKeys = new Set<string>();
  const seenModeKeys = new Set<string>();
  for (const raw of immunities || []) {
    const label = String(raw || '').trim();
    const key = label.toLowerCase();
    if (label && !immuneKeys.has(key)) {
      immuneKeys.add(key);
      pills.push({ label, mode: 'immune' });
    }
  }
  const addNonImmune = (items: string[], mode: 'vuln' | 'resist') => {
    for (const raw of items || []) {
      const label = String(raw || '').trim();
      const key = label.toLowerCase();
      const modeKey = `${mode}:${key}`;
      if (label && !immuneKeys.has(key) && !seenModeKeys.has(modeKey)) {
        seenModeKeys.add(modeKey);
        pills.push({ label, mode });
      }
    }
  };
  addNonImmune(vulnerabilities, 'vuln');
  addNonImmune(resistances, 'resist');
  return pills;
}
