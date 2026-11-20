import { SimpleChange } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { of, throwError } from 'rxjs';
import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting } from '@angular/common/http/testing';
import { CombatPanelComponent } from './combat-panel.component';
import { CharacterSchema } from '../../../../core/models/character.model';
import { DiceService } from '../../../../core/services/dice.service';
import { RollToastService } from '../../../../core/services/roll-toast.service';
import { ClassCombatService } from '../../../../core/services/class-combat.service';

describe('CombatPanelComponent', () => {
  let component: CombatPanelComponent;
  let fixture: ComponentFixture<CombatPanelComponent>;
  let toast: RollToastService;

  const mockChar: CharacterSchema = {
    char_id: 'test-char',
    char_name: 'Thorin',
    char_class: 'Fighter',
    char_level: 5,
    race: 'Dwarf',
    background: 'Soldier',
    armor_class: 18,
    hp_max: 45,
    proficiency_bonus: 3,
    speed: 25,
    stats: { STR: 18, DEX: 10, CON: 16, INT: 10, WIS: 12, CHA: 8 },
    currency: { cp: 10, sp: 50, ep: 0, gp: 120, pp: 1 },
    equipment: [
      { name: 'Potion of Healing', quantity: 2, equipped: false },
      { name: 'Cloak of Protection', equipped: true, attuned: true },
      { name: 'Ring of Warmth', equipped: true, attuned: true },
    ],
    weapons: [
      { name: 'Battleaxe', attack_bonus: '+7', damage_dice: '1d8+4 slashing' },
    ],
  };

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [CombatPanelComponent],
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        DiceService,
        RollToastService,
        ClassCombatService,
      ],
    }).compileComponents();

    fixture = TestBed.createComponent(CombatPanelComponent);
    component = fixture.componentInstance;
    component.char = JSON.parse(JSON.stringify(mockChar));
    toast = TestBed.inject(RollToastService);
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
    expect(component.currency.gp).toBe(120);
  });

  it('should add coins and spend coins correctly', () => {
    const saveSpy = jest.spyOn(component.save, 'emit');
    component.openCoinModal('gp');
    expect(component.showCoinModal).toBe(true);

    component.addCoinPill(50);
    component.executeAddCoins();
    expect(component.currency.gp).toBe(170);
    expect(saveSpy).toHaveBeenCalled();
    expect(component.showCoinModal).toBe(false);

    component.openCoinModal('gp');
    component.addCoinPill(30);
    component.executeSpendCoins();
    expect(component.currency.gp).toBe(140);
  });

  it('should block spending more coins than available', () => {
    const toastSpy = jest.spyOn(toast, 'showMessage');
    component.openCoinModal('gp');
    component.addCoinPill(999);
    component.executeSpendCoins();

    expect(toastSpy).toHaveBeenCalledWith('⚠️ INSUFFICIENT COINS', expect.any(String));
    expect(component.currency.gp).toBe(120);
  });

  it('should cap attuned AND equipped items at 3, not attunement itself', () => {
    const toastSpy = jest.spyOn(toast, 'showMessage');
    const saveSpy = jest.spyOn(component.save, 'emit');
    const equipSpy = jest.spyOn(component.toggleEquipped, 'emit');

    expect(component.attunedCount).toBe(2);

    // 3rd attuned + equipped item fills the limit
    const item3 = { name: 'Boots of Speed', attuned: false, equipped: true };
    component.char.equipment?.push(item3);
    component.toggleAttuned(item3);
    expect(item3.attuned).toBe(true);
    expect(component.attunedCount).toBe(3);
    expect(saveSpy).toHaveBeenCalled();

    // Attuning an item kept in the inventory is allowed and doesn't count
    const item4 = { name: 'Amulet of Health', attuned: false, equipped: false };
    component.char.equipment?.push(item4);
    component.toggleAttuned(item4);
    expect(item4.attuned).toBe(true);
    expect(component.attunedCount).toBe(3);

    // ...but equipping it would make 4 active, so it is blocked
    component.onToggleEquipped(item4);
    expect(equipSpy).not.toHaveBeenCalled();
    expect(toastSpy).toHaveBeenCalledWith('🔮 ATTUNEMENT LIMIT', expect.any(String));

    // Attuning a 4th item that is already equipped is blocked too
    const item5 = { name: 'Ring of Protection', attuned: false, equipped: true };
    component.char.equipment?.push(item5);
    component.toggleAttuned(item5);
    expect(item5.attuned).toBe(false);

    // Unequipping an attuned item is always allowed
    component.onToggleEquipped(item3);
    expect(equipSpy).toHaveBeenCalledWith(item3);
  });

  it('should detect healing potions and emit consumePotion', () => {
    const consumeSpy = jest.spyOn(component.consumePotion, 'emit');
    const potionItem = component.char.equipment![0];

    expect(component.isHealingPotion(potionItem)).toBe(true);
    component.drinkPotion(potionItem, new MouseEvent('click'));

    expect(consumeSpy).toHaveBeenCalledWith({
      item: potionItem,
      dice: '2d4',
      bonus: 2,
      name: 'Potion of Healing',
    });
  });

  it('recognises sheet-style potion names and uses the dice written on them', () => {
    const consumeSpy = jest.spyOn(component.consumePotion, 'emit');
    const greater = { name: 'Greater Healing Potion 4d4 + 4', quantity: 3 };
    const superior = { name: 'Superior healing Potion', quantity: 1 };

    expect(component.isHealingPotion(greater)).toBe(true);
    expect(component.isHealingPotion({ name: 'Potion of Water Breathing' })).toBe(false);

    component.drinkPotion(greater, new MouseEvent('click'));
    expect(consumeSpy).toHaveBeenLastCalledWith(expect.objectContaining({ dice: '4d4', bonus: 4 }));

    component.drinkPotion(superior, new MouseEvent('click'));
    expect(consumeSpy).toHaveBeenLastCalledWith(expect.objectContaining({ dice: '8d4', bonus: 8 }));
  });

  it('should adjust quantity on item', () => {
    const saveSpy = jest.spyOn(component.save, 'emit');
    const item = component.char.equipment![0];
    expect(item.quantity).toBe(2);

    component.adjustQuantity(item, 1, new MouseEvent('click'));
    expect(item.quantity).toBe(3);
    expect(saveSpy).toHaveBeenCalled();

    component.adjustQuantity(item, -2, new MouseEvent('click'));
    expect(item.quantity).toBe(1);
  });

  it('should toggle weapon editor and calculate breakdown', () => {
    expect(component.expandedWeaponIndex).toBeNull();
    component.toggleWeaponEditor(0);
    expect(component.expandedWeaponIndex).toBe(0);

    const weapon = component.char.weapons![0];
    const bd = component.getWeaponBreakdown(weapon);
    expect(bd.attack.statName).toBe('STR');
    expect(bd.attack.statMod).toBe(4);
    expect(bd.attack.total).toBe(7); // STR (+4) + Prof (+3)
    expect(bd.attack.formulaText).toContain('STR (+4) + Prof (+3)');
  });

  it('crit sends every doubled die with its own size, flagged as a critical hit', () => {
    const weapon: any = component.char.weapons![0]; // 1d8+4 slashing
    weapon.conditional_effects = [{ label: 'Love Poison', dice: '3d8' }, { label: 'vs Undead', dice: '1d6' }];
    component.toggleEffect(weapon, weapon.conditional_effects[0]);
    component.toggleEffect(weapon, weapon.conditional_effects[1]);

    component.rollWeaponDamage(weapon, true);

    const shown = toast.activeRoll()!;
    // 1d8 -> 2d8, 3d8 -> 6d8, 1d6 -> 2d6: ten dice, none dropped
    expect(shown.rolls?.length).toBe(10);
    expect(shown.diceSides).toEqual([8, 8, 8, 8, 8, 8, 8, 8, 6, 6]);
    expect(shown.isCritHit).toBe(true);
  });

  it('marks save-for-half parts on the damage roll, read from the effect or a same-named note', () => {
    const weapon: any = component.char.weapons![0];
    const poison = { label: 'Love Poison', dice: '3d8' };
    weapon.conditional_effects = [
      poison,
      { label: 'Love Poison ', note: 'DC 16 CON half damage' }, // note-only twin, trailing space
      { label: 'vs Undead', dice: '1d6' },
    ];
    component.toggleEffect(weapon, poison);
    component.toggleEffect(weapon, weapon.conditional_effects[2]);

    component.rollWeaponDamage(weapon);
    const parts = toast.activeRoll()!.damageParts!;
    expect(parts.map((p) => p.label)).toEqual(['Battleaxe', 'Love Poison', 'vs Undead']);
    expect(parts[0].saveHalf).toBeUndefined();
    expect(parts[1].saveHalf).toEqual({ dc: 'DC 16 CON' });
    expect(parts[2].saveHalf).toBeUndefined();
    expect(parts[1].detail).toMatch(/^3d8 \(/);
  });

  it('an effect without a "half" note offers no save button', () => {
    const weapon: any = component.char.weapons![0];
    const poison = { label: 'Wyvern Poison', dice: '7d6', note: 'DC 15 CON' };
    weapon.conditional_effects = [poison];
    expect(component.saveHalfInfo(weapon, poison)).toBeNull();
    poison.note = 'DC 15 CON, half on a save';
    expect(component.saveHalfInfo(weapon, poison)).toEqual({ dc: 'DC 15 CON' });
  });

  it('editing the dice of an active effect keeps it switched on', () => {
    const weapon: any = component.char.weapons![0];
    const effect = { label: 'vs Undead', dice: '1d6' };
    weapon.conditional_effects = [effect];
    component.toggleEffect(weapon, effect);
    component.onEffectChange(weapon, effect, 'dice', '2d6');
    expect(component.isEffectActive(weapon, effect)).toBe(true);
  });

  it('a normal damage roll is not flagged as a crit', () => {
    component.rollWeaponDamage(component.char.weapons![0]);
    expect(toast.activeRoll()!.isCritHit).toBe(false);
  });

  describe('equipment list', () => {
    it('offers the AC written in the notes until the item has its own', () => {
      const amulet: any = {
        name: 'Arcane Focus (Amulet-Crystal)',
        equipped: true,
        description: '+2 AC attunement item (1/3 attunement slots)',
      };
      expect(component.acHintFromNotes(amulet)).toBe(2);
      component.onItemAcChange(amulet, component.acHintFromNotes(amulet));
      expect(amulet.ac_bonus).toBe(2);
      expect(component.acHintFromNotes(amulet)).toBeNull();
      expect(component.acHintFromNotes({ name: 'Rope', description: '50 ft of hempen rope' })).toBeNull();
    });

    it('sets the AC of an item from Quick Edit and saves so the server recalculates AC', () => {
      const saveSpy = jest.spyOn(component.save, 'emit');
      const amulet: any = { name: 'Arcane Focus (Amulet-Crystal)', equipped: true };

      component.onItemAcChange(amulet, '2');
      expect(amulet.ac_bonus).toBe(2);
      expect(saveSpy).toHaveBeenCalled();

      component.onItemAcChange(amulet, '');
      expect(amulet.ac_bonus).toBe(0);
      component.onItemAcChange(amulet, '-3');
      expect(amulet.ac_bonus).toBe(0);
    });

    // mockChar: [0] Potion (pack), [1] Cloak (equipped, attuned), [2] Ring (equipped, attuned)
    it('groups Equipped first, then Inventory, keeping each original index', () => {
      const groups = component.equipmentGroups;
      expect(groups.map((g) => g.title)).toEqual(['Equipped', 'Inventory']);
      expect(groups[0].rows.map((r) => r.index)).toEqual([1, 2]);
      expect(groups[1].rows.map((r) => [r.item.name, r.index])).toEqual([['Potion of Healing', 0]]);
    });

    it('filters and counts', () => {
      expect(component.equipmentCount('all')).toBe(3);
      expect(component.equipmentCount('equipped')).toBe(2);
      expect(component.equipmentCount('attuned')).toBe(2);
      expect(component.equipmentCount('inventory')).toBe(1);

      component.equipmentFilter = 'inventory';
      const [only] = component.equipmentGroups;
      expect(only.title).toBeNull();
      expect(only.rows.map((r) => r.item.name)).toEqual(['Potion of Healing']);
    });
  });

  it('shows only the formula sources under the big to-hit / damage numbers', () => {
    expect(component.formulaSources('DEX (+5) + Prof (+4) + Magic (+2) = +11')).toBe('DEX (+5) + Prof (+4) + Magic (+2)');
    expect(component.formulaSources('1d6 +5 (DEX) +2 (Magic) = 1d6+7 piercing')).toBe('1d6 +5 (DEX) +2 (Magic)');
    expect(component.formulaSources('+9')).toBe('+9');
  });

  describe('class riders (combat profile)', () => {
    const sneakAttack = {
      id: 'sneak-attack',
      name: 'Sneak Attack',
      icon: '🗡️',
      kind: 'rider',
      notation: '6d6',
      hint: '',
      source: 'Rogue 11',
      rollable: true,
    } as any;
    const rogueProfile = { actions: [sneakAttack], extraCritDice: 0, critThreshold: 20, cantripTier: 3 };

    function changeChar(next: any) {
      component.char = next;
      component.ngOnChanges({ char: new SimpleChange(null, next, false) });
    }

    it('does not refetch on a plain save, and keeps Sneak Attack when a refetch fails', () => {
      const combat = TestBed.inject(ClassCombatService);
      const getProfile = jest.spyOn(combat, 'getProfile').mockReturnValue(of(rogueProfile));

      changeChar({ ...component.char, char_class: 'Rogue', char_level: 11 });
      expect(component.riders.map((r) => r.id)).toEqual(['sneak-attack']);
      const calls = getProfile.mock.calls.length;

      // A save returns a new object with the same class/level: no new request.
      changeChar({ ...component.char, hp_current: 10 });
      expect(getProfile.mock.calls.length).toBe(calls);
      expect(component.riders.map((r) => r.id)).toEqual(['sneak-attack']);

      // Level up triggers a refetch; if it fails, the riders stay.
      jest.spyOn(console, 'warn').mockImplementation(() => {});
      getProfile.mockReturnValue(throwError(() => new Error('429')));
      changeChar({ ...component.char, char_level: 12 });
      expect(component.riders.map((r) => r.id)).toEqual(['sneak-attack']);
    });
  });

  describe('situational weapon effects', () => {
    let weapon: any;

    beforeEach(() => {
      weapon = component.char.weapons![0];
      weapon.conditional_effects = [
        { label: 'vs Undead', dice: '1d6', damage_type: 'radiant' },
        { label: 'vs Chaotic', damage_bonus: 2, attack_bonus: 2 },
        { label: 'vs Vampires', note: 'Instant death on a finishing hit' },
      ];
    });

    it('stay off until switched on, and note-only effects never roll', () => {
      const [undead, chaotic, vampires] = weapon.conditional_effects;
      expect(component.activeEffects(weapon)).toEqual([]);
      expect(component.isEffectRollable(vampires)).toBe(false);

      component.toggleEffect(weapon, undead);
      component.toggleEffect(weapon, vampires);
      expect(component.activeEffects(weapon)).toEqual([undead]);
      expect(component.effectSummary(undead)).toBe('+1d6 radiant');
      expect(component.effectSummary(chaotic)).toBe('+2 dmg · +2 hit');
    });

    it('add their dice to damage and their bonus to attack when on', () => {
      const [undead, chaotic] = weapon.conditional_effects;
      const baseHit = component.displayedAttackBonus(weapon);

      component.toggleEffect(weapon, undead);
      component.toggleEffect(weapon, chaotic);

      expect(component.damagePreview(weapon)).toBe('1d8+4 + 1d6 +2');
      expect(parseInt(component.displayedAttackBonus(weapon), 10)).toBe(parseInt(baseHit, 10) + 2);
    });

    it('keep the on state when an effect is renamed', () => {
      const [undead] = weapon.conditional_effects;
      component.toggleEffect(weapon, undead);
      component.onEffectChange(weapon, undead, 'label', 'vs Undead & Fiends');
      expect(component.isEffectActive(weapon, undead)).toBe(true);
    });
  });

  it('should ignore half-typed base dice and commit a complete one', () => {
    const saveSpy = jest.spyOn(component.save, 'emit');
    const weapon = component.char.weapons![0];
    const before = weapon.damage_dice;

    component.onWeaponBaseDiceChange(weapon, '1');
    component.onWeaponBaseDiceChange(weapon, '1d');
    expect(weapon.damage_dice).toBe(before);
    expect(saveSpy).not.toHaveBeenCalled();

    component.onWeaponBaseDiceChange(weapon, '1d6');
    expect(component.getWeaponBaseDice(weapon)).toBe('1d6');
    expect(saveSpy).toHaveBeenCalledTimes(1);
  });

  it('should sync weapon calculations to sheet and emit save', () => {
    const saveSpy = jest.spyOn(component.save, 'emit');
    const weapon = component.char.weapons![0];

    component.syncWeaponCalculations(weapon);

    expect(weapon.attack_bonus).toBe('+7');
    expect(weapon.damage_dice).toBe('1d8+4 slashing');
    expect(weapon.damage_bonus).toBe('+4');
    expect(saveSpy).toHaveBeenCalled();
  });

  it('should display calculated attack bonus and handle manual adjustments', () => {
    const saveSpy = jest.spyOn(component.save, 'emit');
    const weapon = component.char.weapons![0];

    // Initial breakdown: STR (+4) + Prof (+3) = +7
    expect(component.displayedAttackBonus(weapon)).toBe('+7');

    // Simulate player manual override to +9 in edit mode
    weapon.attack_bonus = '+9';
    component.onManualAttackBonusChange(weapon);

    expect(weapon.misc_attack_bonus).toBe(2);
    expect(component.displayedAttackBonus(weapon)).toBe('+9');
    expect(saveSpy).toHaveBeenCalled();
  });

  it('does not treat redacted enemy combatants with hp null as Down unless health_status is down', () => {
    const healthyMonster = { id: 'm1', name: 'Goblin', hp: null, max_hp: null, health_status: 'healthy' };
    const bloodiedMonster = { id: 'm2', name: 'Orc', hp: null, max_hp: null, health_status: 'bloodied' };
    const downMonster = { id: 'm3', name: 'Kobold', hp: null, max_hp: null, health_status: 'down' };
    const zeroHpNpc = { id: 'a1', name: 'Scout', hp: 0, max_hp: 16 };

    expect(component.isCombatantDown(healthyMonster)).toBe(false);
    expect(component.isCombatantBloodied(healthyMonster)).toBe(false);

    expect(component.isCombatantDown(bloodiedMonster)).toBe(false);
    expect(component.isCombatantBloodied(bloodiedMonster)).toBe(true);

    expect(component.isCombatantDown(downMonster)).toBe(true);
    expect(component.isCombatantDown(zeroHpNpc)).toBe(true);
  });

  it('scales getToppleDc with the weapon scaling ability instead of always using STR', () => {
    component.char = {
      ...component.char,
      proficiency_bonus: 3,
      stats: { STR: 8, DEX: 14, CON: 12, INT: 10, WIS: 12, CHA: 20 }, // CHA +5, STR -1
    } as any;
    const chaMaul = {
      name: 'Pact Maul',
      ability_modifier: 'CHA',
      mastery: 'Topple',
    };
    // 8 + PB (3) + CHA (+5) = 16
    expect(component.getToppleDc(chaMaul)).toBe(16);
  });

  it('non-destructively suppresses magic_bonus during syncWeaponCalculations when magic_items_suppressed is true', () => {
    component.char = {
      ...component.char,
      active_campaign: 'Athas',
      proficiency_bonus: 3,
      stats: { STR: 18, DEX: 12, CON: 14, INT: 10, WIS: 12, CHA: 10 },
      magic_items_suppressed: true,
      weapons: [
        {
          name: 'Longsword +2',
          damage: '1d8',
          magic_bonus: 2,
          attack_bonus: '+9',
          damage_bonus: '+6',
          properties: [],
        },
      ],
    } as any;

    const weapon = component.char.weapons![0];
    // STR +4 + Prof +3 (Magic +2 suppressed!) = +7 attack, +4 damage
    expect(component.displayedAttackBonus(weapon)).toBe('+7');
    expect(component.damagePreview(weapon)).toBe('1d8+4');

    component.syncWeaponCalculations(weapon, false);
    // Underlying magic_bonus field must NOT be destroyed in the weapon object
    expect(weapon.magic_bonus).toBe(2);
    expect(weapon.attack_bonus).toBe('+7');
    expect(weapon.damage_bonus).toBe('+4');

    // Lifting suppression restores +9 attack / 1d8+6 damage seamlessly
    component.char = { ...component.char, magic_items_suppressed: false };
    component.syncWeaponCalculations(weapon, false);
    expect(component.displayedAttackBonus(component.char.weapons![0])).toBe('+9');
    expect(component.damagePreview(component.char.weapons![0])).toBe('1d8+6');
  });

  it('stamps DM/suppression tracking fields on syncWeaponCalculations and preserves is_custom damage in weaponNotation', () => {
    const customSword: any = {
      name: 'Flame Tongue +1',
      is_custom: true,
      damage_dice: '2d6 slashing',
      damage_bonus: '+8',
      attack_bonus: '+10',
      magic_bonus: 1,
      dm_attack_bonus_applied: 0,
      dm_damage_bonus_applied: 0,
      magic_bonus_suppressed_applied: 0,
    };
    component.char = {
      ...component.char,
      dnd_edition: '2024 Revision (5.5e)',
      exhaustion_level: 1,
      magic_items_suppressed: true,
      dm_modifiers: { attack_bonus: 2, damage_bonus: 3 },
      weapons: [customSword],
    } as any;

    // Prior to sync: custom +10 attack + DM (+2) - Exh (2) - supMagic (1) = +9; custom +8 dmg + DM (+3) - supMagic (1) = +10
    expect(component.displayedAttackBonus(customSword)).toBe('+9');
    expect(component.damagePreview(customSword)).toBe('2d6+10');

    // Sync writes custom totals without erasing them or baking +10 into damage_dice, and stamps all 4 tracking fields
    component.syncWeaponCalculations(customSword, false);
    expect(customSword.attack_bonus).toBe('+9');
    expect(customSword.damage_bonus).toBe('+10');
    expect(customSword.damage_dice).toBe('2d6 slashing');
    expect(customSword.damage).toBe('2d6 + 10 slashing');
    expect(customSword.dm_attack_bonus_applied).toBe(2);
    expect(customSword.dm_damage_bonus_applied).toBe(3);
    expect(customSword.magic_bonus_suppressed_applied).toBe(1);
    expect(customSword.exhaustion_attack_penalty_applied).toBe(2);

    // Authoritative backend damage_bonus (+12) takes precedence even if damage_dice carries stale inline (+8)
    const staleDiceWeapon: any = {
      name: 'Flame Tongue +1',
      is_custom: true,
      damage_dice: '2d6+8 slashing',
      damage_bonus: '+12',
      attack_bonus: '+11',
      magic_bonus: 1,
      dm_attack_bonus_applied: 2,
      dm_damage_bonus_applied: 3,
      magic_bonus_suppressed_applied: 1,
      exhaustion_attack_penalty_applied: 2,
    };
    expect(component.damagePreview(staleDiceWeapon)).toBe('2d6+12');
    expect(component.displayedAttackBonus(staleDiceWeapon)).toBe('+11');
  });

  describe('Mobile Companion compactMobile mode', () => {
    beforeEach(() => {
      component.char = {
        ...JSON.parse(JSON.stringify(mockChar)),
        dnd_edition: '2024 Revision (5.5e)',
        subclass: 'Battle Master',
        weapon_masteries: ['Topple'],
        weapons: [
          {
            name: 'Battleaxe',
            attack_bonus: '+7',
            damage_dice: '1d8+4 slashing',
            properties: 'Versatile, Topple',
          },
        ],
        class_resources: [
          { name: 'Second Wind', current: 2, max: 3, recharge: 'short', auto: true },
        ],
        features_traits: [
          { name: 'Action Surge', source: 'Fighter', description: 'Take one additional action.' },
          { name: 'Dwarven Resilience', source: 'Dwarf', description: 'Resistance to poison.' },
          { name: 'Alert', source: 'Origin Feat', description: 'Add PB to initiative.' },
          { name: 'roll', source: 'Level Up', description: 'Selected for hp_method' },
        ],
      };
      fixture.componentRef.setInput('compactMobile', true);
      fixture.detectChanges();
    });

    it('renders 4 sub-pills and switches between Attacks, Actions, Inventory, and Features', () => {
      const el = fixture.nativeElement as HTMLElement;
      expect(el.querySelector('[data-testid="mobile-combat-attacks"]')).toBeTruthy();

      (el.querySelector('[data-testid="mobile-combat-subtab-actions"]') as HTMLButtonElement).click();
      fixture.detectChanges();
      expect(component.mobileCombatSubTab()).toBe('actions');
      expect(el.querySelector('[data-testid="mobile-combat-actions"]')).toBeTruthy();

      (el.querySelector('[data-testid="mobile-combat-subtab-inventory"]') as HTMLButtonElement).click();
      fixture.detectChanges();
      expect(component.mobileCombatSubTab()).toBe('inventory');
      expect(el.querySelector('[data-testid="mobile-combat-inventory"]')).toBeTruthy();

      (el.querySelector('[data-testid="mobile-combat-subtab-features"]') as HTMLButtonElement).click();
      fixture.detectChanges();
      expect(component.mobileCombatSubTab()).toBe('features');
      expect(el.querySelector('[data-testid="mobile-combat-features"]')).toBeTruthy();
    });

    it('opens Weapon Inspector sheet cleanly for index 0 and rolls attack/damage directly from compact row', () => {
      const el = fixture.nativeElement as HTMLElement;
      const atkSpy = jest.spyOn(component, 'rollAttack');
      const dmgSpy = jest.spyOn(component, 'rollWeaponDamage');

      (el.querySelector('[data-testid="mobile-weapon-atk-0"]') as HTMLButtonElement).click();
      expect(atkSpy).toHaveBeenCalledWith(component.char.weapons![0]);

      (el.querySelector('[data-testid="mobile-weapon-dmg-0"]') as HTMLButtonElement).click();
      expect(dmgSpy).toHaveBeenCalledWith(component.char.weapons![0]);

      (el.querySelector('[data-testid="mobile-weapon-row-0"]') as HTMLButtonElement).click();
      fixture.detectChanges();
      expect(component.inspectedWeaponIndex()).toBe(0);
      expect(component.inspectedWeapon?.name).toBe('Battleaxe');
      expect(component.weaponMasteryName(component.char.weapons![0])).toBe('Topple');
    });

    it('toggles class resource pips immutably and emits standard combat actions in Actions sub-tab', () => {
      const saveSpy = jest.spyOn(component.save, 'emit');
      const actionSpy = jest.spyOn(component.combatAction, 'emit');
      const el = fixture.nativeElement as HTMLElement;

      (el.querySelector('[data-testid="mobile-combat-subtab-actions"]') as HTMLButtonElement).click();
      fixture.detectChanges();

      const resBefore = component.char.class_resources![0];
      component.onResourcePipClick(resBefore, 2, new MouseEvent('click'));
      expect(component.char.class_resources![0].current).toBe(1);
      expect(component.char.class_resources![0]).not.toBe(resBefore);
      expect(saveSpy).toHaveBeenCalled();

      component.onResourcePipClick(component.char.class_resources![0], 3, new MouseEvent('click'));
      expect(component.char.class_resources![0].current).toBe(3);

      const dodgeBtn = Array.from(el.querySelectorAll('button')).find((b) => b.textContent?.includes('Dodge'));
      dodgeBtn?.click();
      expect(actionSpy).toHaveBeenCalledWith('Dodge');
    });

    it('filters synthetic level-up entries and filters features by source pills', () => {
      expect(component.features.map((f) => f.name)).toEqual(['Action Surge', 'Dwarven Resilience', 'Alert']);

      component.mobileFeatureFilter.set('species');
      expect(component.filteredMobileFeatures.map((f) => f.name)).toEqual(['Dwarven Resilience']);

      component.mobileFeatureFilter.set('feat');
      expect(component.filteredMobileFeatures.map((f) => f.name)).toEqual(['Alert']);

      component.mobileFeatureFilter.set('class');
      expect(component.filteredMobileFeatures.map((f) => f.name)).toEqual(['Action Surge']);

      component.openFeatureInspector(component.features[0]);
      expect(component.inspectedFeature()?.name).toBe('Action Surge');
    });

    it('opens Item Inspector sheet cleanly for index 0 in Inventory sub-tab', () => {
      const el = fixture.nativeElement as HTMLElement;
      (el.querySelector('[data-testid="mobile-combat-subtab-inventory"]') as HTMLButtonElement).click();
      fixture.detectChanges();

      (el.querySelector('[data-testid="mobile-item-row-0"]') as HTMLButtonElement).click();
      fixture.detectChanges();
      expect(component.inspectedItemIndex()).toBe(0);
      expect(component.inspectedItem?.name).toBe('Potion of Healing');
    });
  });
});
