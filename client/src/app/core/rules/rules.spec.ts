import { CharacterSchema } from '../models/character.model';
import {
  ALL_SKILLS,
  SkillDefinition,
  abilityModifier,
  abilityModifierOf,
  abilityScore,
  adjustedHp,
  availableHitDice,
  clampHp,
  conModifier,
  currentHp,
  findSkill,
  formatModifier,
  hasSpellSlotLevel,
  hitDieSize,
  isProficientIn,
  isSaveProficient,
  levelUp,
  planShortRest,
  proficiencyBonus,
  proficiencyBonusForLevel,
  regainSpellSlot,
  resolveLongRest,
  resolveShortRest,
  restoreAllSpellSlots,
  savingThrowModifier,
  skillModifier,
  skillModifierString,
  spellSlotKey,
  spellSlotMax,
  spellSlotUsed,
  spendSpellSlot,
} from './index';

/**
 * #44: this arithmetic used to live inside a 1400-line component, where reaching
 * it meant standing up an HttpClient, a Router, a WebSocket and three services to
 * ask what a +3 was. It is the one part of the sheet where a wrong answer is
 * visible to the player, so it is now plain functions and these are plain tests.
 *
 * The extraction itself was behaviour-preserving. The four rules bugs it exposed
 * are then fixed on top, and each fix says here what the old answer was.
 */
function hero(overrides: Partial<CharacterSchema> = {}): CharacterSchema {
  return {
    char_id: 'lyra1',
    char_name: 'Lyra Meadowlark',
    char_class: 'Ranger',
    char_level: 5,
    race: 'Half-Elf',
    background: 'Outlander',
    armor_class: 15,
    hp_max: 44,
    speed: 30,
    proficiency_bonus: 3,
    stats: { STR: 10, DEX: 18, CON: 14, INT: 12, WIS: 16, CHA: 8 },
    saving_throws: ['DEX'],
    skill_proficiencies: ['Perception'],
    ...overrides,
  };
}

const skill = (name: string, ability: SkillDefinition['ability']): SkillDefinition => ({
  name,
  ability,
});

// --------------------------------------------------------------------------- //

describe('ability rules', () => {
  describe('abilityModifier', () => {
    it.each([
      [1, -5],
      [3, -4],
      [8, -1],
      [9, -1],
      [10, 0],
      [11, 0],
      [16, 3],
      [20, 5],
      [30, 10],
    ])('score %i is a %i modifier', (score, expected) => {
      expect(abilityModifier(score)).toBe(expected);
    });

    it('rounds a negative modifier down, not toward zero', () => {
      // The trap in this formula: -1.5 is a -2, never a -1.
      expect(abilityModifier(7)).toBe(-2);
    });
  });

  describe('formatModifier', () => {
    it.each([
      [3, '+3'],
      [-1, '-1'],
      [0, '+0'],
    ])('shows %i as %s', (value, expected) => {
      expect(formatModifier(value)).toBe(expected);
    });
  });

  describe('abilityScore', () => {
    it('reads the score off the sheet', () => {
      expect(abilityScore(hero(), 'DEX')).toBe(18);
    });

    it('treats an unwritten line, and no sheet at all, as a 10', () => {
      expect(abilityScore(hero(), 'LUCK')).toBe(10);
      expect(abilityScore(null, 'DEX')).toBe(10);
      expect(abilityModifierOf(null, 'DEX')).toBe(0);
    });
  });

  describe('proficiencyBonus', () => {
    it('uses the sheet value', () => {
      expect(proficiencyBonus(hero({ proficiency_bonus: 4 }))).toBe(4);
    });

    it('falls back to +2 when the sheet does not say', () => {
      const unwritten = hero();
      delete (unwritten as Partial<CharacterSchema>).proficiency_bonus;

      expect(proficiencyBonus(unwritten)).toBe(2);
      expect(proficiencyBonus(hero({ proficiency_bonus: 0 }))).toBe(2);
      expect(proficiencyBonus(null)).toBe(2);
    });
  });

  describe('proficiencyBonusForLevel', () => {
    it.each([
      [1, 2],
      [4, 2],
      [5, 3],
      [8, 3],
      [9, 4],
      [12, 4],
      [13, 5],
      [16, 5],
      [17, 6],
      [20, 6],
    ])('level %i is a +%i', (level, expected) => {
      expect(proficiencyBonusForLevel(level)).toBe(expected);
    });

    it('treats a levelless sheet as level 1 rather than going below +2', () => {
      expect(proficiencyBonusForLevel(0)).toBe(2);
      expect(proficiencyBonusForLevel(-3)).toBe(2);
    });
  });

  describe('savingThrowModifier', () => {
    it('adds proficiency to a trained save', () => {
      // DEX 18 (+4), proficient (+3).
      expect(isSaveProficient(hero(), 'DEX')).toBe(true);
      expect(savingThrowModifier(hero(), 'DEX')).toBe(7);
    });

    it('leaves an untrained save on the bare ability modifier', () => {
      // CHA 8 (-1), not proficient.
      expect(isSaveProficient(hero(), 'CHA')).toBe(false);
      expect(savingThrowModifier(hero(), 'CHA')).toBe(-1);
    });

    it('treats a sheet with no save list as proficient in nothing', () => {
      const untrained = hero({ saving_throws: undefined });
      expect(isSaveProficient(untrained, 'DEX')).toBe(false);
      expect(savingThrowModifier(untrained, 'DEX')).toBe(4);
    });
  });
});

