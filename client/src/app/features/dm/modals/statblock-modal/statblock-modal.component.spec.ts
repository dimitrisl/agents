import { ComponentFixture, TestBed } from '@angular/core/testing';
import { StatblockModalComponent } from './statblock-modal.component';
import { DiceService } from '../../../../core/services/dice.service';
import { RollToastService } from '../../../../core/services/roll-toast.service';
import type { InitiativeCombatant } from '../../../../core/models/initiative.model';
import type { PartyMember } from '../../../../core/models/party.model';
import type { MonsterAction } from '../../../../core/models/bestiary.model';

describe('StatblockModalComponent', () => {
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

  it('should create the component with initial defaults', () => {
    expect(component).toBeTruthy();
    expect(component.open).toBe(false);
    expect(component.combatant).toBeNull();
    expect(component.partyMember).toBeNull();
  });

  describe('hasStructuredContent', () => {
    it('returns false when combatant is null', () => {
      component.combatant = null;
      expect(component.hasStructuredContent()).toBe(false);
    });

    it('returns false when combatant has neither actions, traits, nor stats', () => {
      component.combatant = {
        id: 'c1',
        name: 'Zombie',
        initiative: 8,
        hp: 22,
        max_hp: 22,
        ac: 8,
        dex: 6,
        is_player: false,
        conditions: [],
        statblock: 'AC 8, HP 22',
      };
      expect(component.hasStructuredContent()).toBe(false);
    });

    it('returns true when combatant has stats', () => {
      component.combatant = {
        id: 'c1',
        name: 'Goblin',
        initiative: 12,
        hp: 7,
        max_hp: 7,
        ac: 15,
        dex: 14,
        is_player: false,
        conditions: [],
        stats: { str: 8, dex: 14, con: 10, int: 10, wis: 8, cha: 8 },
      };
      expect(component.hasStructuredContent()).toBe(true);
    });

    it('returns true when combatant has actions', () => {
      component.combatant = {
        id: 'c1',
        name: 'Skeleton',
        initiative: 10,
        hp: 13,
        max_hp: 13,
        ac: 13,
        dex: 14,
        is_player: false,
        conditions: [],
        actions: [{ name: 'Shortsword', attack_bonus: 4, damage_dice: '1d6+2' }],
      };
      expect(component.hasStructuredContent()).toBe(true);
    });

    it('returns true when combatant has traits', () => {
      component.combatant = {
        id: 'c1',
        name: 'Wolf',
        initiative: 14,
        hp: 11,
        max_hp: 11,
        ac: 13,
        dex: 15,
        is_player: false,
        conditions: [],
        traits: [{ name: 'Pack Tactics', description: 'Advantage on attack rolls when ally is adjacent.' }],
      };
      expect(component.hasStructuredContent()).toBe(true);
    });
  });

  describe('abilityMod and formatBonus', () => {
    it('computes correct modifier strings for various scores', () => {
      expect(component.abilityMod(10)).toBe('+0');
      expect(component.abilityMod(11)).toBe('+0');
      expect(component.abilityMod(12)).toBe('+1');
      expect(component.abilityMod(14)).toBe('+2');
      expect(component.abilityMod(18)).toBe('+4');
      expect(component.abilityMod(20)).toBe('+5');
      expect(component.abilityMod(8)).toBe('-1');
      expect(component.abilityMod(7)).toBe('-2');
      expect(component.abilityMod(1)).toBe('-5');
      expect(component.abilityMod(null)).toBe('+0');
      expect(component.abilityMod(undefined)).toBe('+0');
    });

    it('formats bonuses with sign prefix', () => {
      expect(component.formatBonus(5)).toBe('+5');
      expect(component.formatBonus(0)).toBe('+0');
      expect(component.formatBonus(-3)).toBe('-3');
    });
  });

  describe('getActionAttackBonus', () => {
    it('returns structured attack_bonus when numeric', () => {
      expect(component.getActionAttackBonus({ name: 'Bite', attack_bonus: 5 })).toBe(5);
    });

    it('returns 0 when attack_bonus is 0', () => {
      expect(component.getActionAttackBonus({ name: 'Claws', attack_bonus: 0 })).toBe(0);
    });

    it('returns negative value when attack_bonus is negative', () => {
      expect(component.getActionAttackBonus({ name: 'Slam', attack_bonus: -2 })).toBe(-2);
    });

    it('extracts bonus via regex fallback on description', () => {
      expect(component.getActionAttackBonus({
        name: 'Dagger',
        description: 'Melee Weapon Attack: +6 to hit, reach 5 ft., one target.',
      })).toBe(6);
    });

    it('extracts bonus via regex fallback on desc', () => {
      expect(component.getActionAttackBonus({
        name: 'Club',
        desc: 'Melee Weapon Attack: +2 to hit, reach 5 ft.',
      })).toBe(2);
    });

    it('extracts negative bonus via regex fallback', () => {
      expect(component.getActionAttackBonus({
        name: 'Flail',
        description: 'Melee Weapon Attack: -1 to hit, reach 5 ft.',
      })).toBe(-1);
    });

    it('returns null when action has no attack bonus or regex match', () => {
      expect(component.getActionAttackBonus({
        name: 'Fire Breath',
        description: 'DC 15 Dexterity saving throw, taking 24 (7d6) fire damage on a failed save.',
      })).toBeNull();
    });

    it('returns null when description is empty or missing', () => {
      expect(component.getActionAttackBonus({ name: 'Multiattack' })).toBeNull();
    });
  });

  describe('getActionDamageDice', () => {
    it('returns structured damage_dice when provided', () => {
      expect(component.getActionDamageDice({ name: 'Bite', damage_dice: '2d6+3' })).toBe('2d6+3');
    });

    it('returns flat damage notation', () => {
      expect(component.getActionDamageDice({ name: 'Scratch', damage_dice: '1' })).toBe('1');
    });

    it('extracts parenthesized dice notation from description', () => {
      expect(component.getActionDamageDice({
        name: 'Scimitar',
        description: 'Hit: 5 (1d6 + 2) slashing damage.',
      })).toBe('1d6+2');
    });

    it('extracts dice from breath weapon description', () => {
      expect(component.getActionDamageDice({
        name: 'Lightning Breath',
        description: 'taking 55 (10d10) lightning damage on a failed save.',
      })).toBe('10d10');
    });

    it('extracts flat damage from description fallback', () => {
      expect(component.getActionDamageDice({
        name: 'Cat Claws',
        description: 'Hit: 1 slashing damage.',
      })).toBe('1');
    });

    it('returns null when no damage is mentioned', () => {
      expect(component.getActionDamageDice({
        name: 'Dodge',
        description: 'Focuses entirely on avoiding attacks.',
      })).toBeNull();
    });
  });

  describe('getActionDamageType', () => {
    it('returns structured damage_type in lowercase', () => {
      expect(component.getActionDamageType({ name: 'Bite', damage_type: 'Piercing' })).toBe('piercing');
    });

    it('extracts damage type from description via regex fallback', () => {
      expect(component.getActionDamageType({
        name: 'Claws',
        description: 'Hit: 7 (2d4 + 2) slashing damage.',
      })).toBe('slashing');
    });

    it('extracts elemental damage type', () => {
      expect(component.getActionDamageType({
        name: 'Firebolt',
        description: 'Hit: 5 (1d10) fire damage.',
      })).toBe('fire');
    });

    it('returns null when no damage type is recognized', () => {
      expect(component.getActionDamageType({
        name: 'Shove',
        description: 'Pushes the target 5 feet back.',
      })).toBeNull();
    });
  });

  describe('rollAttack', () => {
    it('invokes dice.rollD20 and announces via rollToast.showRoll', () => {
      component.combatant = {
        id: 'c1',
        name: 'Goblin Boss',
        initiative: 15,
        hp: 21,
        max_hp: 21,
        ac: 17,
        dex: 14,
        is_player: false,
        conditions: [],
      };

      const rollD20Spy = jest.spyOn(diceService, 'rollD20');
      const showRollSpy = jest.spyOn(rollToastService, 'showRoll');

      const action: MonsterAction = { name: 'Scimitar', attack_bonus: 4 };
      component.rollAttack(action);

      expect(rollD20Spy).toHaveBeenCalledWith(4);
      expect(showRollSpy).toHaveBeenCalledWith(
        expect.objectContaining({
          title: '⚔️ GOBLIN BOSS — SCIMITAR ATTACK',
          modifier: 4,
          sides: 20,
        })
      );
    });

    it('does nothing when combatant is not set', () => {
      component.combatant = null;
      const rollD20Spy = jest.spyOn(diceService, 'rollD20');
      component.rollAttack({ name: 'Bite', attack_bonus: 3 });
      expect(rollD20Spy).not.toHaveBeenCalled();
    });

    it('does nothing when action has no attack bonus', () => {
      component.combatant = {
        id: 'c1',
        name: 'Mage',
        initiative: 10,
        hp: 40,
        max_hp: 40,
        ac: 12,
        dex: 14,
        is_player: false,
        conditions: [],
      };
      const rollD20Spy = jest.spyOn(diceService, 'rollD20');
      component.rollAttack({ name: 'Teleport', description: 'Teleports 30 feet.' });
      expect(rollD20Spy).not.toHaveBeenCalled();
    });
  });

  describe('rollDamage', () => {
    it('invokes dice.rollDamage and announces via rollToast.showRoll with damage parts', () => {
      component.combatant = {
        id: 'c1',
        name: 'Ogre',
        initiative: 8,
        hp: 59,
        max_hp: 59,
        ac: 11,
        dex: 8,
        is_player: false,
        conditions: [],
      };

      const rollDamageSpy = jest.spyOn(diceService, 'rollDamage');
      const showRollSpy = jest.spyOn(rollToastService, 'showRoll');

      const action: MonsterAction = {
        name: 'Greatclub',
        damage_dice: '2d8+4',
        damage_type: 'bludgeoning',
      };
      component.rollDamage(action);

      expect(rollDamageSpy).toHaveBeenCalledWith([{ label: 'Greatclub (bludgeoning)', notation: '2d8+4' }]);
      expect(showRollSpy).toHaveBeenCalledWith(
        expect.objectContaining({
          title: '💥 OGRE — GREATCLUB DAMAGE',
          damageParts: expect.arrayContaining([
            expect.objectContaining({ label: 'Greatclub (bludgeoning)' }),
          ]),
        })
      );
    });

    it('handles flat damage rolls safely', () => {
      component.combatant = {
        id: 'c1',
        name: 'Cat',
        initiative: 12,
        hp: 2,
        max_hp: 2,
        ac: 12,
        dex: 15,
        is_player: false,
        conditions: [],
      };

      const showRollSpy = jest.spyOn(rollToastService, 'showRoll');
      component.rollDamage({ name: 'Claws', damage_dice: '1', damage_type: 'slashing' });

      expect(showRollSpy).toHaveBeenCalledWith(
        expect.objectContaining({
          title: '💥 CAT — CLAWS DAMAGE',
          total: 1,
        })
      );
    });

    it('does nothing when damage dice cannot be resolved', () => {
      component.combatant = {
        id: 'c1',
        name: 'Wolf',
        initiative: 10,
        hp: 11,
        max_hp: 11,
        ac: 13,
        dex: 15,
        is_player: false,
        conditions: [],
      };
      const rollDamageSpy = jest.spyOn(diceService, 'rollDamage');
      component.rollDamage({ name: 'Howl', description: 'Howls loudly.' });
      expect(rollDamageSpy).not.toHaveBeenCalled();
    });
  });

  describe('DOM Rendering & Interactivity', () => {
    afterEach(() => {
      // Clean up any dialogs after each test
      component.open = false;
      fixture.detectChanges();
    });

    it('renders structured monster view with ability scores, traits, and action roll buttons', () => {
      component.open = true;
      component.partyMember = null;
      component.combatant = {
        id: 'c1',
        name: 'Bugbear',
        initiative: 11,
        hp: 27,
        max_hp: 27,
        ac: 16,
        dex: 14,
        cr: '1',
        size: 'Medium',
        is_player: false,
        conditions: [],
        stats: { str: 15, dex: 14, con: 13, int: 8, wis: 11, cha: 9 },
        traits: [{ name: 'Surprise Attack', description: 'Extra 2d6 damage on surprise turn.' }],
        actions: [{
          name: 'Morningstar',
          attack_bonus: 4,
          damage_dice: '2d8+2',
          damage_type: 'piercing',
          description: 'Melee Weapon Attack: +4 to hit. Hit: 11 (2d8 + 2) piercing damage.',
        }],
      };

      fixture.detectChanges();

      const overlay = document.body;
      expect(overlay.textContent).toContain('AC: 16');
      expect(overlay.textContent).toContain('HP: 27');
      expect(overlay.textContent).toContain('STR');
      expect(overlay.textContent).toContain('+2'); // STR 15 mod
      expect(overlay.textContent).toContain('Traits');
      expect(overlay.textContent).toContain('Surprise Attack.');
      expect(overlay.textContent).toContain('Actions');
      expect(overlay.textContent).toContain('Morningstar');
      expect(overlay.textContent).toContain('+4 to Hit');
      expect(overlay.textContent).toContain('2d8+2 Damage');

      // Test attack roll click
      const rollAttackSpy = jest.spyOn(component, 'rollAttack');
      const attackBtn = overlay.querySelector('button[tone="accent"]') as HTMLButtonElement;
      expect(attackBtn).toBeTruthy();
      attackBtn.click();
      expect(rollAttackSpy).toHaveBeenCalledWith(component.combatant.actions![0]);

      // Test damage roll click
      const rollDamageSpy = jest.spyOn(component, 'rollDamage');
      const damageBtn = overlay.querySelector('button[tone="danger"]') as HTMLButtonElement;
      expect(damageBtn).toBeTruthy();
      damageBtn.click();
      expect(rollDamageSpy).toHaveBeenCalledWith(component.combatant.actions![0]);
    });

    it('renders fallback text statblock when actions array is empty', () => {
      component.open = true;
      component.partyMember = null;
      component.combatant = {
        id: 'c1',
        name: 'Legacy Monster',
        initiative: 10,
        hp: 15,
        max_hp: 15,
        ac: 12,
        dex: 10,
        is_player: false,
        conditions: [],
        actions: [],
        statblock: 'Armor Class 12\nHit Points 15\nSpeed 30 ft.',
      };

      fixture.detectChanges();

      const overlay = document.body;
      expect(overlay.textContent).toContain('Armor Class 12\nHit Points 15\nSpeed 30 ft.');
      expect(overlay.querySelector('button[tone="accent"]')).toBeNull();
      expect(overlay.querySelector('button[tone="danger"]')).toBeNull();
    });

    it('renders party member view when partyMember input is provided', () => {
      component.open = true;
      component.partyMember = {
        char_id: 'p1',
        name: 'Gimli',
        char_class: 'Fighter',
        level: 5,
        hp_current: 45,
        hp_max: 50,
        ac: 18,
        conditions: [],
        stats: { STR: 18, DEX: 12, CON: 16, INT: 10, WIS: 12, CHA: 8 },
      };
      component.combatant = {
        id: 'c1',
        char_id: 'p1',
        name: 'Gimli',
        initiative: 14,
        hp: 45,
        max_hp: 50,
        ac: 18,
        dex: 12,
        is_player: true,
        conditions: [],
      };

      fixture.detectChanges();

      const overlay = document.body;
      expect(overlay.textContent).toContain('Fighter Level 5');
      expect(overlay.textContent).toContain('HP: 45/50');
      expect(overlay.textContent).toContain('AC: 18');
      expect(overlay.querySelector('button[tone="accent"]')).toBeNull();
    });

    it('emits closed event when Close button is clicked', () => {
      component.open = true;
      component.combatant = {
        id: 'c1',
        name: 'Goblin',
        initiative: 10,
        hp: 7,
        max_hp: 7,
        ac: 15,
        dex: 14,
        is_player: false,
        conditions: [],
      };

      fixture.detectChanges();

      const closedSpy = jest.spyOn(component.closed, 'emit');
      const closeButtons = document.body.querySelectorAll('button');
      const closeBtn = Array.from(closeButtons).find((b) => b.textContent?.trim() === 'Close');
      expect(closeBtn).toBeTruthy();
      closeBtn!.click();

      expect(closedSpy).toHaveBeenCalled();
    });

    it('emits viewBeyond event when View on D&D Beyond button is clicked', () => {
      component.open = true;
      component.partyMember = null;
      component.combatant = {
        id: 'c1',
        name: 'Ancient Red Dragon',
        initiative: 10,
        hp: 546,
        max_hp: 546,
        ac: 22,
        dex: 10,
        is_player: false,
        conditions: [],
      };

      fixture.detectChanges();

      const viewBeyondSpy = jest.spyOn(component.viewBeyond, 'emit');
      const buttons = document.body.querySelectorAll('button');
      const beyondBtn = Array.from(buttons).find((b) => b.textContent?.includes('D&D Beyond'));
      expect(beyondBtn).toBeTruthy();
      beyondBtn!.click();

      expect(viewBeyondSpy).toHaveBeenCalledWith('Ancient Red Dragon');
    });
  });
});
