import {
  CharacterSchema,
  CurrencyBlock,
  EncumbranceStatus,
  EquipmentItem,
  Weapon,
  WeightBreakdown,
} from '../models/character.model';

/**
 * Pure D&D 2014 & 2024 rules arithmetic for carried weight, carrying capacity,
 * ammunition classification/recovery, and utility consumables (#262).
 *
 * Mirrors `backend/services/inventory_service.py` with zero `@angular/*` imports.
 */

const SIZE_CAPACITY_MULTIPLIERS: Record<string, number> = {
  tiny: 0.5,
  small: 1,
  medium: 1,
  large: 2,
  huge: 4,
  gargantuan: 8,
};

const ONE_SIZE_LARGER_MARKERS = [
  'powerful build',
  'equine build',
  'hippo build',
  'little giant',
  'brawny',
];

const ONE_SIZE_LARGER_SPECIES = ['goliath', 'firbolg', 'bugbear'];

const AMMO_WEAPON_KEYWORDS =
  /\b(longbow|shortbow|crossbow|light crossbow|heavy crossbow|hand crossbow|sling|blowgun|pistol|musket)\b/i;

const THROWN_WEAPON_KEYWORDS = /\b(javelin|dagger|handaxe|light hammer|spear|trident|dart|net)\b/i;

/**
 * Canonical catalog unit weights (lb) mirroring `data/rules/items.json` and `weapons.json`
 * for instant offline/optimistic UI calculation before server hydration returns.
 */
export const CATALOG_WEIGHTS_LB: Record<string, number> = {
  'plate': 65,
  'plate armor': 65,
  'dwarven plate': 65,
  'chain mail': 55,
  'splint': 60,
  'splint armor': 60,
  'ring mail': 40,
  'scale mail': 45,
  'dragon scale mail': 45,
  'breastplate': 20,
  'chain shirt': 20,
  'elven chain': 20,
  'half plate': 40,
  'hide': 12,
  'hide armor': 12,
  'studded leather': 13,
  'leather': 10,
  'leather armor': 10,
  'padded': 8,
  'padded armor': 8,
  'shield': 6,
  'sentinel shield': 6,
  'spellguard shield': 6,
  'cloak of protection': 1,
  'bracers of defense': 1,
  'robe of the archmagi': 4,
  'robe of stars': 4,
  'gauntlets of ogre power': 2,
  'amulet of health': 0.5,
  'headband of intellect': 0.5,
  'belt of hill giant strength': 3,
  'belt of stone giant strength': 3,
  'belt of frost giant strength': 3,
  'belt of fire giant strength': 3,
  'belt of cloud giant strength': 3,
  'belt of storm giant strength': 3,
  'belt of dwarvenkind': 3,
  'manual of gainful exercise': 5,
  'manual of quickness of action': 5,
  'manual of bodily health': 5,
  'tome of clear thought': 5,
  'tome of understanding': 5,
  'tome of leadership and influence': 5,
  'staff of power': 4,
  'staff of the magi': 4,
  'wand of the war mage': 1,
  'rod of the pact keeper': 2,
  'arcane grimoire': 3,
  'moon sickle': 2,
  "rhythm-maker's drum": 3,
  'all-purpose tool': 1,
  'bracers of archery': 1,
  'boots of speed': 1,
  'boots of striding and springing': 1,
  'boots of elvenkind': 1,
  'winged boots': 1,
  'cloak of elvenkind': 1,
  'cloak of displacement': 1,
  'cloak of the bat': 1,
  'goggles of night': 0.5,
  'gloves of missile snaring': 0.5,
  'alchemy jug': 12,
  'potion of healing': 0.5,
  'potion of greater healing': 0.5,
  'potion of superior healing': 0.5,
  'potion of supreme healing': 0.5,
  'healing potion': 0.5,
  'greater healing potion': 0.5,
  'superior healing potion': 0.5,
  'supreme healing potion': 0.5,
  'potion of invisibility': 0.5,
  'potion of flying': 0.5,
  'potion of speed': 0.5,
  'potion of heroism': 0.5,
  'antitoxin': 0.1,
  'bag of holding': 15,
  'handy haversack': 5,
  "thieves' tools": 1,
  "healer's kit": 3,
  'component pouch': 2,
  'arcane focus': 1,
  'druidic focus': 1,
  'holy symbol': 1,
  "explorer's pack": 59,
  "dungeoneer's pack": 61.5,
  'arrows (20)': 1,
  'arrow': 0.05,
  'arrows': 0.05,
  'crossbow bolts (20)': 1.5,
  'crossbow bolt': 0.075,
  'crossbow bolts': 0.075,
  'bolts': 0.075,
  'sling bullets (20)': 1.5,
  'sling bullet': 0.075,
  'sling bullets': 0.075,
  'bullets': 0.075,
  'blowgun needles (50)': 1,
  'blowgun needle': 0.02,
  'blowgun needles': 0.02,
  'quiver': 1,
  'crossbow bolt case': 1,
  'bolt case': 1,
  'backpack': 5,
  'bedroll': 7,
  'pouch': 1,
  'rations (1 day)': 2,
  'rations': 2,
  'rope, hempen (50 ft.)': 10,
  'hempen rope': 10,
  '50 ft hempen rope': 10,
  'rope, silk (50 ft.)': 5,
  'silk rope': 5,
  '50 ft silk rope': 5,
  'torch': 1,
  'torches': 1,
  'waterskin': 5,
  'tinderbox': 1,
  'crowbar': 5,
  'lantern, hooded': 2,
  'hooded lantern': 2,
  'common clothes': 3,
  "traveler's clothes": 4,
  'fine clothes': 6,
  'spellbook': 3,
  // Weapons (matching data/rules/weapons.json)
  'club': 2,
  'dagger': 1,
  'greatclub': 10,
  'handaxe': 2,
  'javelin': 2,
  'light hammer': 2,
  'mace': 4,
  'quarterstaff': 4,
  'sickle': 2,
  'spear': 3,
  'battleaxe': 4,
  'flail': 2,
  'glaive': 6,
  'greataxe': 7,
  'greatsword': 6,
  'halberd': 6,
  'longsword': 3,
  'maul': 10,
  'morningstar': 4,
  'pike': 18,
  'rapier': 2,
  'scimitar': 3,
  'shortsword': 2,
  'trident': 4,
  'warhammer': 2,
  'whip': 3,
  'light crossbow': 5,
  'shortbow': 2,
  'longbow': 2,
  'musket': 4,
  'pistol': 3,
  'heavy crossbow': 18,
  'hand crossbow': 3,
  'dart': 0.25,
  'sling': 0,
  'blowgun': 1,
};

