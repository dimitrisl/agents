import {
  calculateWeaponBreakdown,
  extractMagicBonus,
  resolveWeaponStat,
  getArcheryBonus,
  getDuelingBonus,
} from './weapon-calc';
import { CharacterSchema, Weapon } from '../models/character.model';

describe('Weapon Bonus Calculations and Breakdown', () => {
  const uladBhor: CharacterSchema = {
    char_name: 'Ulad Bhor',
    char_class: 'Ranger',
    char_level: 9,
    proficiency_bonus: 4,
    stats: { STR: 18, DEX: 20, CON: 14, INT: 10, WIS: 14, CHA: 12 },
    features_traits: [
      { name: 'Fighting Style: Archery', description: '+2 bonus to attack rolls with ranged weapons' },
      { name: 'Planar Warrior', description: 'Bonus action force damage' },
    ],
  } as any;

  it('extracts magic bonus from name or field', () => {
    expect(extractMagicBonus({ name: 'Longbow +1', attack_bonus: '+9' })).toBe(1);
    expect(extractMagicBonus({ name: 'Dagger +2', attack_bonus: '+5' })).toBe(2);
    expect(extractMagicBonus({ name: 'Greatsword', attack_bonus: '+5', magic_bonus: 3 })).toBe(3);
    expect(extractMagicBonus({ name: 'Standard Mace', attack_bonus: '+4' })).toBe(0);
  });

  it('resolves correct stat modifier for ranged, finesse, and explicit weapons', () => {
    expect(resolveWeaponStat({ name: 'Longbow', attack_bonus: '+0' }, uladBhor)).toBe('DEX');
    expect(resolveWeaponStat({ name: 'Shortsword', attack_bonus: '+0', properties: 'finesse' }, uladBhor)).toBe('DEX');
    expect(resolveWeaponStat({ name: 'Greatsword', attack_bonus: '+0' }, uladBhor)).toBe('STR');
    expect(resolveWeaponStat({ name: 'Eldritch Blade', attack_bonus: '+0', ability_modifier: 'CHA' }, uladBhor)).toBe('CHA');
  });

  it('calculates full breakdown for Longbow +1 on Ulad Bhor with Archery style', () => {
    const longbow: Weapon = {
      name: 'Longbow +1',
      attack_bonus: '+9',
      damage_dice: '1d8 piercing',
      range: '150/600',
    };

    const breakdown = calculateWeaponBreakdown(longbow, uladBhor);

    // Attack breakdown: DEX (+5) + Prof (+4) + Magic (+1) + Archery (+2) = +12
    expect(breakdown.attack.statName).toBe('DEX');
    expect(breakdown.attack.statMod).toBe(5);
    expect(breakdown.attack.profBonus).toBe(4);
    expect(breakdown.attack.magicBonus).toBe(1);
    expect(breakdown.attack.fightingStyleBonus).toBe(2);
    expect(breakdown.attack.total).toBe(12);
    expect(breakdown.attack.formulaText).toBe('DEX (+5) + Prof (+4) + Magic (+1) + Archery (+2) = +12');

    // Damage breakdown: 1d8 + DEX (+5) + Magic (+1) = 1d8+6 piercing
    expect(breakdown.damage.dice).toBe('1d8');
    expect(breakdown.damage.statMod).toBe(5);
    expect(breakdown.damage.magicBonus).toBe(1);
    expect(breakdown.damage.totalBonus).toBe(6);
    expect(breakdown.damage.damageType).toBe('piercing');
    expect(breakdown.damage.notation).toBe('1d8+6');
    expect(breakdown.damage.formulaText).toBe('1d8 +5 (DEX) +1 (Magic) = 1d8+6 piercing');
  });

  it('handles custom misc attack and damage bonuses', () => {
    const customWeapon: Weapon = {
      name: 'Custom Dagger',
      attack_bonus: '+0',
      damage_dice: '1d4 piercing',
      properties: 'finesse',
      misc_attack_bonus: 1,
      misc_damage_bonus: 2,
    };

    const breakdown = calculateWeaponBreakdown(customWeapon, uladBhor);
    // DEX (+5) + Prof (+4) + Misc (+1) = +10
    expect(breakdown.attack.total).toBe(10);
    // 1d4 + 5 (DEX) + 2 (Misc) = 1d4+7
    expect(breakdown.damage.totalBonus).toBe(7);
  });
});
