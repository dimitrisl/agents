import { ComponentFixture, TestBed } from '@angular/core/testing';
import { StatblockModalComponent } from './statblock-modal.component';
import { DiceService } from '../../../../core/services/dice.service';
import { RollToastService } from '../../../../core/services/roll-toast.service';
import type { InitiativeCombatant } from '../../../../core/models/initiative.model';
import type { PartyMember } from '../../../../core/models/party.model';
import type { MonsterAction } from '../../../../core/models/bestiary.model';

describe('StatblockModalComponent — Challenger Adversarial & Boundary Suite', () => {
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

  describe('Task 1.1: Legacy combatant without actions, traits, or stats', () => {
    it('renders the legacy text statblock in pre-wrap when actions, traits, and stats are undefined', () => {
      component.open = true;
      component.partyMember = null;
      component.combatant = {
        id: 'legacy-1',
        name: 'Legacy Carrion Crawler',
        initiative: 12,
        hp: 51,
        max_hp: 51,
        ac: 13,
        dex: 13,
        is_player: false,
        conditions: [],
        statblock: 'Armor Class 13 (natural armor)\nHit Points 51 (6d10 + 18)\nSpeed 30 ft., climb 30 ft.\nTentacles: +8 to hit.',
      };

      fixture.detectChanges();

      const overlay = document.body;
      // Must render combatant core summary
      expect(overlay.textContent).toContain('AC: 13');
      expect(overlay.textContent).toContain('HP: 51');
      expect(overlay.textContent).toContain('DEX: 13');

      // Must render pre-wrap statblock
      expect(overlay.textContent).toContain('Armor Class 13 (natural armor)');
      expect(overlay.textContent).toContain('Tentacles: +8 to hit.');

      // Must NOT render structured ability grid or traits header
      const preWrap = overlay.querySelector('.whitespace-pre-wrap');
      expect(preWrap).toBeTruthy();
      expect(preWrap?.textContent).toContain('Tentacles: +8 to hit.');
      expect(overlay.textContent).not.toContain('Traits');
      expect(overlay.querySelector('button[tone="accent"]')).toBeNull();
      expect(overlay.querySelector('button[tone="danger"]')).toBeNull();
    });

    it('renders default fallback text when combatant has no statblock text at all', () => {
      component.open = true;
      component.partyMember = null;
      component.combatant = {
        id: 'legacy-empty',
        name: 'Empty Monster',
        initiative: 10,
        hp: 10,
        max_hp: 10,
        ac: 10,
        dex: 10,
        is_player: false,
        conditions: [],
      };

      fixture.detectChanges();

      const overlay = document.body;
      expect(overlay.textContent).toContain('Standard D&D 5e monster statblock.');
    });
  });

  describe('Task 1.2: Combatant with empty arrays (actions: [], traits: [])', () => {
    it('renders properly without crash when actions and traits are empty arrays', () => {
      expect(() => {
        component.open = true;
        component.partyMember = null;
        component.combatant = {
          id: 'empty-arrays',
          name: 'Blank Specter',
          initiative: 15,
          hp: 22,
          max_hp: 22,
          ac: 12,
          dex: 14,
          is_player: false,
          conditions: [],
          traits: [],
          actions: [],
          statblock: 'Custom specter text without structured items.',
        };
        fixture.detectChanges();
      }).not.toThrow();

      const overlay = document.body;
      expect(overlay.textContent).toContain('Blank Specter');
      expect(overlay.textContent).toContain('Custom specter text without structured items.');
      expect(overlay.textContent).not.toContain('Traits');
      expect(overlay.textContent).not.toContain('Actions');
      expect(overlay.querySelectorAll('button[tone="accent"]').length).toBe(0);
      expect(overlay.querySelectorAll('button[tone="danger"]').length).toBe(0);
    });

    it('hasStructuredContent returns false for empty arrays and null stats', () => {
      component.combatant = {
        id: 'c-test',
        name: 'Ghost',
        initiative: 10,
        hp: 10,
        max_hp: 10,
        ac: 10,
        dex: 10,
        is_player: false,
        conditions: [],
        traits: [],
        actions: [],
      };
      expect(component.hasStructuredContent()).toBe(false);
    });
  });

  describe('Task 1.3: Player combatant (partyMember) rendering', () => {
    it('renders partyMember view and isolates from monster structured sections', () => {
      component.open = true;
      component.partyMember = {
        char_id: 'pm-1',
        name: 'Aelar Silverleaf',
        portrait: 'https://example.com/portrait.png',
        char_class: 'Ranger',
        level: 7,
        hp_current: 58,
        hp_max: 64,
        ac: 16,
        conditions: ['blessed'],
        stats: { STR: 12, DEX: 18, CON: 14, INT: 10, WIS: 16, CHA: 8 },
      };
      component.combatant = {
        id: 'c-aelar',
        char_id: 'pm-1',
        name: 'Aelar Silverleaf',
        initiative: 20,
        hp: 58,
        max_hp: 64,
        ac: 16,
        dex: 18,
        is_player: true,
        conditions: ['blessed'],
        stats: { str: 12, dex: 18, con: 14, int: 10, wis: 16, cha: 8 },
        actions: [{ name: 'Longbow', attack_bonus: 7, damage_dice: '1d8+4' }],
      };

      fixture.detectChanges();

      const overlay = document.body;
      // Party member specifics
      expect(overlay.textContent).toContain('Ranger Level 7');
      expect(overlay.textContent).toContain('AC: 16');
      expect(overlay.textContent).toContain('HP: 58/64');
      const portrait = overlay.querySelector('img');
      expect(portrait).toBeTruthy();
      expect(portrait?.getAttribute('src')).toBe('https://example.com/portrait.png');

      // Check stats grid uppercase STR/DEX/etc.
      expect(overlay.textContent).toContain('STR');
      expect(overlay.textContent).toContain('12');
      expect(overlay.textContent).toContain('DEX');
      expect(overlay.textContent).toContain('18');

      // In partyMember mode, View on D&D Beyond MUST be hidden
      const beyondBtn = Array.from(overlay.querySelectorAll('button')).find((b) =>
        b.textContent?.includes('D&D Beyond')
      );
      expect(beyondBtn).toBeUndefined();

      // Monster action roll buttons MUST NOT be rendered
      expect(overlay.querySelector('button[tone="accent"]')).toBeNull();
      expect(overlay.querySelector('button[tone="danger"]')).toBeNull();
    });
  });

  describe('Adversarial Boundary & D&D Rules Stress Tests', () => {
    it('handles extreme ability scores and computes D&D mathematical modifiers accurately', () => {
      // D&D modifier formula: floor((score - 10) / 2)
      expect(component.abilityMod(1)).toBe('-5'); // Commoner debilitated
      expect(component.abilityMod(3)).toBe('-4');
      expect(component.abilityMod(8)).toBe('-1');
      expect(component.abilityMod(9)).toBe('-1');
      expect(component.abilityMod(10)).toBe('+0');
      expect(component.abilityMod(11)).toBe('+0');
      expect(component.abilityMod(12)).toBe('+1');
      expect(component.abilityMod(19)).toBe('+4');
      expect(component.abilityMod(20)).toBe('+5');
      expect(component.abilityMod(30)).toBe('+10'); // Tiamat / Tarrasque cap
      expect(component.abilityMod(0)).toBe('-5'); // Floor((0-10)/2) = -5
    });

    it('handles partial monster stats without runtime null-pointer crash', () => {
      component.open = true;
      component.partyMember = null;
      component.combatant = {
        id: 'c-partial',
        name: 'Incomplete Golem',
        initiative: 5,
        hp: 100,
        max_hp: 100,
        ac: 15,
        dex: 9,
        is_player: false,
        conditions: [],
        // Missing INT, WIS, CHA
        stats: { str: 20, dex: 9, con: 18 } as any,
      };

      expect(() => fixture.detectChanges()).not.toThrow();

      const overlay = document.body;
      expect(overlay.textContent).toContain('+5'); // STR 20
      expect(overlay.textContent).toContain('-1'); // DEX 9
      expect(overlay.textContent).toContain('+4'); // CON 18
      expect(overlay.textContent).toContain('+0'); // Missing INT -> defaults to 10 -> +0
    });

    it('preserves exact attack bonus 0 and negative bonus without falsy coercion', () => {
      const zeroAction: MonsterAction = { name: 'Pounce', attack_bonus: 0 };
      const negativeAction: MonsterAction = { name: 'Weak Flail', attack_bonus: -3 };

      expect(component.getActionAttackBonus(zeroAction)).toBe(0);
      expect(component.formatBonus(0)).toBe('+0');

      expect(component.getActionAttackBonus(negativeAction)).toBe(-3);
      expect(component.formatBonus(-3)).toBe('-3');
    });

    it('correctly executes rollAttack with bonus 0 and negative bonus', () => {
      component.combatant = {
        id: 'c-cat',
        name: 'Cat',
        initiative: 12,
        hp: 2,
        max_hp: 2,
        ac: 12,
        dex: 15,
        is_player: false,
        conditions: [],
      };

      const rollD20Spy = jest.spyOn(diceService, 'rollD20');
      const showRollSpy = jest.spyOn(rollToastService, 'showRoll');

      component.rollAttack({ name: 'Claws', attack_bonus: 0 });
      expect(rollD20Spy).toHaveBeenCalledWith(0);
      expect(showRollSpy).toHaveBeenCalledWith(
        expect.objectContaining({
          title: '⚔️ CAT — CLAWS ATTACK',
          modifier: 0,
        })
      );

      component.rollAttack({ name: 'Fumble', attack_bonus: -2 });
      expect(rollD20Spy).toHaveBeenCalledWith(-2);
      expect(showRollSpy).toHaveBeenCalledWith(
        expect.objectContaining({
          modifier: -2,
        })
      );
    });

    it('correctly executes rollDamage for compound dice and flat damage', () => {
      component.combatant = {
        id: 'c-dragon',
        name: 'Adult Red Dragon',
        initiative: 10,
        hp: 256,
        max_hp: 256,
        ac: 19,
        dex: 10,
        is_player: false,
        conditions: [],
      };

      const rollDamageSpy = jest.spyOn(diceService, 'rollDamage');
      const showRollSpy = jest.spyOn(rollToastService, 'showRoll');

      // Bite deals 2d10 + 8 piercing plus 2d6 fire
      const action: MonsterAction = {
        name: 'Bite',
        damage_dice: '2d10+8',
        damage_type: 'piercing',
        description: 'Hit: 19 (2d10 + 8) piercing damage plus 7 (2d6) fire damage.',
      };

      component.rollDamage(action);
      expect(rollDamageSpy).toHaveBeenCalledWith([{ label: 'Bite (piercing)', notation: '2d10+8' }]);
      expect(showRollSpy).toHaveBeenCalledWith(
        expect.objectContaining({
          title: '💥 ADULT RED DRAGON — BITE DAMAGE',
          damageParts: expect.any(Array),
        })
      );
    });

    it('resiliently handles action without damage or attack bonus gracefully', () => {
      component.combatant = {
        id: 'c-succubus',
        name: 'Succubus',
        initiative: 13,
        hp: 66,
        max_hp: 66,
        ac: 15,
        dex: 17,
        is_player: false,
        conditions: [],
      };

      const nonCombatAction: MonsterAction = {
        name: 'Charm',
        description: 'One humanoid the fiend can see must succeed on a DC 15 Wisdom saving throw or be charmed.',
      };

      expect(component.getActionAttackBonus(nonCombatAction)).toBeNull();
      expect(component.getActionDamageDice(nonCombatAction)).toBeNull();

      const rollD20Spy = jest.spyOn(diceService, 'rollD20');
      const rollDamageSpy = jest.spyOn(diceService, 'rollDamage');

      component.rollAttack(nonCombatAction);
      component.rollDamage(nonCombatAction);

      expect(rollD20Spy).not.toHaveBeenCalled();
      expect(rollDamageSpy).not.toHaveBeenCalled();
    });
  });
});