export function parseWeightLb(rawWeight: unknown): number | null {
  if (rawWeight === null || rawWeight === undefined || typeof rawWeight === 'boolean') {
    return null;
  }
  if (typeof rawWeight === 'number') {
    return Number.isFinite(rawWeight) ? Math.max(0, Math.round(rawWeight * 10000) / 10000) : null;
  }
  const text = String(rawWeight).trim().toLowerCase();
  if (!text) return null;
  if (/^\s*-/.test(text)) return 0;

  const mixed = /(\d+)\s+(\d+)\s*\/\s*(\d+)/.exec(text);
  if (mixed && Number(mixed[3]) !== 0) {
    const val = Number(mixed[1]) + Number(mixed[2]) / Number(mixed[3]);
    return Math.max(0, Math.round(val * 10000) / 10000);
  }
  const frac = /(\d+)\s*\/\s*(\d+)/.exec(text);
  if (frac && Number(frac[2]) !== 0) {
    return Math.max(0, Math.round((Number(frac[1]) / Number(frac[2])) * 10000) / 10000);
  }
  const num = /(\d+(?:\.\d+)?|\.\d+)/.exec(text);
  if (!num) return null;
  return Math.max(0, Math.round(Number(num[1]) * 10000) / 10000);
}

function normalizeWeightLookupName(rawName: string | undefined): string {
  return String(rawName || '')
    .toLowerCase()
    .replace(/\(\s*\+\s*[1-3]\s*\)/g, ' ')
    .replace(/\+\s*\d+/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();
}

export function catalogDefaultWeightLb(name: string | undefined): number {
  const exact = String(name || '')
    .trim()
    .toLowerCase()
    .replace(/\s+/g, ' ');
  if (!exact) return 0;
  if (CATALOG_WEIGHTS_LB[exact] !== undefined) {
    return CATALOG_WEIGHTS_LB[exact];
  }
  const stripped = normalizeWeightLookupName(exact);
  if (CATALOG_WEIGHTS_LB[stripped] !== undefined) {
    return CATALOG_WEIGHTS_LB[stripped];
  }
  const noParens = stripped
    .replace(/\([^)]*\)/g, ' ')
    .replace(/,/g, ' ')
    .replace(/\barmou?r\b/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();
  if (CATALOG_WEIGHTS_LB[noParens] !== undefined) {
    return CATALOG_WEIGHTS_LB[noParens];
  }
  return 0;
}

export function effectiveItemUnitWeightLb(item: EquipmentItem | null | undefined): number {
  if (!item) return 0;
  const explicit = parseWeightLb(item.weight);
  if (explicit !== null) return explicit;
  const resolved = parseWeightLb(item.resolved_weight_lb);
  if (resolved !== null) return resolved;
  return catalogDefaultWeightLb(item.name);
}

export function effectiveWeaponUnitWeightLb(weapon: Weapon | null | undefined): number {
  if (!weapon) return 0;
  const explicit = parseWeightLb(weapon.weight);
  if (explicit !== null) return explicit;
  const resolved = parseWeightLb(weapon.resolved_weight_lb);
  if (resolved !== null) return resolved;
  return catalogDefaultWeightLb(weapon.name);
}

export function computeCoinWeightLb(currency: CurrencyBlock | null | undefined): number {
  if (!currency) return 0;
  const coins =
    Math.max(0, Math.trunc(Number(currency.cp) || 0)) +
    Math.max(0, Math.trunc(Number(currency.sp) || 0)) +
    Math.max(0, Math.trunc(Number(currency.ep) || 0)) +
    Math.max(0, Math.trunc(Number(currency.gp) || 0)) +
    Math.max(0, Math.trunc(Number(currency.pp) || 0));
  return Math.round((coins / 50) * 100) / 100;
}

function hasOneSizeLargerCapacity(char: CharacterSchema | null | undefined): string | null {
  if (!char) return null;
  for (const feat of char.features_traits || []) {
    const name = (typeof feat === 'string' ? feat : feat?.name || '').trim();
    const desc = (typeof feat === 'string' ? '' : feat?.description || '').toLowerCase();
    const low = name.toLowerCase();
    if (ONE_SIZE_LARGER_MARKERS.some((marker) => low.includes(marker))) {
      return name;
    }
    if (
      (desc.includes('one size larger') || desc.includes('as if you were one size larger')) &&
      desc.includes('carrying capacity')
    ) {
      return name;
    }
  }
  const raceLow = (char.race || '').toLowerCase();
  if (ONE_SIZE_LARGER_SPECIES.some((s) => raceLow.includes(s))) {
    return 'Powerful Build';
  }
  return null;
}

export function hasBearAspectDoubleCapacity(char: CharacterSchema | null | undefined): boolean {
  if (!char) return false;
  for (const feat of char.features_traits || []) {
    const fname = (typeof feat === 'string' ? feat : feat?.name || '').toLowerCase();
    const fdesc = (typeof feat === 'string' ? '' : feat?.description || '').toLowerCase();
    const hasAllThreeChoices = fdesc.includes('eagle') && fdesc.includes('wolf');
    if (fname.includes('aspect of the beast')) {
      if (fname.includes('bear') || (fdesc.includes('bear') && !hasAllThreeChoices)) {
        return true;
      }
      if (/\b(?:chosen|totem)\s*:\s*bear\b/.test(fdesc)) {
        return true;
      }
    }
    if (
      fdesc.includes('carrying capacity') &&
      fdesc.includes('doubled') &&
      (fname + ' ' + fdesc).includes('bear') &&
      !hasAllThreeChoices
    ) {
      return true;
    }
  }
  return false;
}

export function computeCarryingCapacity(char: CharacterSchema | null | undefined): {
  capacityLb: number;
  multiplier: number;
  sources: string[];
} {
  const strScore = Math.max(1, Math.trunc(Number(char?.stats?.STR ?? 10) || 10));
  const rawSize = String((char as { size?: string } | null | undefined)?.size || 'Medium').trim();
  const sizeMult = SIZE_CAPACITY_MULTIPLIERS[rawSize.toLowerCase()] ?? 1;

  let multiplier = sizeMult;
  const sources: string[] = [`15 × STR ${strScore}`];
  if (sizeMult !== 1) {
    sources.push(`${rawSize} size (×${sizeMult})`);
  }

  const oneSizeSource = hasOneSizeLargerCapacity(char);
  if (oneSizeSource) {
    multiplier *= 2;
    sources.push(`${oneSizeSource} (×2)`);
  }

  if (hasBearAspectDoubleCapacity(char)) {
    multiplier *= 2;
    sources.push('Aspect of the Beast: Bear (×2)');
  }

  const capacityLb = Math.round(15 * strScore * multiplier * 10) / 10;
  return { capacityLb, multiplier, sources };
}

export interface EncumbranceSummary {
  totalWeightLb: number;
  capacityLb: number;
  status: EncumbranceStatus;
  percentUsed: number;
  breakdown: WeightBreakdown;
}

export function computeEncumbranceSummary(
  char: CharacterSchema | null | undefined
): EncumbranceSummary {
  let equipmentLb = 0;
  for (const eq of char?.equipment || []) {
    if (!eq || eq.weight_ignored) continue;
    const qty = eq.quantity !== undefined && eq.quantity !== null ? Math.max(0, Math.trunc(eq.quantity)) : 1;
    equipmentLb += effectiveItemUnitWeightLb(eq) * qty;
  }

  let weaponsLb = 0;
  for (const w of char?.weapons || []) {
    if (!w || w.weight_ignored) continue;
    weaponsLb += effectiveWeaponUnitWeightLb(w);
  }

  equipmentLb = Math.round(equipmentLb * 100) / 100;
  weaponsLb = Math.round(weaponsLb * 100) / 100;
  const coinsLb = computeCoinWeightLb(char?.currency);
  const totalWeightLb = Math.round((equipmentLb + weaponsLb + coinsLb) * 10) / 10;

  const { capacityLb, multiplier, sources } = computeCarryingCapacity(char);
  const encumberedLb = Math.round((capacityLb / 3) * 10) / 10;
  const heavilyLb = Math.round(((2 * capacityLb) / 3) * 10) / 10;
  const pushDragLiftLb = Math.round(capacityLb * 2 * 10) / 10;

  let status: EncumbranceStatus = 'unencumbered';
  if (totalWeightLb > capacityLb) {
    status = 'over_capacity';
  } else if (totalWeightLb > heavilyLb) {
    status = 'heavily_encumbered';
  } else if (totalWeightLb > encumberedLb) {
    status = 'encumbered';
  }

  const percentUsed =
    capacityLb > 0 ? Math.min(100, Math.round((totalWeightLb / capacityLb) * 100)) : 100;

  return {
    totalWeightLb,
    capacityLb,
    status,
    percentUsed,
    breakdown: {
      equipment_lb: equipmentLb,
      weapons_lb: weaponsLb,
      coins_lb: coinsLb,
      multiplier: Math.round(multiplier * 100) / 100,
      capacity_sources: sources,
      encumbered_threshold_lb: encumberedLb,
      heavily_encumbered_threshold_lb: heavilyLb,
      push_drag_lift_lb: pushDragLiftLb,
    },
  };
}

export interface WeaponAmmoClassification {
  usesAmmunition: boolean;
  isThrown: boolean;
  isRepeatingShot: boolean;
  canTrackAmmo: boolean;
  suggestedMax: number;
}

function weaponPropsLower(weapon: Weapon): string {
  const raw = weapon.properties as unknown;
  if (Array.isArray(raw)) {
    return raw.map((x) => String(x || '')).join(', ').toLowerCase();
  }
  return String(raw || '').toLowerCase();
}

export function classifyWeaponAmmo(
  weapon: Weapon,
  char?: CharacterSchema | null
): WeaponAmmoClassification {
  const name = (weapon.name || '').toLowerCase();
  const desc = (weapon.description || '').toLowerCase();
  const props = weaponPropsLower(weapon);

  const usesAmmunition =
    props.includes('ammunition') || AMMO_WEAPON_KEYWORDS.test(name);
  const isThrown = props.includes('thrown') || THROWN_WEAPON_KEYWORDS.test(name);

  const weaponTagsRepeating =
    name.includes('repeating shot') ||
    desc.includes('repeating shot') ||
    desc.includes('creates its own ammunition') ||
    props.includes('repeating');

  const baseWeaponName = normalizeWeightLookupName(name);
  const charHasRepeatingFeature = (char?.features_traits || []).some((f) => {
    const fname = (typeof f === 'string' ? f : f?.name || '').toLowerCase();
    const fdesc = (typeof f === 'string' ? '' : f?.description || '').toLowerCase();
    if (!fname.includes('repeating shot')) return false;
    if (!usesAmmunition) return false;
    const explicitInfusion = /infused into\s+([a-z0-9\s'-]+)/i.exec(fdesc);
    if (explicitInfusion) {
      const infusedTarget = normalizeWeightLookupName(explicitInfusion[1]);
      return Boolean(baseWeaponName && infusedTarget.includes(baseWeaponName));
    }
    return true;
  });

  const isRepeatingShot = weaponTagsRepeating || charHasRepeatingFeature;
  const hasExplicitAmmo = weapon.ammo_count !== undefined && weapon.ammo_count !== null;
  const canTrackAmmo = usesAmmunition || isThrown || hasExplicitAmmo;
  const suggestedMax = usesAmmunition ? 20 : 4;

  return { usesAmmunition, isThrown, isRepeatingShot, canTrackAmmo, suggestedMax };
}

/** PHB post-combat recovery: half of expended ammunition, rounded down (2014 p.7 & 2024 PHB). */
export function recoverExpendedAmmo(current: number, max: number): number {
  const safeCur = Math.max(0, Math.trunc(current));
  const safeMax = Math.max(safeCur, Math.trunc(max));
  const expended = Math.max(0, safeMax - safeCur);
  return Math.min(safeMax, safeCur + Math.floor(expended / 2));
}

export interface UtilityConsumableAction {
  kind: 'temp_hp' | 'buff' | 'charges';
  label: string;
  icon: string;
  toastTitle: string;
  effectNote: string;
  tempHp?: number;
  maxUses?: number;
}

export function classifyUtilityConsumable(
  item: EquipmentItem | null | undefined
): UtilityConsumableAction | null {
  if (!item) return null;
  const name = (item.name || '').toLowerCase().trim();
  if (!name) return null;
  if (name.includes('potion') && name.includes('healing')) {
    return null; // Handled by dedicated 1-tap Healing Potion drinkPotion() flow
  }

  if (name.includes('potion of heroism') || name.includes('heroism potion')) {
    return {
      kind: 'temp_hp',
      label: 'Drink',
      icon: '🛡️',
      toastTitle: '🛡️ POTION OF HEROISM',
      effectNote: 'Gained 10 Temporary HP (non-stacking) & Bless effect for 1 hour.',
      tempHp: 10,
    };
  }
  if (name.includes('potion of speed') || name.includes('speed potion')) {
    return {
      kind: 'buff',
      label: 'Drink',
      icon: '⚡',
      toastTitle: '⚡ POTION OF SPEED',
      effectNote: 'Gained Haste for 1 minute (no Concentration required).',
    };
  }
  if (name.includes('potion of invisibility')) {
    return {
      kind: 'buff',
      label: 'Drink',
      icon: '👁️',
      toastTitle: '👁️ POTION OF INVISIBILITY',
      effectNote: 'Invisible for 1 hour (ends if you attack or cast a spell).',
    };
  }
  if (name.includes('potion of flying')) {
    return {
      kind: 'buff',
      label: 'Drink',
      icon: '🪶',
      toastTitle: '🪶 POTION OF FLYING',
      effectNote: 'Gained Flying Speed equal to walking speed for 1 hour.',
    };
  }
  if (name.includes('antitoxin')) {
    return {
      kind: 'buff',
      label: 'Use',
      icon: '🧪',
      toastTitle: '🧪 ANTITOXIN',
      effectNote: 'Advantage on saving throws against poison for 1 hour.',
    };
  }
  if (name.includes("healer's kit") || name.includes('healers kit')) {
    return {
      kind: 'charges',
      label: 'Use',
      icon: '🩹',
      toastTitle: "🩹 HEALER'S KIT",
      effectNote: 'Stabilized a creature at 0 HP without a Medicine check.',
      maxUses: 10,
    };
  }
  return null;
}
