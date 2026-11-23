import { CharacterSchema } from '../models/character.model';
import {
  applyShortRestSlotRecovery,
  availableHitDice,
  availableHitDieOptions,
  conModifier,
  harnessDivinePowerMaxSlotLevel,
  hasShortRestSlotRecovery,
  hitDieSize,
  planShortRest,
  rechargeShortRestResources,
  resolveLongRest,
  resolveShortRest,
  shortRestRecoveryBudget,
  songOfRestDie,
  warlockPactDetails,
} from './rest';

function hero(overrides: Partial<CharacterSchema> = {}): CharacterSchema {
  return {
    char_id: 'test-hero-1',
    char_name: 'Valeros',
    char_class: 'Fighter',
    char_level: 5,
    race: 'Human',
    background: 'Soldier',
    armor_class: 18,
    hp_max: 44,
    hp_current: 20,
    speed: 30,
    proficiency_bonus: 3,
    stats: { STR: 16, DEX: 12, CON: 14, INT: 10, WIS: 12, CHA: 8 },
    saving_throws: ['STR', 'CON'],
    skill_proficiencies: ['Athletics', 'Intimidation'],
    ...overrides,
  };
}

describe('rest rules', () => {
  describe('resolveLongRest', () => {
    describe('2024 Revision ruleset', () => {
      it('recovers all spent hit dice when dnd_edition contains "2024"', () => {
        const char = hero({
          char_level: 5,
          hit_dice_used: 5,
          dnd_edition: '2024 Edition',
        });
        const rest = resolveLongRest(char);

        expect(rest.hpCurrent).toBe(44);
        expect(rest.hitDiceRecovered).toBe(5);
        expect(rest.hitDiceUsed).toBe(0);
      });

      it('recovers all spent hit dice when ruleset_version contains "2024"', () => {
        const char = hero({
          char_level: 6,
          hit_dice_used: 4,
          ruleset_version: '2024',
        });
        const rest = resolveLongRest(char);

        expect(rest.hpCurrent).toBe(44);
        expect(rest.hitDiceRecovered).toBe(6);
        expect(rest.hitDiceUsed).toBe(0);
      });

      it('recovers all hit dice when both dnd_edition and ruleset_version specify 2024', () => {
        const char = hero({
          char_level: 8,
          hit_dice_used: 8,
          dnd_edition: 'D&D 2024 Revision',
          ruleset_version: '2024.1',
        });
        const rest = resolveLongRest(char);

        expect(rest.hitDiceRecovered).toBe(8);
        expect(rest.hitDiceUsed).toBe(0);
      });

      it('gives a level 1 hero all hit dice back (1 die)', () => {
        const char = hero({
          char_level: 1,
          hit_dice_used: 1,
          dnd_edition: '2024',
        });
        const rest = resolveLongRest(char);

        expect(rest.hitDiceRecovered).toBe(1);
        expect(rest.hitDiceUsed).toBe(0);
      });

      it('gives a level 20 hero all 20 hit dice back', () => {
        const char = hero({
          char_level: 20,
          hit_dice_used: 15,
          dnd_edition: '2024',
        });
        const rest = resolveLongRest(char);

        expect(rest.hitDiceRecovered).toBe(20);
        expect(rest.hitDiceUsed).toBe(0);
      });

      it('leaves hitDiceUsed at 0 even if character had 0 used hit dice', () => {
        const char = hero({
          char_level: 5,
          hit_dice_used: 0,
          dnd_edition: '2024',
        });
        const rest = resolveLongRest(char);

        expect(rest.hitDiceRecovered).toBe(5);
        expect(rest.hitDiceUsed).toBe(0);
      });

      it('treats a sheet with char_level 0 as level 1 and recovers 1 die', () => {
        const char = hero({
          char_level: 0,
          hit_dice_used: 1,
          dnd_edition: '2024',
        });
        const rest = resolveLongRest(char);

        expect(rest.hitDiceRecovered).toBe(1);
        expect(rest.hitDiceUsed).toBe(0);
      });
    });

    describe('2014 Edition ruleset', () => {
      it('recovers half total hit dice floored when dnd_edition contains "2014"', () => {
        const char = hero({
          char_level: 5,
          hit_dice_used: 5,
          dnd_edition: '2014 Edition',
        });
        const rest = resolveLongRest(char);

        expect(rest.hpCurrent).toBe(44);
        expect(rest.hitDiceRecovered).toBe(2); // Math.floor(5 / 2) = 2
        expect(rest.hitDiceUsed).toBe(3); // 5 - 2 = 3
      });

      it('recovers half total hit dice when neither property is specified (default 2014)', () => {
        const char = hero({
          char_level: 6,
          hit_dice_used: 6,
        });
        const rest = resolveLongRest(char);

        expect(rest.hitDiceRecovered).toBe(3); // Math.floor(6 / 2) = 3
        expect(rest.hitDiceUsed).toBe(3);
      });

      it('recovers a minimum of 1 die for a level 1 hero', () => {
        const char = hero({
          char_level: 1,
          hit_dice_used: 1,
          dnd_edition: '2014',
        });
        const rest = resolveLongRest(char);

        expect(rest.hitDiceRecovered).toBe(1);
        expect(rest.hitDiceUsed).toBe(0);
      });

      it('cannot push hitDiceUsed below zero when recovering more dice than spent', () => {
        const char = hero({
          char_level: 9,
          hit_dice_used: 1,
          dnd_edition: '2014',
        });
        const rest = resolveLongRest(char);

        expect(rest.hitDiceRecovered).toBe(4); // Math.floor(9 / 2) = 4
        expect(rest.hitDiceUsed).toBe(0);
      });

      it('treats a sheet with char_level 0 as level 1', () => {
        const char = hero({
          char_level: 0,
          hit_dice_used: 0,
          dnd_edition: '2014',
        });
        const rest = resolveLongRest(char);

        expect(rest.hitDiceRecovered).toBe(1);
        expect(rest.hitDiceUsed).toBe(0);
      });

      it('recovers half total hit dice for other editions like "5e" or "Legacy"', () => {
        const char = hero({
          char_level: 7,
          hit_dice_used: 5,
          dnd_edition: '5e Legacy',
        });
        const rest = resolveLongRest(char);

        expect(rest.hitDiceRecovered).toBe(3); // Math.floor(7 / 2) = 3
        expect(rest.hitDiceUsed).toBe(2); // 5 - 3 = 2
      });
    });

    it('always restores character to hp_max regardless of edition', () => {
      const char2024 = hero({ hp_max: 50, hp_current: 5, dnd_edition: '2024' });
      const char2014 = hero({ hp_max: 50, hp_current: 5, dnd_edition: '2014' });

      expect(resolveLongRest(char2024).hpCurrent).toBe(50);
      expect(resolveLongRest(char2014).hpCurrent).toBe(50);
    });
  });

  describe('short rest planning and resolution', () => {
    it('plans a short rest correctly within available hit dice', () => {
      const char = hero({ char_level: 5, hit_dice_used: 2, stats: { STR: 10, DEX: 10, CON: 14, INT: 10, WIS: 10, CHA: 10 } });
      const plan = planShortRest(char, 2);

      expect(plan).not.toBeNull();
      expect(plan?.diceSpent).toBe(2);
      expect(plan?.conModifier).toBe(2);
      expect(plan?.conBonus).toBe(4);
    });

    it('resolves a short rest and heals without exceeding hp_max', () => {
      const char = hero({ hp_max: 40, hp_current: 25, hit_dice_used: 1 });
      const plan = { diceSpent: 2, dieSize: 10, conModifier: 2, conBonus: 4 };
      const outcome = resolveShortRest(char, plan, 20);

      expect(outcome.rolled).toBe(20);
      expect(outcome.hpGained).toBe(15); // capped at 40
      expect(outcome.hpAfter).toBe(40);
      expect(outcome.hitDiceUsed).toBe(3);
    });
  });

  describe('rechargeShortRestResources', () => {
    it('restores 1 use for 2024 Rage, Second Wind, Channel Divinity, and Wild Shape', () => {
      const resources = [
        { name: 'Rage', current: 0, max: 3, recharge: 'long' as const },
        { name: 'Second Wind', current: 1, max: 2, recharge: 'short' as const },
        { name: 'Channel Divinity', current: 0, max: 2, recharge: 'short' as const },
        { name: 'Wild Shape', current: 0, max: 2, recharge: 'short' as const },
        { name: 'Action Surge', current: 0, max: 1, recharge: 'short' as const },
      ];

      const recharged = rechargeShortRestResources(resources, '2024');

      expect(recharged.find((r) => r.name === 'Rage')?.current).toBe(1);
      expect(recharged.find((r) => r.name === 'Second Wind')?.current).toBe(2);
      expect(recharged.find((r) => r.name === 'Channel Divinity')?.current).toBe(1);
      expect(recharged.find((r) => r.name === 'Wild Shape')?.current).toBe(1);
      expect(recharged.find((r) => r.name === 'Action Surge')?.current).toBe(1); // regular short rest recharge
    });

    it('restores +4 Sorcery Points for 2014 Sorcerer level 20 on short rest (and excludes 2024)', () => {
      const resources = [
        { name: 'Sorcery Points', current: 3, max: 20, recharge: 'long' as const },
      ];
      const sorc2014 = hero({ char_class: 'Sorcerer', char_level: 20, dnd_edition: '2014 Edition' });
      const res14 = rechargeShortRestResources(resources, '2014 Edition', sorc2014);
      expect(res14[0].current).toBe(7);

      const fontRes = rechargeShortRestResources(
        [{ name: 'Font of Magic', current: 2, max: 20, recharge: 'long' as const }],
        '2014 Edition',
        sorc2014
      );
      expect(fontRes[0].current).toBe(6);

      const sorc2024 = hero({ char_class: 'Sorcerer', char_level: 20, dnd_edition: '2024 Revision' });
      const res24 = rechargeShortRestResources(resources, '2024 Revision', sorc2024);
      expect(res24[0].current).toBe(3);
    });
  });

  describe('songOfRestDie', () => {
    it('scales 1d6/1d8/1d10/1d12 across 2014 Bard tiers and returns null for 2024', () => {
      expect(songOfRestDie(hero({ char_class: 'Bard', char_level: 1, dnd_edition: '2014 Edition' }))).toBeNull();
      expect(songOfRestDie(hero({ char_class: 'Bard', char_level: 2, dnd_edition: '2014 Edition' }))).toBe('1d6');
      expect(songOfRestDie(hero({ char_class: 'Bard', char_level: 9, dnd_edition: '2014 Edition' }))).toBe('1d8');
      expect(songOfRestDie(hero({ char_class: 'Bard', char_level: 13, dnd_edition: '2014 Edition' }))).toBe('1d10');
      expect(songOfRestDie(hero({ char_class: 'Bard', char_level: 17, dnd_edition: '2014 Edition' }))).toBe('1d12');
      expect(songOfRestDie(hero({ char_class: 'Bard', char_level: 17, dnd_edition: '2024 Revision' }))).toBeNull();
    });
  });

  describe('multiclass hit die resolution', () => {
    it('resolves Sorcerer 5 / Warlock 3 primary die as d6 despite descending "3d8, 5d6" string', () => {
      const sorclock = hero({
        char_class: 'Sorcerer',
        char_level: 8,
        hit_dice: '3d8, 5d6',
        classes: [
          { class_name: 'Sorcerer', level: 5 },
          { class_name: 'Warlock', level: 3 },
        ],
      });

      expect(hitDieSize(sorclock)).toBe(6);
      expect(availableHitDieOptions(sorclock)).toEqual([
        { className: 'Sorcerer', level: 5, dieSize: 6 },
        { className: 'Warlock', level: 3, dieSize: 8 },
      ]);
    });

    it('resolves Paladin 5 / Sorcerer 3 pools as d10 and d6 accurately', () => {
      const palasorc = hero({
        char_class: 'Paladin',
        char_level: 8,
        hit_dice: '5d10, 3d6',
        classes: [
          { class_name: 'Paladin', level: 5 },
          { class_name: 'Sorcerer', level: 3 },
        ],
      });

      expect(hitDieSize(palasorc)).toBe(10);
      expect(availableHitDieOptions(palasorc)).toEqual([
        { className: 'Paladin', level: 5, dieSize: 10 },
        { className: 'Sorcerer', level: 3, dieSize: 6 },
      ]);
    });
  });

  describe('short-rest spell slot recovery helpers', () => {
    it('computes Arcane Recovery and Natural Recovery budgets across 2014 and 2024', () => {
      const wiz = hero({
        char_class: 'Wizard',
        char_level: 5,
        classes: [{ class_name: 'Wizard', level: 5 }],
        class_resources: [{ name: 'Arcane Recovery', current: 1, max: 1, recharge: 'long' }],
      });
      expect(shortRestRecoveryBudget(wiz, 'arcane_recovery')).toBe(3);

      const wizSpent = hero({
        ...wiz,
        class_resources: [{ name: 'Arcane Recovery', current: 0, max: 1, recharge: 'long' }],
      });
      expect(shortRestRecoveryBudget(wizSpent, 'arcane_recovery')).toBe(0);

      const land2014 = hero({
        char_class: 'Druid',
        subclass: 'Circle of the Land',
        char_level: 4,
        dnd_edition: '2014 Edition',
        classes: [{ class_name: 'Druid', subclass: 'Circle of the Land', level: 4 }],
        class_resources: [{ name: 'Natural Recovery', current: 1, max: 1, recharge: 'long' }],
      });
      expect(shortRestRecoveryBudget(land2014, 'natural_recovery')).toBe(2);

      const land2024Low = hero({
        ...land2014,
        dnd_edition: '2024 Revision (5.5e)',
      });
      expect(shortRestRecoveryBudget(land2024Low, 'natural_recovery')).toBe(0);

      const land2024L6 = hero({
        char_class: 'Druid',
        subclass: 'Circle of the Land',
        char_level: 6,
        dnd_edition: '2024 Revision (5.5e)',
        classes: [{ class_name: 'Druid', subclass: 'Circle of the Land', level: 6 }],
        class_resources: [{ name: 'Natural Recovery', current: 1, max: 1, recharge: 'long' }],
      });
      expect(shortRestRecoveryBudget(land2024L6, 'natural_recovery')).toBe(3);
    });

    it('computes Harness Divine Power cap and allows 0-Hit-Dice short rest plans', () => {
      const cleric = hero({
        char_class: 'Cleric',
        char_level: 5,
        proficiency_bonus: 3,
        classes: [{ class_name: 'Cleric', level: 5 }],
        class_resources: [{ name: 'Channel Divinity', current: 1, max: 2, recharge: 'short' }],
        hit_dice_used: 5,
      });
      expect(harnessDivinePowerMaxSlotLevel(cleric)).toBe(2);
      expect(hasShortRestSlotRecovery(cleric)).toBe(true);
      expect(planShortRest(cleric, 0, 8)).toEqual({
        diceSpent: 0,
        dieSize: 8,
        conBonus: 0,
        conModifier: 2,
      });

      const noCd = hero({
        ...cleric,
        class_resources: [{ name: 'Channel Divinity', current: 0, max: 2, recharge: 'short' }],
      });
      expect(harnessDivinePowerMaxSlotLevel(noCd)).toBe(0);
      expect(hasShortRestSlotRecovery(noCd)).toBe(false);
    });

    it('immutably recovers spell slots and consumes Arcane/Natural Recovery & Channel Divinity', () => {
      const slots = {
        level_1: { max: 4, used: 2 },
        level_2: { max: 3, used: 1 },
      };
      const resources = [
        { name: 'Arcane Recovery', current: 1, max: 1, recharge: 'long' as const },
        { name: 'Channel Divinity', current: 1, max: 2, recharge: 'short' as const },
      ];
      const out = applyShortRestSlotRecovery(slots, resources, {
        arcaneRecoverySlots: { 1: 1, 2: 1 },
        harnessDivinePowerSlot: 1,
      });

      expect(out.spell_slots['level_1'].used).toBe(0);
      expect(out.spell_slots['level_2'].used).toBe(0);
      expect(out.class_resources.find((r) => r.name === 'Arcane Recovery')?.current).toBe(0);
      expect(out.class_resources.find((r) => r.name === 'Channel Divinity')?.current).toBe(0);
      // Original objects remain unmutated
      expect(slots.level_1.used).toBe(2);
      expect(resources[0].current).toBe(1);
    });

    it('does not consume recovery pools when target slots have no non-pact expended uses and isolates multiclass subclass fallback', () => {
      const mcDruid = hero({
        char_class: 'Fighter',
        subclass: 'Highlander',
        char_level: 7,
        dnd_edition: '2014 Edition',
        classes: [
          { class_name: 'Fighter', subclass: 'Highlander', level: 3 },
          { class_name: 'Druid', subclass: 'Circle of the Moon', level: 4 },
        ],
        class_resources: [{ name: 'Natural Recovery', current: 1, max: 1, recharge: 'long' }],
      });
      expect(shortRestRecoveryBudget(mcDruid, 'natural_recovery')).toBe(0);

      // Only Pact slots spent (used: 2, pact_used: 2) -> must NOT consume Arcane Recovery or Channel Divinity
      const pactOnlySlots = {
        level_1: { max: 6, used: 2, pact_max: 2, pact_used: 2 },
      };
      const resources = [
        { name: 'Arcane Recovery', current: 1, max: 1, recharge: 'long' as const },
        { name: 'Channel Divinity', current: 1, max: 1, recharge: 'short' as const },
      ];
      const out = applyShortRestSlotRecovery(pactOnlySlots, resources, {
        arcaneRecoverySlots: { 1: 1 },
        harnessDivinePowerSlot: 1,
      });
      expect(out.spell_slots['level_1'].used).toBe(2);
      expect(out.class_resources.find((r) => r.name === 'Arcane Recovery')?.current).toBe(1);
      expect(out.class_resources.find((r) => r.name === 'Channel Divinity')?.current).toBe(1);
    });
  });
});