// --------------------------------------------------------------------------- //

describe('skill rules', () => {
  it('lists the eighteen skills of the sheet', () => {
    expect(ALL_SKILLS).toHaveLength(18);
    expect(ALL_SKILLS.map((s) => s.name)).toContain('Sleight of Hand');
  });

  describe('isProficientIn', () => {
    it('matches the name exactly, and says no for everything else', () => {
      expect(isProficientIn(hero(), 'Perception')).toBe(true);
      expect(isProficientIn(hero(), 'Stealth')).toBe(false);
      expect(isProficientIn(hero(), 'perception')).toBe(false);
      expect(isProficientIn(hero({ skill_proficiencies: undefined }), 'Perception')).toBe(false);
      expect(isProficientIn(null, 'Perception')).toBe(false);
    });
  });

  describe('skillModifier', () => {
    it('adds the proficiency bonus to a trained skill', () => {
      // WIS 16 (+3) + proficiency (+3).
      expect(skillModifier(hero(), skill('Perception', 'WIS'))).toBe(6);
    });

    it('leaves an untrained skill on the ability modifier alone', () => {
      // WIS 16 (+3), no proficiency.
      expect(skillModifier(hero(), skill('Insight', 'WIS'))).toBe(3);
    });

    it('carries a negative ability modifier through', () => {
      // CHA 8 (-1), untrained.
      expect(skillModifier(hero(), skill('Deception', 'CHA'))).toBe(-1);
      // And proficiency can still pull it back above zero: -1 +3.
      expect(
        skillModifier(hero({ skill_proficiencies: ['Deception'] }), skill('Deception', 'CHA'))
      ).toBe(2);
    });

    it('falls back to a +2 proficiency bonus when the sheet omits one', () => {
      const unwritten = hero();
      delete (unwritten as Partial<CharacterSchema>).proficiency_bonus;

      // WIS 16 (+3) + the assumed +2.
      expect(skillModifier(unwritten, skill('Perception', 'WIS'))).toBe(5);
    });

    it('scores an unknown ability off a 10', () => {
      const unknown = { name: 'Thaumaturgy', ability: 'LCK' } as unknown as SkillDefinition;
      expect(skillModifier(hero(), unknown)).toBe(0);
    });

    it('scores 0 flat when there is no sheet, or no stat block on it', () => {
      // Pinned: the old component bailed before it read the proficiency list, so a
      // statless sheet shows nothing rather than a lone +3 beside a blank ability.
      const statless = hero({ skill_proficiencies: ['Perception'] });
      delete (statless as Partial<CharacterSchema>).stats;

      expect(skillModifier(statless, skill('Perception', 'WIS'))).toBe(0);
      expect(skillModifier(null, skill('Perception', 'WIS'))).toBe(0);
    });
  });

  describe('skillModifierString', () => {
    it.each<[string, SkillDefinition['ability'], string]>([
      ['Insight', 'WIS', '+3'],
      ['Deception', 'CHA', '-1'],
      ['Athletics', 'STR', '+0'],
    ])('formats %s as %s', (name, ability, expected) => {
      expect(skillModifierString(hero(), skill(name, ability))).toBe(expected);
    });
  });

  describe('findSkill', () => {
    it('ignores the case the DM typed', () => {
      expect(findSkill(ALL_SKILLS, 'sleight of hand')?.name).toBe('Sleight of Hand');
      expect(findSkill(ALL_SKILLS, 'PERCEPTION')?.name).toBe('Perception');
    });

    it('returns nothing for a name that is not a skill', () => {
      expect(findSkill(ALL_SKILLS, 'DEX')).toBeUndefined();
    });
  });
});

