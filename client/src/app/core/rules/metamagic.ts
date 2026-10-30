import { CharacterSchema, ClassResource, FeatureTrait } from '../models/character.model';
import { sorceryPointsPool } from './flexible-casting';

/**
 * The Sorcerer's Metamagic options: what each costs in sorcery points, how many
 * the Sorcerer knows, and which ones this sheet has.
 *
 * Known options live on the sheet as features ("Metamagic: Quickened Spell"), so
 * an imported sheet that already lists them is read as-is and picking one in the
 * panel adds the same kind of feature. Costs differ by edition: 2014 Twinned
 * costs the spell's level (1 for a cantrip) and Heightened costs 3; in 2024
 * Twinned is 1 and Heightened 2.
 */
export type MetamagicEdition = '2014' | '2024';

export interface MetamagicOption {
  id: string;
  name: string;
  /** Flat cost; Twinned in 2014 pays the spell's level instead (`costBySpellLevel`). */
  cost: number;
  costBySpellLevel?: boolean;
  summary: string;
}

const COMMON: Omit<MetamagicOption, 'cost'>[] = [
  { id: 'careful', name: 'Careful Spell', summary: 'Chosen creatures automatically succeed on the spell’s saving throw.' },
  { id: 'distant', name: 'Distant Spell', summary: 'Double the range; a touch spell reaches 30 feet.' },
  { id: 'empowered', name: 'Empowered Spell', summary: 'Reroll damage dice up to your CHA modifier and keep the new rolls.' },
  { id: 'extended', name: 'Extended Spell', summary: 'Double the duration (max 24 hours).' },
  { id: 'heightened', name: 'Heightened Spell', summary: 'One target has disadvantage on its first save against the spell.' },
  { id: 'quickened', name: 'Quickened Spell', summary: 'Cast a 1-action spell as a bonus action.' },
  { id: 'seeking', name: 'Seeking Spell', summary: 'Reroll a missed spell attack roll.' },
  { id: 'subtle', name: 'Subtle Spell', summary: 'Cast without verbal or somatic components.' },
  { id: 'transmuted', name: 'Transmuted Spell', summary: 'Change the damage type to acid, cold, fire, lightning, poison or thunder.' },
  { id: 'twinned', name: 'Twinned Spell', summary: 'A single-target spell targets a second creature.' },
];

const COSTS: Record<MetamagicEdition, Record<string, number>> = {
  // PHB, plus Seeking and Transmuted from Tasha's.
  '2014': { careful: 1, distant: 1, empowered: 1, extended: 1, heightened: 3, quickened: 2, seeking: 2, subtle: 1, transmuted: 1, twinned: 1 },
  '2024': { careful: 1, distant: 1, empowered: 1, extended: 1, heightened: 2, quickened: 2, seeking: 1, subtle: 1, transmuted: 1, twinned: 1 },
};

export function metamagicEdition(edition: string | null | undefined): MetamagicEdition {
  return String(edition || '').includes('2024') ? '2024' : '2014';
}

export function metamagicOptions(edition: MetamagicEdition): MetamagicOption[] {
  return COMMON.map((o) => ({
    ...o,
    cost: COSTS[edition][o.id],
    costBySpellLevel: edition === '2014' && o.id === 'twinned' ? true : undefined,
  }));
}

/** Sorcery points an option costs; a 2014 Twinned cantrip still costs 1. */
export function metamagicCost(option: MetamagicOption, spellLevel = 1): number {
  return option.costBySpellLevel ? Math.max(1, spellLevel) : option.cost;
}

function sorcererLevel(char: CharacterSchema | null | undefined): number {
  const entry = (char?.classes ?? []).find((c) => /sorcerer/i.test(c.class_name || ''));
  if (entry) return entry.level || 0;
  return /sorcerer/i.test(char?.char_class || '') ? char?.char_level || 0 : 0;
}

/** How many options the class grants at this Sorcerer level (the Metamagic Adept feat adds 2). */
export function metamagicKnownLimit(char: CharacterSchema | null | undefined, edition: MetamagicEdition): number {
  const lvl = sorcererLevel(char);
  const fromClass =
    edition === '2024'
      ? lvl >= 17 ? 6 : lvl >= 10 ? 4 : lvl >= 2 ? 2 : 0
      : lvl >= 17 ? 4 : lvl >= 10 ? 3 : lvl >= 3 ? 2 : 0;
  const adept = (char?.features_traits ?? []).some((f) => /metamagic adept/i.test(f.name || '')) ? 2 : 0;
  return fromClass + adept;
}

export function metamagicFeatureName(option: MetamagicOption): string {
  return `Metamagic: ${option.name}`;
}

function mentions(text: string, option: MetamagicOption): boolean {
  const word = option.name.split(' ')[0];
  return new RegExp(`\\b${word}\\b`, 'i').test(text);
}

/**
 * The options this sheet knows: any feature named after one ("Metamagic:
 * Quickened Spell", "Twinned Spell"), or a Metamagic feature that lists a few
 * ("Metamagic (Quickened, Subtle)"). The class's own Metamagic feature text,
 * which describes every option, is not read as knowing them all.
 */
export function knownMetamagic(char: CharacterSchema | null | undefined, options: MetamagicOption[]): Set<string> {
  const known = new Set<string>();
  for (const feature of char?.features_traits ?? []) {
    const name = feature.name || '';
    options.filter((o) => new RegExp(`\\b${o.name}\\b`, 'i').test(name)).forEach((o) => known.add(o.id));
    if (!/metamagic/i.test(name) || /adept/i.test(name)) continue;

    const listed = options.filter((o) => mentions(name, o));
    const described = options.filter((o) => mentions(feature.description || '', o));
    listed.forEach((o) => known.add(o.id));
    if (described.length <= 6) described.forEach((o) => known.add(o.id));
  }
  return known;
}

/** Adds or removes the option's own feature; a known option read from other text is left alone. */
export function toggleMetamagicFeature(features: FeatureTrait[] | undefined, option: MetamagicOption): FeatureTrait[] {
  const name = metamagicFeatureName(option);
  const list = features ?? [];
  if (list.some((f) => f.name === name)) return list.filter((f) => f.name !== name);
  return [...list, { name, description: option.summary, source: 'Sorcerer (Metamagic)' }];
}

/** Spends the option's cost from Sorcery Points; null when the pool can't pay. */
export function spendMetamagic(
  char: CharacterSchema,
  option: MetamagicOption,
  spellLevel = 1
): ClassResource[] | null {
  const pool = sorceryPointsPool(char);
  const cost = metamagicCost(option, spellLevel);
  if (!pool || pool.current < cost) return null;
  return (char.class_resources ?? []).map((r) => (r === pool ? { ...r, current: r.current - cost } : r));
}
