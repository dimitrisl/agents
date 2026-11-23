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
    expect(resolveWeaponStat({ name: 'Rapier', attack_bonus: '+0', properties: ['Finesse'] as any }, uladBhor)).toBe('DEX');
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

  it('non-destructively suppresses magic_bonus and global gear bonuses under Athas, and applies DM/exhaustion offsets', () => {
    const athasHero: CharacterSchema = {
      ...uladBhor,
      dnd_edition: '2024 Revision (5.5e)',
      magic_items_suppressed: true,
      global_attack_bonus: 2,
      global_damage_bonus: 1,
      exhaustion_level: 1, // -2 in 2024
      dm_modifiers: {
        attack_bonus: -1,
        damage_bonus: 3,
      },
    };
    const longbow: Weapon = {
      name: 'Longbow +1',
      attack_bonus: '+12',
      damage_dice: '1d8 piercing',
      magic_bonus: 1,
    };

    const suppressed = calculateWeaponBreakdown(longbow, athasHero);
    // Atk: DEX (+5) + Prof (+4) + Magic (0, suppressed!) + Archery (+2) + Global (0) + DM (-1) - Exh (2) = +8
    expect(suppressed.attack.magicBonus).toBe(0);
    expect(suppressed.attack.total).toBe(8);
    expect(suppressed.attack.formulaText).toContain('Magic Suppressed');
    expect(suppressed.attack.formulaText).toContain('DM (-1)');
    expect(suppressed.attack.formulaText).toContain('Exh (-2)');
    // Dmg: 1d8 + DEX (+5) + Magic (0) + DM (+3) = 1d8+8
    expect(suppressed.damage.magicBonus).toBe(0);
    expect(suppressed.damage.totalBonus).toBe(8);

    // Lifting suppression restores full +1 magic + global bonuses cleanly
    const restored = calculateWeaponBreakdown(longbow, { ...athasHero, magic_items_suppressed: false });
    expect(restored.attack.magicBonus).toBe(1);
    expect(restored.attack.total).toBe(11); // +5 + 4 + 1 + 2 + 2 - 1 - 2 = 11
    expect(restored.damage.totalBonus).toBe(10); // 5 + 1 + 1 + 3 = 10
  });

  it('adds Agonizing Blast +CHA damage on Eldritch Blast without double-counting explicit CHA modifier', () => {
    const warlock: CharacterSchema = {
      char_name: 'Morthos',
      char_class: 'Warlock',
      char_level: 5,
      proficiency_bonus: 3,
      stats: { STR: 8, DEX: 14, CON: 14, INT: 10, WIS: 12, CHA: 18 },
      features_traits: [{ name: 'Agonizing Blast', description: 'Add CHA mod to Eldritch Blast damage.' }],
    } as any;

    const ebNoStat: Weapon = {
      name: 'Eldritch Blast',
      attack_bonus: '+7',
      damage_dice: '1d10 force',
      ability_modifier: 'NONE',
      range: '120 ft.',
    };
    const breakdownNone = calculateWeaponBreakdown(ebNoStat, warlock);
    expect(breakdownNone.damage.totalBonus).toBe(4);
    expect(breakdownNone.damage.formulaText).toContain('+4 (Agonizing)');

    const ebExplicitCha: Weapon = { ...ebNoStat, ability_modifier: 'CHA' };
    const breakdownCha = calculateWeaponBreakdown(ebExplicitCha, warlock);
    expect(breakdownCha.damage.totalBonus).toBe(4);
    expect(breakdownCha.damage.formulaText).not.toContain('(Agonizing)');
  });

  it('adds +2 bow damage for Bracers of Archery on Longbow/Shortbow only and suppresses under Athas', () => {
    const archer: CharacterSchema = {
      ...uladBhor,
      equipment: [{ name: 'Bracers of Archery', equipped: true, attuned: true } as any],
    };
    const longbow: Weapon = {
      name: 'Longbow',
      attack_bonus: '+9',
      damage_dice: '1d8 piercing',
      range: '150/600',
    };
    const longsword: Weapon = {
      name: 'Longsword',
      attack_bonus: '+8',
      damage_dice: '1d8 slashing',
    };

    const bowBd = calculateWeaponBreakdown(longbow, archer);
    expect(bowBd.damage.totalBonus).toBe(7); // 5 DEX + 2 Bracers
    expect(bowBd.damage.formulaText).toContain('+2 (Bracers of Archery)');

    const swordBd = calculateWeaponBreakdown(longsword, archer);
    expect(swordBd.damage.totalBonus).toBe(4); // 4 STR only (Bracers do not apply to melee weapons)
    expect(swordBd.damage.formulaText).not.toContain('Bracers of Archery');

    const suppBd = calculateWeaponBreakdown(longbow, { ...archer, magic_items_suppressed: true });
    expect(suppBd.damage.totalBonus).toBe(5);
    expect(suppBd.damage.formulaText).not.toContain('Bracers of Archery');
  });
});