// --------------------------------------------------------------------------- //

describe('hit dice', () => {
  /**
   * There used to be two class → die lookups that disagreed: the player sheet
   * matched substrings, the class-combat table matched exactly. A wizard whose
   * sheet said `1d10` was shown "1d10+2" by the action dock and then handed a d6
   * by the short rest. This is now the only lookup.
   */
  describe('hitDieSize', () => {
    it.each([
      ['Barbarian', 12],
      ['Fighter', 10],
      ['Paladin', 10],
      ['Ranger', 10],
      ['Sorcerer', 6],
      ['Wizard', 6],
      ['Rogue', 8],
      ['Warlock', 8],
      ['Artificer', 8],
    ])('gives a %s a d%i', (char_class, expected) => {
      expect(hitDieSize({ char_class })).toBe(expected);
    });

    it('lets the sheet outrank the class table', () => {
      expect(hitDieSize({ char_class: 'Wizard', hit_dice: '5d10' })).toBe(10);
      expect(hitDieSize({ char_class: 'Wizard', hit_dice: 'd12' })).toBe(12);
    });

    it('falls back to the class table when the string is malformed or missing', () => {
      expect(hitDieSize({ char_class: 'Barbarian', hit_dice: 'five' })).toBe(12);
      expect(hitDieSize({ char_class: 'Barbarian', hit_dice: '3' })).toBe(12);
      expect(hitDieSize({ char_class: 'Barbarian', hit_dice: '' })).toBe(12);
      expect(hitDieSize({ char_class: 'Barbarian' })).toBe(12);
    });

    it('finds the class inside a free-text subclass string', () => {
      // `char_class` is a free-text field; this is what heroes actually hold.
      expect(hitDieSize({ char_class: 'Eldritch Knight Fighter' })).toBe(10);
      expect(hitDieSize({ char_class: 'Barbarian (Totem Warrior)' })).toBe(12);
      expect(hitDieSize({ char_class: 'Arcane Trickster Rogue' })).toBe(8);
    });

    it('resolves a multiclass string to the first class in table order', () => {
      expect(hitDieSize({ char_class: 'Fighter/Wizard' })).toBe(10);
    });

    it('falls back to a d8 for no class at all, or one it does not know', () => {
      expect(hitDieSize({ char_class: '' })).toBe(8);
      expect(hitDieSize({ char_class: 'Blood Hunter' })).toBe(8);
      expect(hitDieSize(null)).toBe(8);
    });
  });

  describe('availableHitDice', () => {
    it('is the level minus what has been spent', () => {
      expect(availableHitDice(hero({ char_level: 5, hit_dice_used: 2 }))).toBe(3);
      expect(availableHitDice(hero({ char_level: 5 }))).toBe(5);
    });

    it('never goes negative, however many the sheet claims were spent', () => {
      expect(availableHitDice(hero({ char_level: 5, hit_dice_used: 9 }))).toBe(0);
      expect(availableHitDice(hero({ char_level: 0, hit_dice_used: 0 }))).toBe(1);
      expect(availableHitDice(null)).toBe(0);
    });
  });

  describe('conModifier', () => {
    it('is the CON ability modifier', () => {
      expect(conModifier(hero())).toBe(2);
      expect(conModifier(hero({ stats: { ...hero().stats, CON: 6 } }))).toBe(-2);
    });
  });
});

// --------------------------------------------------------------------------- //

