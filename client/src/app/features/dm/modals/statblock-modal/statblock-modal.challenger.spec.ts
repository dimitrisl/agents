import { ComponentFixture, TestBed } from '@angular/core/testing';
import { StatblockModalComponent } from './statblock-modal.component';
import { DiceService } from '../../../../core/services/dice.service';
import { RollToastService } from '../../../../core/services/roll-toast.service';
import type { InitiativeCombatant } from '../../../../core/models/initiative.model';
import type { MonsterAction } from '../../../../core/models/bestiary.model';

describe('StatblockModalComponent — Challenger Stress & Edge-Case Harness', () => {
  let component: StatblockModalComponent;
  let fixture: ComponentFixture<StatblockModalComponent>;
  let diceService: DiceService;
  let rollToastService: RollToastService;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [StatblockModalComponent],
      providers: [DiceService, RollToastService],
    }).compileComponents();

    fixture = TestBed.createComponent(StatblockModalComponent);
    component = fixture.componentInstance;
    diceService = TestBed.inject(DiceService);
    rollToastService = TestBed.inject(RollToastService);
  });

  afterEach(() => {
    component.open = false;
    fixture.detectChanges();
  });

  // =========================================================================
  // 1. EXTREME ABILITY SCORES (0, 1, 10, 20, 30, negative, undefined, null, NaN)
  // =========================================================================
  describe('Adversarial Ability Scores & Modifiers', () => {
    it('handles D&D ability scores strictly according to PHB derivation Math.floor((score - 10) / 2)', () => {
      // Score 0: Math.floor(-10/2) = -5
      expect(component.abilityMod(0)).toBe('-5');
      // Score 1: Math.floor(-9/2) = -5
      expect(component.abilityMod(1)).toBe('-5');
      // Score 2: Math.floor(-8/2) = -4
      expect(component.abilityMod(2)).toBe('-4');
      // Score 3: Math.floor(-7/2) = -4
      expect(component.abilityMod(3)).toBe('-4');
      // Score 9: Math.floor(-1/2) = -1
      expect(component.abilityMod(9)).toBe('-1');
      // Score 10: Math.floor(0/2) = 0
      expect(component.abilityMod(10)).toBe('+0');
      // Score 11: Math.floor(1/2) = 0
      expect(component.abilityMod(11)).toBe('+0');
      // Score 12: Math.floor(2/2) = 1
      expect(component.abilityMod(12)).toBe('+1');
      // Score 19: Math.floor(9/2) = 4
      expect(component.abilityMod(19)).toBe('+4');
      // Score 20: Math.floor(10/2) = 5
      expect(component.abilityMod(20)).toBe('+5');
      // Score 30 (God / Tarrasque peak): Math.floor(20/2) = 10
      expect(component.abilityMod(30)).toBe('+10');
      // Score 40 (Supernatural overflow): Math.floor(30/2) = 15
      expect(component.abilityMod(40)).toBe('+15');
    });

    it('handles negative ability scores gracefully', () => {
      // Negative score -2: Math.floor(-12/2) = -6
      expect(component.abilityMod(-2)).toBe('-6');
      // Negative score -5: Math.floor(-15/2) = -8
      expect(component.abilityMod(-5)).toBe('-8');
    });

    it('handles undefined, null, and non-numeric ability scores safely defaulting to +0 (score 10)', () => {
      expect(component.abilityMod(undefined)).toBe('+0');
      expect(component.abilityMod(null)).toBe('+0');
    });

    it('renders partial stats safely when some ability scores are missing from combatant.stats', () => {
      component.open = true;
      component.combatant = {
        id: 'c-partial',
        name: 'Incomplete Golem',
        initiative: 10,
        hp: 50,
        max_hp: 50,
        ac: 15,
        dex: 10,
        is_player: false,
        conditions: [],
        // Only STR is defined, all other scores are undefined
        stats: { str: 22 } as any,
      };

      expect(() => fixture.detectChanges()).not.toThrow();

      const overlay = document.body;
      expect(overlay.textContent).toContain('STR');
      expect(overlay.textContent).toContain('22');
      expect(overlay.textContent).toContain('+6'); // STR 22 mod
      // Undefined DEX/CON/INT/WIS/CHA should display +0 modifier
      expect(overlay.textContent).toContain('+0');
    });
  });

  // =========================================================================
  // 2. ABNORMAL ATTACK BONUS VALUES (0, negative, +19, malformed, regex edge cases)
  // =========================================================================
  describe('Adversarial Attack Bonus Extraction & Execution', () => {
    it('correctly distinguishes numeric attack bonus 0 from null/undefined', () => {
      const actionWithZero: MonsterAction = { name: 'Touch', attack_bonus: 0 };
      expect(component.getActionAttackBonus(actionWithZero)).toBe(0);
      expect(component.formatBonus(0)).toBe('+0');
    });

    it('correctly handles extreme negative and positive attack bonuses', () => {
      const cursedAction: MonsterAction = { name: 'Feeble Strike', attack_bonus: -7 };
      expect(component.getActionAttackBonus(cursedAction)).toBe(-7);
      expect(component.formatBonus(-7)).toBe('-7');

      const avatarAction: MonsterAction = { name: 'Godly Smite', attack_bonus: 19 };
      expect(component.getActionAttackBonus(avatarAction)).toBe(19);
      expect(component.formatBonus(19)).toBe('+19');
    });

    it('extracts bonus when provided as string representation of number', () => {
      const actionStringBonus: MonsterAction = { name: 'Bite', attack_bonus: '8' as any };
      expect(component.getActionAttackBonus(actionStringBonus)).toBe(8);

      const actionSignedStringBonus: MonsterAction = { name: 'Claw', attack_bonus: '+11' as any };
      expect(component.getActionAttackBonus(actionSignedStringBonus)).toBe(11);
    });

    it('extracts attack bonuses with odd whitespace and formatting in description', () => {
      // Space between sign and digits
      expect(component.getActionAttackBonus({
        name: 'Weird Weapon',
        description: 'Melee Weapon Attack: + 9 to hit, reach 10 ft.',
      })).toBe(9);

      // Negative bonus with space
      expect(component.getActionAttackBonus({
        name: 'Clumsy Flail',
        description: 'Melee Weapon Attack: - 3 to hit, reach 5 ft.',
      })).toBe(-3);

      // Uppercase TO HIT
      expect(component.getActionAttackBonus({
        name: 'Uppercut',
        description: 'Melee Weapon Attack: +14 TO HIT, reach 5 ft.',
      })).toBe(14);
    });

    it('returns null and does not execute rollAttack on malformed or non-attack actions', () => {
      const rollD20Spy = jest.spyOn(diceService, 'rollD20');
      const showRollSpy = jest.spyOn(rollToastService, 'showRoll');

      component.combatant = {
        id: 'c-spellcaster',
        name: 'Archmage',
        initiative: 12,
        hp: 99,
        max_hp: 99,
        ac: 15,
        dex: 14,
        is_player: false,
        conditions: [],
      };

      const utilityAction: MonsterAction = {
        name: 'Time Stop',
        description: 'You briefly stop the flow of time for everyone but yourself.',
      };

      expect(component.getActionAttackBonus(utilityAction)).toBeNull();

      component.rollAttack(utilityAction);
      expect(rollD20Spy).not.toHaveBeenCalled();
      expect(showRollSpy).not.toHaveBeenCalled();
    });

    it('executes rollAttack with negative attack bonus and passes negative modifier to RollToastService', () => {
      component.combatant = {
        id: 'c-weak',
        name: 'Weak Goblin',
        initiative: 5,
        hp: 3,
        max_hp: 3,
        ac: 10,
        dex: 8,
        is_player: false,
        conditions: [],
      };

      const showRollSpy = jest.spyOn(rollToastService, 'showRoll');
      const action: MonsterAction = { name: 'Rusty Shiv', attack_bonus: -2 };

      component.rollAttack(action);

      expect(showRollSpy).toHaveBeenCalledWith(
        expect.objectContaining({
          title: '⚔️ WEAK GOBLIN — RUSTY SHIV ATTACK',
          modifier: -2,
        })
      );
    });
  });

  // =========================================================================
  // 3. COMPLEX DAMAGE EXPRESSIONS (4d6+2d8, flat damage, 0 dice, missing types)
  // =========================================================================
  describe('Adversarial Damage Expressions & Complex Dice Parsing', () => {
    it('extracts and processes compound damage dice expressions (e.g. 4d6+2d8)', () => {
      component.combatant = {
        id: 'c-dragon',
        name: 'Shadow Dragon',
        initiative: 14,
        hp: 212,
        max_hp: 212,
        ac: 18,
        dex: 10,
        is_player: false,
        conditions: [],
      };

      const action: MonsterAction = {
        name: 'Shadow Bite',
        damage_dice: '2d10+2d6+6',
        damage_type: 'necrotic',
      };

      expect(component.getActionDamageDice(action)).toBe('2d10+2d6+6');

      const rollDamageSpy = jest.spyOn(diceService, 'rollDamage');
      const showRollSpy = jest.spyOn(rollToastService, 'showRoll');

      component.rollDamage(action);

      expect(rollDamageSpy).toHaveBeenCalledWith([{
        label: 'Shadow Bite (necrotic)',
        notation: '2d10+2d6+6',
      }]);
      expect(showRollSpy).toHaveBeenCalledWith(
        expect.objectContaining({
          title: '💥 SHADOW DRAGON — SHADOW BITE DAMAGE',
          damageParts: expect.any(Array),
        })
      );
    });

    it('safely rolls flat damage notation without division by zero or NaN', () => {
      component.combatant = {
        id: 'c-homunculus',
        name: 'Homunculus',
        initiative: 12,
        hp: 5,
        max_hp: 5,
        ac: 13,
        dex: 15,
        is_player: false,
        conditions: [],
      };

      const action: MonsterAction = {
        name: 'Bite',
        damage_dice: '1',
        damage_type: 'piercing',
      };

      const showRollSpy = jest.spyOn(rollToastService, 'showRoll');

      component.rollDamage(action);

      expect(showRollSpy).toHaveBeenCalledWith(
        expect.objectContaining({
          title: '💥 HOMUNCULUS — BITE DAMAGE',
          total: 1,
          rolls: expect.arrayContaining([1]),
          sides: expect.any(Number),
        })
      );
    });

    it('extracts multi-part damage from SRD description with primary and secondary damage clauses', () => {
      const action: MonsterAction = {
        name: 'Poison Dagger',
        description: 'Hit: 4 (1d4 + 2) piercing damage plus 10 (3d6) poison damage.',
      };

      // Primary damage should be extracted
      expect(component.getActionDamageDice(action)).toBe('1d4+2');
      expect(component.getActionDamageType(action)).toBe('piercing');
    });

    it('extracts damage dice with no modifier (e.g. 8d6)', () => {
      const breathAction: MonsterAction = {
        name: 'Fire Breath',
        description: 'taking 28 (8d6) fire damage on a failed save.',
      };

      expect(component.getActionDamageDice(breathAction)).toBe('8d6');
      expect(component.getActionDamageType(breathAction)).toBe('fire');
    });

    it('extracts damage type correctly across all 13 standard D&D damage types', () => {
      const types = [
        'acid', 'bludgeoning', 'cold', 'fire', 'force',
        'lightning', 'necrotic', 'piercing', 'poison',
        'psychic', 'radiant', 'slashing', 'thunder',
      ];

      for (const t of types) {
        const action: MonsterAction = {
          name: `${t} attack`,
          description: `Hit: 7 (2d6) ${t} damage.`,
        };
        expect(component.getActionDamageType(action)).toBe(t);
      }
    });

    it('handles damage action with missing damage_type by using action name alone in label', () => {
      component.combatant = {
        id: 'c-untyped',
        name: 'Mysterious Entity',
        initiative: 10,
        hp: 30,
        max_hp: 30,
        ac: 12,
        dex: 10,
        is_player: false,
        conditions: [],
      };

      const action: MonsterAction = {
        name: 'Disruption',
        damage_dice: '3d6',
        description: 'Hit: 10 (3d6) damage.', // untyped damage
      };

      const rollDamageSpy = jest.spyOn(diceService, 'rollDamage');
      component.rollDamage(action);

      // Should label simply as 'Disruption' without undefined or null
      expect(rollDamageSpy).toHaveBeenCalledWith([{ label: 'Disruption', notation: '3d6' }]);
    });
  });

  // =========================================================================
  // 4. EDGE-CASE ACTION DESCRIPTIONS & MISSING PROPERTIES
  // =========================================================================
  describe('Adversarial Missing Properties & Schema Defiance', () => {
    it('handles action with completely empty object without crashing', () => {
      const emptyAction: MonsterAction = {} as any;

      expect(() => component.getActionAttackBonus(emptyAction)).not.toThrow();
      expect(component.getActionAttackBonus(emptyAction)).toBeNull();

      expect(() => component.getActionDamageDice(emptyAction)).not.toThrow();
      expect(component.getActionDamageDice(emptyAction)).toBeNull();

      expect(() => component.getActionDamageType(emptyAction)).not.toThrow();
      expect(component.getActionDamageType(emptyAction)).toBeNull();
    });

    it('uses fallback name defaults when combatant or action name is missing', () => {
      component.combatant = {
        id: 'c-nameless',
        name: '', // Empty name
        initiative: 10,
        hp: 10,
        max_hp: 10,
        ac: 10,
        dex: 10,
        is_player: false,
        conditions: [],
      };

      const showRollSpy = jest.spyOn(rollToastService, 'showRoll');

      const namelessAttack: MonsterAction = { name: '', attack_bonus: 3 };
      component.rollAttack(namelessAttack);

      expect(showRollSpy).toHaveBeenCalledWith(
        expect.objectContaining({
          title: '⚔️ CREATURE — ATTACK ATTACK',
        })
      );

      const namelessDamage: MonsterAction = { name: '', damage_dice: '1d6' };
      component.rollDamage(namelessDamage);

      expect(showRollSpy).toHaveBeenCalledWith(
        expect.objectContaining({
          title: '💥 CREATURE — ACTION DAMAGE',
        })
      );
    });

    it('supports actions using desc instead of description property', () => {
      const actionWithDesc: MonsterAction = {
        name: 'Mace',
        desc: 'Melee Weapon Attack: +5 to hit. Hit: 6 (1d6 + 2) bludgeoning damage.',
      } as any;

      expect(component.getActionAttackBonus(actionWithDesc)).toBe(5);
      expect(component.getActionDamageDice(actionWithDesc)).toBe('1d6+2');
      expect(component.getActionDamageType(actionWithDesc)).toBe('bludgeoning');
    });

    it('escapes and safely renders action descriptions containing HTML/script tags', () => {
      component.open = true;
      component.combatant = {
        id: 'c-xss',
        name: 'Corrupted Infiltrator',
        initiative: 10,
        hp: 15,
        max_hp: 15,
        ac: 12,
        dex: 10,
        is_player: false,
        conditions: [],
        actions: [{
          name: '<script>alert("hack")</script>Corrupting Strike',
          description: '<img src=x onerror=alert(1)> Hit: 4 (1d4 + 2) necrotic damage.',
        }],
      };

      fixture.detectChanges();

      const overlay = document.body;
      // Script tags must NOT execute and must be rendered safely as text content
      expect(overlay.querySelector('script')).toBeNull();
      expect(overlay.textContent).toContain('<script>alert("hack")</script>');
      expect(overlay.textContent).toContain('Hit: 4 (1d4 + 2) necrotic damage.');
    });

    it('renders huge numbers of actions without crashing or performance degradation', () => {
      const manyActions: MonsterAction[] = Array.from({ length: 50 }, (_, i) => ({
        name: `Strike #${i + 1}`,
        attack_bonus: 5 + (i % 5),
        damage_dice: `${(i % 3) + 1}d6+3`,
        damage_type: 'slashing',
        description: `Melee Attack #${i + 1}: +${5 + (i % 5)} to hit. Hit: ${(i % 3) + 1}d6+3 damage.`,
      }));

      component.open = true;
      component.combatant = {
        id: 'c-hydra',
        name: '50-Headed Hydra',
        initiative: 10,
        hp: 500,
        max_hp: 500,
        ac: 15,
        dex: 12,
        is_player: false,
        conditions: [],
        actions: manyActions,
      };

      expect(() => fixture.detectChanges()).not.toThrow();

      const overlay = document.body;
      const attackButtons = overlay.querySelectorAll('button[tone="accent"]');
      const damageButtons = overlay.querySelectorAll('button[tone="danger"]');

      expect(attackButtons.length).toBe(50);
      expect(damageButtons.length).toBe(50);
    });
  });

  // =========================================================================
  // 5. RAPID CLICK & STATE RESILIENCE
  // =========================================================================
  describe('Rapid Click & Event Concurrency', () => {
    it('survives rapid consecutive clicks on attack and damage buttons independently', () => {
      component.combatant = {
        id: 'c-boss',
        name: 'Lich King',
        initiative: 20,
        hp: 135,
        max_hp: 135,
        ac: 17,
        dex: 16,
        is_player: false,
        conditions: [],
      };

      const showRollSpy = jest.spyOn(rollToastService, 'showRoll');
      const action: MonsterAction = {
        name: 'Paralyzing Touch',
        attack_bonus: 12,
        damage_dice: '3d6',
        damage_type: 'cold',
      };

      // 10 rapid attack clicks
      for (let i = 0; i < 10; i++) {
        component.rollAttack(action);
      }
      expect(showRollSpy).toHaveBeenCalledTimes(10);

      // 10 rapid damage clicks
      for (let i = 0; i < 10; i++) {
        component.rollDamage(action);
      }
      expect(showRollSpy).toHaveBeenCalledTimes(20);
    });
  });
});
