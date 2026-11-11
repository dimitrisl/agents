import { CharacterSchema } from '../models/character.model';
import {
  availableHitDice,
  availableHitDieOptions,
  conModifier,
  hitDieSize,
  planShortRest,
  rechargeShortRestResources,
  resolveLongRest,
  resolveShortRest,
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
  });
});
