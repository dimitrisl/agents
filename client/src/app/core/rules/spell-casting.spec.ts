import {
  analyzeSpell,
  cantripDiceMultiplier,
  canCastAsRitual,
  diceForCast,
  isAlwaysPreparedSpell,
  isRitualSpell,
  maxPreparedSpells,
  preparedSpellsCount,
  RITUAL_SPELLS_2014,
  RITUAL_SPELLS_2024,
} from './index';
import { CharacterSchema } from '../models/character.model';

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

describe('prepared caps, always-prepared split, and 2014 vs 2024 ritual casting (#261)', () => {
  function caster(overrides: Partial<CharacterSchema> = {}): CharacterSchema {
    return {
      char_id: 'c1',
      char_name: 'Lyra',
      char_class: 'Wizard',
      char_level: 5,
      race: 'Human',
      background: 'Sage',
      armor_class: 12,
      hp_max: 30,
      speed: 30,
      proficiency_bonus: 3,
      dnd_edition: '2014 Edition',
      stats: { STR: 8, DEX: 14, CON: 14, INT: 18, WIS: 16, CHA: 14 },
      spells: {
        cantrips: ['Fire Bolt'],
        level_1: ['Detect Magic', 'Mage Armor', 'Bless'],
        level_2: ['Hold Person'],
      },
      prepared_spells: ['Mage Armor'],
      always_prepared_spells: [],
      ...overrides,
    };
  }

  it('tracks ritual tag in analyzeSpell and canonical 2014/2024 ritual sets', () => {
    expect(analyzeSpell({ name: 'Detect Magic', level: 1, ritual: 'True' }).ritual).toBe(true);
    expect(analyzeSpell({ name: 'Detect Magic', level: 1, ritual: true }).ritual).toBe(true);
    expect(analyzeSpell({ name: 'Hold Person', level: 2, ritual: false }).ritual).toBe(false);

    expect(RITUAL_SPELLS_2014.has('purify food and drink')).toBe(true);
    expect(RITUAL_SPELLS_2024.has('purify food and drink')).toBe(true);
    expect(RITUAL_SPELLS_2014.has('hold person')).toBe(false);
    expect(RITUAL_SPELLS_2024.has('hold person')).toBe(false);
    expect(isRitualSpell('Purify Food and Drink', '2014 Edition')).toBe(true);
    expect(isRitualSpell('Hold Person', '2024 Revision (5.5e)')).toBe(false);
  });

  it('computes prepared spell caps across 2014, 2024, and multiclass builds', () => {
    expect(maxPreparedSpells(caster({ char_class: 'Wizard', char_level: 5 }))).toBe(9);
    expect(maxPreparedSpells(caster({ char_class: 'Cleric', char_level: 5 }))).toBe(8);
    expect(maxPreparedSpells(caster({ char_class: 'Paladin', char_level: 1 }))).toBeNull();
    expect(maxPreparedSpells(caster({ char_class: 'Sorcerer', char_level: 5 }))).toBeNull();

    expect(
      maxPreparedSpells(caster({ char_class: 'Bard', char_level: 5, dnd_edition: '2024 Revision (5.5e)' }))
    ).toBe(9);
    expect(
      maxPreparedSpells(
        caster({ char_class: 'Paladin', char_level: 1, dnd_edition: '2024 Revision (5.5e)' })
      )
    ).toBe(2);
    expect(
      maxPreparedSpells(
        caster({
          char_class: 'Fighter',
          subclass: 'Eldritch Knight',
          char_level: 3,
          dnd_edition: '2024 Revision (5.5e)',
        })
      )
    ).toBe(3);
  });

  it('excludes cantrips and always_prepared_spells from preparedSpellsCount', () => {
    const c = caster({
      prepared_spells: ['Fire Bolt', 'Mage Armor', 'Bless', 'Mage Armor'],
      always_prepared_spells: ['Bless'],
    });
    expect(isAlwaysPreparedSpell(c, 'bless')).toBe(true);
    expect(preparedSpellsCount(c)).toBe(1);
  });

  it('enforces 2014 vs 2024 Ritual Casting eligibility rules', () => {
    // 2014 Wizard can cast unprepared Detect Magic directly from spellbook
    expect(canCastAsRitual(caster({ char_class: 'Wizard', dnd_edition: '2014 Edition' }), 'Detect Magic')).toBe(
      true
    );
    expect(canCastAsRitual(caster({ char_class: 'Wizard', dnd_edition: '2014 Edition' }), 'Hold Person')).toBe(
      false
    );

    // 2014 Cleric must have it prepared (or always prepared)
    expect(
      canCastAsRitual(
        caster({ char_class: 'Cleric', dnd_edition: '2014 Edition', prepared_spells: [] }),
        'Detect Magic'
      )
    ).toBe(false);
    expect(
      canCastAsRitual(
        caster({
          char_class: 'Cleric',
          dnd_edition: '2014 Edition',
          prepared_spells: ['Detect Magic'],
        }),
        'Detect Magic'
      )
    ).toBe(true);

    // 2014 Bard can ritual cast known spells; 2014 Sorcerer needs Ritual Caster feat
    expect(
      canCastAsRitual(
        caster({ char_class: 'Bard', dnd_edition: '2014 Edition', prepared_spells: [] }),
        'Detect Magic'
      )
    ).toBe(true);
    expect(
      canCastAsRitual(
        caster({ char_class: 'Sorcerer', dnd_edition: '2014 Edition', prepared_spells: ['Detect Magic'] }),
        'Detect Magic'
      )
    ).toBe(false);
    expect(
      canCastAsRitual(
        caster({
          char_class: 'Sorcerer',
          dnd_edition: '2014 Edition',
          features_traits: [{ name: 'Ritual Caster', description: 'Can cast rituals' }],
        }),
        'Detect Magic'
      )
    ).toBe(true);

    // 2024 Revision: any caster with a prepared ritual spell can ritual cast it; Wizard also casts from book
    expect(
      canCastAsRitual(
        caster({
          char_class: 'Sorcerer',
          dnd_edition: '2024 Revision (5.5e)',
          prepared_spells: ['Detect Magic'],
        }),
        'Detect Magic'
      )
    ).toBe(true);
    expect(
      canCastAsRitual(
        caster({
          char_class: 'Sorcerer',
          dnd_edition: '2024 Revision (5.5e)',
          prepared_spells: [],
        }),
        'Detect Magic'
      )
    ).toBe(false);
    expect(
      canCastAsRitual(
        caster({
          char_class: 'Wizard',
          dnd_edition: '2024 Revision (5.5e)',
          prepared_spells: [],
        }),
        'Detect Magic'
      )
    ).toBe(true);
  });

  it('falls back cleanly when max_prepared_spells is null (pre-#261 DB docs), supports PHB aliases, and guards Ritual Casting trait name', () => {
    // Pre-#261 MongoDB document with max_prepared_spells: null
    expect(
      maxPreparedSpells(
        caster({
          char_class: 'Wizard',
          char_level: 5,
          max_prepared_spells: null,
        })
      )
    ).toBe(9);

    // Eponymous PHB alias support
    expect(isRitualSpell("Leomund's Tiny Hut", '2014 Edition')).toBe(true);
    expect(
      canCastAsRitual(
        caster({
          char_class: 'Wizard',
          spells: { level_3: ["Leomund's Tiny Hut"] },
          prepared_spells: [],
        }),
        "Leomund's Tiny Hut"
      )
    ).toBe(true);

    // Generic 2014 Cleric "Ritual Casting" sub-trait must NOT bypass preparation requirement
    expect(
      canCastAsRitual(
        caster({
          char_class: 'Cleric',
          dnd_edition: '2014 Edition',
          prepared_spells: [],
          features_traits: [{ name: 'Ritual Casting', description: 'You can cast prepared cleric spells as rituals.' }],
        }),
        'Detect Magic'
      )
    ).toBe(false);

    // 2024 Pact of the Tome grants ritual book casting
    expect(
      canCastAsRitual(
        caster({
          char_class: 'Warlock',
          dnd_edition: '2024 Revision (5.5e)',
          prepared_spells: [],
          features_traits: [{ name: 'Pact of the Tome', description: 'Book of Shadows rituals' }],
        }),
        'Detect Magic'
      )
    ).toBe(true);
  });
});