describe('short rest', () => {
  describe('planShortRest', () => {
    it('spends what was asked for when the dice are there', () => {
      const plan = planShortRest(hero({ char_level: 5, hit_dice_used: 0 }), 3);

      expect(plan).toEqual({ diceSpent: 3, dieSize: 10, conModifier: 2, conBonus: 6 });
    });

    it('refuses to spend more hit dice than are left', () => {
      // Level 3, two already spent: one die remains, whatever the stepper says.
      const plan = planShortRest(hero({ char_level: 3, hit_dice_used: 2 }), 5);

      expect(plan?.diceSpent).toBe(1);
    });

    it('always spends at least one die', () => {
      expect(planShortRest(hero(), 0)?.diceSpent).toBe(1);
      expect(planShortRest(hero(), -4)?.diceSpent).toBe(1);
    });

    it('returns nothing at all when there are no dice to spend', () => {
      expect(planShortRest(hero({ char_level: 3, hit_dice_used: 3 }), 1)).toBeNull();
      expect(planShortRest(null, 1)).toBeNull();
    });

    it('applies CON once per die spent', () => {
      const tough = hero({ char_level: 5, hit_dice_used: 0, stats: { ...hero().stats, CON: 18 } });

      expect(planShortRest(tough, 3)?.conBonus).toBe(12);
    });
  });

  describe('resolveShortRest', () => {
    const plan = { diceSpent: 2, dieSize: 10, conModifier: 2, conBonus: 4 };

    it('heals by the rolled total and books the dice as spent', () => {
      const char = hero({ hp_max: 44, hp_current: 20, hit_dice_used: 1 });
      const rest = resolveShortRest(char, plan, 15);

      expect(rest).toEqual({
        rolled: 15,
        hpGained: 15,
        hpBefore: 20,
        hpAfter: 35,
        hitDiceUsed: 3,
        restoresPactSlots: false,
      });
    });

    it('never heals past the maximum', () => {
      const char = hero({ hp_max: 44, hp_current: 40 });

      expect(resolveShortRest(char, plan, 20).hpAfter).toBe(44);
    });

    it('starts from full HP when the sheet never wrote a current value', () => {
      const char = hero({ hp_max: 44, hp_current: undefined });
      const rest = resolveShortRest(char, plan, 8);

      expect(rest.hpBefore).toBe(44);
      expect(rest.hpAfter).toBe(44);
    });

    it('cannot make a hit die deal damage', () => {
      // 1 on a d6 with CON -2 is a total of -1. A rest is never a wound.
      const frail = hero({ hp_max: 20, hp_current: 10, stats: { ...hero().stats, CON: 6 } });
      const rest = resolveShortRest(frail, { ...plan, conModifier: -2, conBonus: -4 }, -1);

      expect(rest.rolled).toBe(0);
      expect(rest.hpGained).toBe(0);
      expect(rest.hpAfter).toBe(10);
    });

    it('gives a warlock their pact slots back, and nobody else theirs', () => {
      expect(resolveShortRest(hero({ char_class: 'Warlock' }), plan, 5).restoresPactSlots).toBe(
        true
      );
      expect(
        resolveShortRest(hero({ char_class: 'Hexblade Warlock' }), plan, 5).restoresPactSlots
      ).toBe(true);
      expect(resolveShortRest(hero({ char_class: 'Ranger' }), plan, 5).restoresPactSlots).toBe(
        false
      );
      expect(resolveShortRest(hero({ char_class: '' }), plan, 5).restoresPactSlots).toBe(false);
    });

    /**
     * The sheet used to report the rolled total as HP healed: at 40/44 a rolled
     * 20 announced "Healed for +20 HP! (40 ➡️ 44)", which is four points of
     * healing described as twenty. The two numbers are separate now — the roll
     * display shows `rolled`, the message shows `hpGained`.
     */
    it('separates what was rolled from what the hero actually got', () => {
      const rest = resolveShortRest(hero({ hp_max: 44, hp_current: 40 }), plan, 20);

      expect(rest.rolled).toBe(20);
      expect(rest.hpGained).toBe(4);
      expect(rest.hpAfter - rest.hpBefore).toBe(rest.hpGained);
    });

    it('gains nothing at full health', () => {
      const rest = resolveShortRest(hero({ hp_max: 44, hp_current: 44 }), plan, 12);

      expect(rest.rolled).toBe(12);
      expect(rest.hpGained).toBe(0);
    });
  });
});

// --------------------------------------------------------------------------- //

