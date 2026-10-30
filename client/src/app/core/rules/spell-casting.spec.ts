import { analyzeSpell, cantripDiceMultiplier, diceForCast } from './index';

// Excerpts of the real texts in data/rules/spells_2014.json (OCR slips included).
const FIREBALL = {
  name: 'Fireball',
  level: '3',
  duration: 'Instantaneous',
  description:
    'Each creature in a 20-foot-radius sphere centered on that point must make a Dexterity saving throw. ' +
    'A target takes 8d6 fire damage on a failed save, or half as much damage on a successful one.',
  higherLevelSlot:
    'When you cast this spell using a spell slot of 4th level or higher, the damage increases by 1d6 for each slot level above 3rd.',
};
const SHATTER = {
  name: 'Shatter',
  level: '2',
  duration: 'Instantaneous',
  description:
    'Each creature in a lO-foot-radius sphere centered on that point must make a Constitution saving throw. ' +
    'A creature takes 3d8 thunder damage on a failed save, or half as much damage on a successful one.',
  higherLevelSlot:
    'When you cast this spell using a spell slot of 3rd levei or higher, the damage increases by ld8 for each slot level above 2nd.',
};
const FIRE_BOLT = {
  name: 'Fire Bolt',
  level: '0',
  duration: 'Instantaneous',
  description: 'Make a ranged spell attack against the target. On a hit, the target takes 1d10 fire damage.',
  higherLevelSlot: 'None',
};
const MAGIC_MISSILE = {
  name: 'Magic Missile',
  level: '1',
  duration: 'Instantaneous',
  description:
    'You create three glowing darts of magical force. Each dart hits a creature of your choice. A dart deals 1d4 + 1 force damage to its target.',
  higherLevelSlot:
    'When you cast this spell using a spell slot of 2nd level or higher, the spell creates one more dart for each slot level above 1st.',
};
const CURE_WOUNDS = {
  name: 'Cure Wounds',
  level: '1',
  duration: 'Instantaneous',
  description: 'A creature you touch regains a number of hit points equal to 1d8 + your spellcasting ability modifier.',
  higherLevelSlot:
    'When you cast this spell using a spell slot of 2nd level or higher, the healing increases by 1d8 for each slot level above 1st.',
};
const FIRE_SHIELD = {
  name: 'Fire Shield',
  level: '4',
  duration: '10 minutes',
  description:
    'Thin and wispy flames wreathe your body for the duration. Whenever a creature within 5 feet of you hits you with a melee attack, the shield erupts with flame. The attacker takes 2d8 fire damage from a warm shield.',
  higherLevelSlot: 'None',
};
const SACRED_FLAME = {
  name: 'Sacred Flame',
  level: '0',
  duration: 'Instantaneous',
  description: 'The target must succeed on a Dexterity saving throw or take 1d8 radiant damage.',
  higherLevelSlot: 'None',
};

describe('spell casting rolls', () => {
  it('reads Fireball: 8d6 fire, DEX save for half, +1d6 per slot level', () => {
    const fireball = analyzeSpell(FIREBALL);
    expect(fireball).toMatchObject({
      dice: '8d6',
      damageType: 'fire',
      save: { ability: 'DEX', halfOnSuccess: true },
      perSlotLevel: '1d6',
      spellAttack: false,
      rollsOnCast: true,
    });
    expect(diceForCast(fireball, 3, 8)).toBe('8d6');
    expect(diceForCast(fireball, 4, 8)).toBe('9d6');
    expect(diceForCast(fireball, 5, 8)).toBe('10d6');
  });

  it('copes with the OCR slips in the texts ("ld8", "lO-foot")', () => {
    const shatter = analyzeSpell(SHATTER);
    expect(shatter.save).toEqual({ ability: 'CON', halfOnSuccess: true });
    expect(diceForCast(shatter, 4, 8)).toBe('5d8');
  });

  it('scales damage cantrips with character level', () => {
    const bolt = analyzeSpell(FIRE_BOLT);
    expect(bolt.spellAttack).toBe(true);
    expect([1, 5, 11, 17].map((lvl) => diceForCast(bolt, 0, lvl))).toEqual(['1d10', '2d10', '3d10', '4d10']);
    expect(cantripDiceMultiplier(4)).toBe(1);
  });

  it('counts Magic Missile darts, including one more per upcast level', () => {
    const missile = analyzeSpell(MAGIC_MISSILE);
    expect(diceForCast(missile, 1, 8)).toBe('3d4+3');
    expect(diceForCast(missile, 2, 8)).toBe('4d4+4');
  });

  it('treats Cure Wounds as healing that adds the spellcasting modifier', () => {
    const cure = analyzeSpell(CURE_WOUNDS);
    expect(cure.healing).toBe(true);
    expect(cure.addsAbilityModifier).toBe(true);
    expect(cure.damageType).toBeNull();
    expect(diceForCast(cure, 3, 8)).toBe('3d8');
  });

  it('does not roll damage that only happens later (Fire Shield retaliation)', () => {
    expect(analyzeSpell(FIRE_SHIELD).rollsOnCast).toBe(false);
  });

  it('knows concentration from the data shape of either edition', () => {
    expect(analyzeSpell({ ...FIREBALL, concentration: 'False' }).concentration).toBe(false);
    expect(analyzeSpell({ name: 'Haste', level: 3, concentration: 'True' }).concentration).toBe(true); // 2014
    expect(analyzeSpell({ name: 'Haste', level: 3, concentration: true }).concentration).toBe(true); // 2024
    expect(analyzeSpell({ name: 'Bless', level: 1, duration: 'Concentration, up to 1 minute' }).concentration).toBe(true);
  });

  it('reads "must succeed on" saves; Sacred Flame has no half damage', () => {
    expect(analyzeSpell(SACRED_FLAME).save).toEqual({ ability: 'DEX', halfOnSuccess: false });
  });
});
