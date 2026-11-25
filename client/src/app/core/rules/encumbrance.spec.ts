import {
  catalogDefaultWeightLb,
  classifyUtilityConsumable,
  classifyWeaponAmmo,
  computeCarryingCapacity,
  computeCoinWeightLb,
  computeEncumbranceSummary,
  effectiveItemUnitWeightLb,
  parseWeightLb,
  recoverExpendedAmmo,
} from './encumbrance';

describe('encumbrance & ammo rules (#262)', () => {
  it('parses fractional and string D&D weights accurately', () => {
    expect(parseWeightLb(null)).toBeNull();
    expect(parseWeightLb('2 lb.')).toBe(2);
    expect(parseWeightLb('1.5 lbs')).toBe(1.5);
    expect(parseWeightLb('1/2 lb.')).toBe(0.5);
    expect(parseWeightLb('1 1/2 lb.')).toBe(1.5);
    expect(parseWeightLb('-5 lb.')).toBe(0);
    expect(parseWeightLb(0)).toBe(0);
  });

  it('resolves catalog weights matching items.json & weapons.json and respects 0.0 / stashed overrides', () => {
    expect(catalogDefaultWeightLb('Plate Armor')).toBe(65);
    expect(catalogDefaultWeightLb('Plate Armor +1')).toBe(65);
    expect(catalogDefaultWeightLb('Longbow')).toBe(2);
    expect(catalogDefaultWeightLb('Potion of Healing')).toBe(0.5);
    expect(effectiveItemUnitWeightLb({ name: 'Plate Armor', weight: 0 })).toBe(0);
    expect(effectiveItemUnitWeightLb({ name: 'Custom Relic', resolved_weight_lb: 4.5 })).toBe(4.5);
  });

  it.each(['2014 Edition', '2024 Revision (5.5e)'])(
    'computes carrying capacity, coins weight, Powerful Build & Bear Aspect (%s)',
    (edition) => {
      const char: any = {
        char_name: 'Karg',
        char_class: 'Barbarian',
        char_level: 6,
        dnd_edition: edition,
        race: 'Goliath',
        stats: { STR: 16, DEX: 14, CON: 14, INT: 10, WIS: 12, CHA: 8 },
        currency: { cp: 0, sp: 50, ep: 0, gp: 100, pp: 0 }, // 150 coins = 3 lb
        weapons: [{ name: 'Longbow', attack_bonus: '+5' }], // 2 lb
        equipment: [
          { name: 'Chain Mail', quantity: 1 }, // 55 lb
          { name: 'Loot Pile', weight: 100, quantity: 1, weight_ignored: true },
        ],
        features_traits: [
          { name: 'Powerful Build', description: 'You count as one size larger for carrying capacity.' },
          { name: 'Brawny', description: 'Count as one size larger for carrying capacity.' },
        ],
      };

      expect(computeCoinWeightLb(char.currency)).toBe(3);
      expect(computeCarryingCapacity(char).capacityLb).toBe(480); // 15 * 16 * 2 (Brawny + Powerful Build don't stack)

      const summary = computeEncumbranceSummary(char);
      expect(summary.totalWeightLb).toBe(60); // 55 + 2 + 3
      expect(summary.capacityLb).toBe(480);
      expect(summary.status).toBe('unencumbered');

      // Adding Aspect of the Beast (Bear) stacks x2 cleanly to 960 lb
      char.features_traits.push({
        name: 'Aspect of the Beast (Bear)',
        description: 'Your carrying capacity is doubled.',
      });
      expect(computeCarryingCapacity(char).capacityLb).toBe(960);
    }
  );

  it('classifies Ammunition, Thrown, and Repeating Shot weapons and recovers half ammo rounded down', () => {
    const longbow = { name: 'Longbow', attack_bonus: '+7', properties: 'Ammunition (150/600), Heavy' };
    const dagger = { name: 'Dagger', attack_bonus: '+5', properties: 'Finesse, Light, Thrown (20/60)' };
    const repeating = {
      name: 'Repeating Shot Light Crossbow',
      attack_bonus: '+7',
      properties: 'Ammunition (80/320), Two-Handed',
    };

    expect(classifyWeaponAmmo(longbow)).toEqual({
      usesAmmunition: true,
      isThrown: false,
      isRepeatingShot: false,
      canTrackAmmo: true,
      suggestedMax: 20,
    });
    expect(classifyWeaponAmmo(dagger).isThrown).toBe(true);
    expect(classifyWeaponAmmo(dagger).canTrackAmmo).toBe(true);
    expect(classifyWeaponAmmo(repeating).isRepeatingShot).toBe(true);

    // Repeating Shot feature scoped via "infused into Light Crossbow" matches +1 variant, not unrelated Heavy Crossbow
    const infusedChar: any = {
      features_traits: [
        {
          name: 'Infusion: Repeating Shot',
          description: 'Infused into Light Crossbow (can replace crossbow or longbow ammo).',
        },
      ],
    };
    expect(
      classifyWeaponAmmo({ name: 'Light Crossbow +1', attack_bonus: '+7', properties: 'Ammunition (80/320)' }, infusedChar)
        .isRepeatingShot
    ).toBe(true);
    expect(
      classifyWeaponAmmo({ name: 'Heavy Crossbow', attack_bonus: '+6', properties: 'Ammunition (100/400)' }, infusedChar)
        .isRepeatingShot
    ).toBe(false);

    // PHB half expended rounded down: 15/20 -> 5 expended -> recover 2 -> 17
    expect(recoverExpendedAmmo(15, 20)).toBe(17);
    expect(recoverExpendedAmmo(19, 20)).toBe(19);
  });

  it('classifies utility consumables separately from healing potions', () => {
    expect(classifyUtilityConsumable({ name: 'Potion of Healing' })).toBeNull();
    expect(classifyUtilityConsumable({ name: 'Potion of Heroism' })?.tempHp).toBe(10);
    expect(classifyUtilityConsumable({ name: "Healer's Kit" })?.maxUses).toBe(10);
    expect(classifyUtilityConsumable({ name: 'Antitoxin' })?.kind).toBe('buff');
  });
});