describe('long rest', () => {
  it('restores full HP', () => {
    expect(resolveLongRest(hero({ hp_max: 44, hp_current: 3 })).hpCurrent).toBe(44);
  });

  it('gives back half the hero total hit dice', () => {
    const rest = resolveLongRest(hero({ char_level: 5, hit_dice_used: 5 }));

    expect(rest.hitDiceRecovered).toBe(2);
    expect(rest.hitDiceUsed).toBe(3);
  });

  it('gives a level 1 hero their single die back rather than nothing', () => {
    // floor(1 / 2) is 0, which would make a long rest worthless at level 1.
    const rest = resolveLongRest(hero({ char_level: 1, hit_dice_used: 1 }));

    expect(rest.hitDiceRecovered).toBe(1);
    expect(rest.hitDiceUsed).toBe(0);
  });

  it('cannot push the spent count below zero', () => {
    const rest = resolveLongRest(hero({ char_level: 9, hit_dice_used: 1 }));

    expect(rest.hitDiceRecovered).toBe(4);
    expect(rest.hitDiceUsed).toBe(0);
  });

  it('treats a sheet with no level as level 1', () => {
    expect(resolveLongRest(hero({ char_level: 0, hit_dice_used: 0 })).hitDiceRecovered).toBe(1);
  });

  it('restores every spell slot', () => {
    const slots = { level_1: { max: 4, used: 4 }, level_2: { max: 3, used: 1 } };

    expect(restoreAllSpellSlots(slots)).toEqual({
      level_1: { max: 4, used: 0 },
      level_2: { max: 3, used: 0 },
    });
  });

  it('has nothing to restore for a hero with no slots', () => {
    expect(restoreAllSpellSlots(undefined)).toEqual({});
  });
});

// --------------------------------------------------------------------------- //

describe('spell slots', () => {
  const slots = () => ({ level_1: { max: 4, used: 1 }, level_2: { max: 3, used: 3 } });

  it('keys a level the way the sheet does', () => {
    expect(spellSlotKey(3)).toBe('level_3');
  });

  describe('reading', () => {
    it('reads max and used off the sheet', () => {
      const char = hero({ spell_slots: slots() });

      expect(spellSlotMax(char, 1)).toBe(4);
      expect(spellSlotUsed(char, 1)).toBe(1);
      expect(hasSpellSlotLevel(char, 1)).toBe(true);
    });

    it('reports a level the sheet does not have as zero', () => {
      const char = hero({ spell_slots: slots() });

      expect(spellSlotMax(char, 9)).toBe(0);
      expect(spellSlotUsed(char, 9)).toBe(0);
      expect(hasSpellSlotLevel(char, 9)).toBe(false);
      expect(hasSpellSlotLevel(hero(), 1)).toBe(false);
      expect(hasSpellSlotLevel(null, 1)).toBe(false);
      expect(spellSlotMax(null, 1)).toBe(0);
      expect(spellSlotUsed(null, 1)).toBe(0);
    });
  });

  describe('spendSpellSlot', () => {
    it('spends one', () => {
      expect(spendSpellSlot(slots(), 1)['level_1']).toEqual({ max: 4, used: 2 });
    });

    it('cannot push used past max', () => {
      // level_2 is already 3 of 3.
      expect(spendSpellSlot(slots(), 2)['level_2']).toEqual({ max: 3, used: 3 });
    });

    it('leaves the other levels alone', () => {
      expect(spendSpellSlot(slots(), 1)['level_2']).toEqual({ max: 3, used: 3 });
    });

    /**
     * The old code invented an unrecorded level with four slots — four being a
     * guess, not a rule — so anything that asked to spend a 9th-level slot handed
     * a level 1 wizard four of them.
     */
    it('is a no-op for a level the sheet does not have', () => {
      expect(spendSpellSlot(slots(), 5)).toEqual(slots());
      expect(spendSpellSlot(slots(), 5)['level_5']).toBeUndefined();
      expect(spendSpellSlot(undefined, 1)).toEqual({});
    });
  });

  describe('regainSpellSlot', () => {
    it('gives one back', () => {
      expect(regainSpellSlot(slots(), 2)['level_2']).toEqual({ max: 3, used: 2 });
    });

    it('cannot go below zero', () => {
      const spent = { level_1: { max: 4, used: 0 } };

      expect(regainSpellSlot(spent, 1)['level_1']).toEqual({ max: 4, used: 0 });
    });

    it('is a no-op for a level the sheet does not have', () => {
      expect(regainSpellSlot(slots(), 5)).toEqual(slots());
      expect(regainSpellSlot(undefined, 1)).toEqual({});
    });
  });
});

// --------------------------------------------------------------------------- //

describe('hit points', () => {
  it('reads an unwritten current HP as full health', () => {
    expect(currentHp(hero({ hp_max: 44, hp_current: undefined }))).toBe(44);
    expect(currentHp(hero({ hp_max: 44, hp_current: 0 }))).toBe(0);
  });

  it('clamps between zero and the maximum', () => {
    expect(clampHp(-5, 20)).toBe(0);
    expect(clampHp(25, 20)).toBe(20);
    expect(clampHp(12, 20)).toBe(12);
  });

  describe('adjustedHp', () => {
    it('applies the delta', () => {
      expect(adjustedHp(hero({ hp_max: 44, hp_current: 20 }), -7)).toBe(13);
      expect(adjustedHp(hero({ hp_max: 44, hp_current: 20 }), 7)).toBe(27);
    });

    it('stops at zero', () => {
      expect(adjustedHp(hero({ hp_max: 44, hp_current: 3 }), -10)).toBe(0);
    });

    it('goes no further down once the hero is already at zero', () => {
      expect(adjustedHp(hero({ hp_max: 44, hp_current: 0 }), -1)).toBe(0);
    });

    it('stops at the maximum', () => {
      expect(adjustedHp(hero({ hp_max: 44, hp_current: 40 }), 10)).toBe(44);
      expect(adjustedHp(hero({ hp_max: 44, hp_current: undefined }), 5)).toBe(44);
    });
  });
});

// --------------------------------------------------------------------------- //

describe('level up', () => {
  const analysis = { new_total_hp: 52 };

  it('advances the level by one', () => {
    expect(levelUp(hero({ char_level: 5 }), analysis).char_level).toBe(6);
    expect(levelUp(hero({ char_level: 0 }), analysis).char_level).toBe(2);
  });

  it('takes the new maximum from the analysis and heals to it', () => {
    const advanced = levelUp(hero({ hp_max: 44, hp_current: 9 }), analysis);

    // Pinned: levelling up is a full heal on this sheet, whatever the hero's HP was.
    expect(advanced.hp_max).toBe(52);
    expect(advanced.hp_current).toBe(52);
  });

  it('appends the new features to the ones already on the sheet', () => {
    const existing = { name: 'Favored Enemy', description: 'Humanoids' };
    const gained = { name: 'Extra Attack', description: 'Attack twice.' };

    const advanced = levelUp(hero({ features_traits: [existing] }), {
      ...analysis,
      new_features: [gained],
    });

    expect(advanced.features_traits).toEqual([existing, gained]);
  });

  it('starts the list when the sheet had none', () => {
    const gained = { name: 'Extra Attack', description: 'Attack twice.' };

    expect(levelUp(hero(), { ...analysis, new_features: [gained] }).features_traits).toEqual([
      gained,
    ]);
  });

  it('leaves the existing features alone when the analysis brought none', () => {
    // Undefined rather than `[]`, so the caller knows not to overwrite the list.
    expect(levelUp(hero({ features_traits: [] }), analysis).features_traits).toBeUndefined();
  });

  it('does not touch the sheet it was given', () => {
    const char = hero({ char_level: 4, hp_max: 44, proficiency_bonus: 2 });
    levelUp(char, analysis);

    expect(char.char_level).toBe(4);
    expect(char.hp_max).toBe(44);
    expect(char.proficiency_bonus).toBe(2);
  });

  /**
   * The level-up used to leave `proficiency_bonus` exactly as it found it, so a
   * hero crossing level 5 kept a stale +2 on every proficient skill, save and
   * attack until someone edited the sheet by hand.
   */
  it('recalculates the proficiency bonus from the new level', () => {
    expect(levelUp(hero({ char_level: 4, proficiency_bonus: 2 }), analysis)).toMatchObject({
      char_level: 5,
      proficiency_bonus: 3,
    });
  });

  it('leaves the bonus alone on a level that does not cross a threshold', () => {
    expect(levelUp(hero({ char_level: 5, proficiency_bonus: 3 }), analysis)).toMatchObject({
      char_level: 6,
      proficiency_bonus: 3,
    });
  });
});
