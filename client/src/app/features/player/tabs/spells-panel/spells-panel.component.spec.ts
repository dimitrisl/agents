import { ComponentFixture, TestBed } from '@angular/core/testing';
import { SpellsPanelComponent } from './spells-panel.component';
import { CharacterSchema } from '../../../../core/models/character.model';
import { HapticsService } from '../../../../core/services/haptics.service';
import { RollToastService } from '../../../../core/services/roll-toast.service';

describe('SpellsPanelComponent', () => {
  let component: SpellsPanelComponent;
  let fixture: ComponentFixture<SpellsPanelComponent>;

  const mockChar: CharacterSchema = {
    char_id: 'wizard-char',
    char_name: 'Gondorff',
    char_class: 'Wizard',
    char_level: 5,
    race: 'Human',
    background: 'Sage',
    armor_class: 12,
    hp_max: 30,
    proficiency_bonus: 3,
    speed: 30,
    stats: { STR: 8, DEX: 14, CON: 14, INT: 18, WIS: 12, CHA: 10 },
    spells: {
      cantrips: ['Fire Bolt', 'Mage Hand', 'Light'],
      level_1: ['Magic Missile', 'Shield', 'Detect Magic'],
      level_2: ['Misty Step', 'Scorching Ray'],
      level_3: ['Fireball'],
    },
    prepared_spells: ['Fire Bolt', 'Magic Missile', 'Shield', 'Misty Step', 'Fireball'],
    spell_slots: {
      '1': { max: 4, used: 1 },
      '2': { max: 3, used: 0 },
      '3': { max: 2, used: 2 },
    },
    class_resources: [
      { name: 'Arcane Recovery', current: 1, max: 1, recharge: 'short' },
    ],
  };

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [SpellsPanelComponent],
      providers: [HapticsService, RollToastService],
    }).compileComponents();

    fixture = TestBed.createComponent(SpellsPanelComponent);
    component = fixture.componentInstance;
    component.char = JSON.parse(JSON.stringify(mockChar));
    component.getSpellSlotMax = (lvl: number) => component.char.spell_slots?.[String(lvl)]?.max ?? 0;
    component.getSpellSlotUsed = (lvl: number) => component.char.spell_slots?.[String(lvl)]?.used ?? 0;
    fixture.detectChanges();
  });

  it('should create and calculate spell slot remaining', () => {
    expect(component).toBeTruthy();
    expect(component.slotsRemaining(1)).toBe(3);
    expect(component.slotsRemaining(2)).toBe(3);
    expect(component.slotsRemaining(3)).toBe(0);
  });

  it('should filter spells by search query and prepared pill', () => {
    expect(component.filteredSpellGroups.length).toBeGreaterThan(0);

    // Search query
    component.searchQuery.set('Fire');
    const filtered = component.filteredSpellGroups;
    const allFilteredSpells = filtered.flatMap(g => g.spells);
    expect(allFilteredSpells).toContain('Fire Bolt');
    expect(allFilteredSpells).toContain('Fireball');
    expect(allFilteredSpells).not.toContain('Shield');

    // Filter prepared only
    component.searchQuery.set('');
    component.selectedFilter.set('prepared');
    const preparedSpells = component.filteredSpellGroups.flatMap(g => g.spells);
    expect(preparedSpells).toContain('Shield');
    expect(preparedSpells).not.toContain('Detect Magic');
  });

  it('should cast cantrips for free without expending slot', () => {
    const castSpy = jest.spyOn(component.castSpell, 'emit');
    const slotSpy = jest.spyOn(component.useSpellSlot, 'emit');

    component.castNow('Fire Bolt', 0, new MouseEvent('click'));
    expect(castSpy).toHaveBeenCalledWith({ spellName: 'Fire Bolt', level: 0, isRitual: false });
    expect(slotSpy).not.toHaveBeenCalled();
  });

  it('casts with one click, spending the lowest open slot, without opening a dialog', () => {
    const castSpy = jest.spyOn(component.castSpell, 'emit');
    const slotSpy = jest.spyOn(component.useSpellSlot, 'emit');

    // Magic Missile (level 1): level 1 still has slots, so it is used
    component.castNow('Magic Missile', 1, new MouseEvent('click'));
    expect(slotSpy).toHaveBeenCalledWith(1);
    expect(castSpy).toHaveBeenCalledWith({ spellName: 'Magic Missile', level: 1, isRitual: false });
    expect(component.upcastTarget()).toBeNull();
  });

  it('refuses to cast and says so when no slot of that level or higher is left', () => {
    const castSpy = jest.spyOn(component.castSpell, 'emit');
    const toastSpy = jest.spyOn((component as any).toast, 'showMessage');
    component.castNow('Wish', 9, new MouseEvent('click'));
    expect(castSpy).not.toHaveBeenCalled();
    expect(toastSpy).toHaveBeenCalledWith('⚠️ NO SPELL SLOTS', expect.stringContaining('Wish'));
  });

  it('the ▾ opens the slot picker for upcasting, which spends the chosen slot', () => {
    component.openCastOptions('Magic Missile', 1, new MouseEvent('click'));
    expect(component.upcastTarget()).toEqual({ spellName: 'Magic Missile', baseLevel: 1 });

    const castSpy = jest.spyOn(component.castSpell, 'emit');
    const slotSpy = jest.spyOn(component.useSpellSlot, 'emit');
    component.confirmUpcast(2);
    expect(slotSpy).toHaveBeenCalledWith(2);
    expect(castSpy).toHaveBeenCalledWith({ spellName: 'Magic Missile', level: 2, isRitual: false });
    expect(component.upcastTarget()).toBeNull();
  });

  it('a Sorcerer can add Metamagic in the cast window, priced by the slot for 2014 Twinned', () => {
    component.char = {
      ...component.char,
      char_class: 'Sorcerer',
      classes: [{ class_name: 'Sorcerer', level: 5 }],
      dnd_edition: '2014 Edition',
      features_traits: [
        { name: 'Metamagic: Careful Spell', description: '' },
        { name: 'Metamagic: Twinned Spell', description: '' },
      ],
      class_resources: [{ name: 'Sorcery Points', current: 3, max: 5, recharge: 'long', auto: true }],
    };
    component.openCastOptions('Fireball', 1, new MouseEvent('click'));
    const [careful, twinned] = component.knownMetamagicOptions;

    component.toggleCastMetamagic(careful);
    expect(component.castMetamagicCost(2)).toBe(1);
    expect(component.canAddCastMetamagic(twinned, 1)).toBe(true);
    component.toggleCastMetamagic(twinned);
    expect(component.castMetamagicCost(2)).toBe(3); // Careful 1 + Twinned at 2nd level 2
    expect(component.canPayCastMetamagic(2)).toBe(true);
    expect(component.canPayCastMetamagic(3)).toBe(false); // 1 + 3 > 3 points

    const castSpy = jest.spyOn(component.castSpell, 'emit');
    component.confirmUpcast(2);
    expect(castSpy).toHaveBeenCalledWith({
      spellName: 'Fireball',
      level: 2,
      isRitual: false,
      metamagic: ['careful', 'twinned'],
    });
    expect(component.castMetamagic()).toEqual([]);
  });

  it('edits a rules pool through an adjustment on top of the class max', () => {
    component.char = {
      ...component.char,
      class_resources: [{ name: 'Sorcery Points', current: 5, max: 10, recharge: 'long', auto: true, bonus: 2 }],
    };
    const saveSpy = jest.spyOn(component.save, 'emit');
    component.openEditResource(0, new MouseEvent('click'));
    expect(component.resourceRulesMax).toBe(8);

    component.newResourceBonus = -1;
    component.newResourceCurrent = 99;
    component.newResourceRecharge = 'short'; // ignored: the rules own recharge
    component.confirmAddResource();

    expect(component.char.class_resources![0]).toEqual({
      name: 'Sorcery Points',
      current: 7,
      max: 7,
      recharge: 'long',
      auto: true,
      bonus: -1,
    });
    expect(saveSpy).toHaveBeenCalled();
    expect(component.showAddResourceModal()).toBe(false);
  });

  it('edits every field of a hand-made pool', () => {
    component.openEditResource(0, new MouseEvent('click'));
    component.newResourceName = 'Luck Points';
    component.newResourceMax = 3;
    component.newResourceCurrent = 2;
    component.newResourceRecharge = 'long';
    component.confirmAddResource();
    expect(component.char.class_resources![0]).toEqual({ name: 'Luck Points', current: 2, max: 3, recharge: 'long' });
  });

  it('should manipulate class resource counters', () => {
    const saveSpy = jest.spyOn(component.save, 'emit');
    const res = component.classResources[0];
    expect(res.current).toBe(1);

    component.decrementResource(res, new MouseEvent('click'));
    expect(res.current).toBe(0);
    expect(saveSpy).toHaveBeenCalled();

    component.incrementResource(res, new MouseEvent('click'));
    expect(res.current).toBe(1);
  });

  it('Expand all opens only features that have text; name-only ones have nothing to open', () => {
    component.char.features_traits = [
      { name: 'Metamagic Adept', description: 'You learn two Metamagic options.' },
      { name: 'Resilient', description: '' },
      { name: 'Font of Magic', description: 'You have sorcery points.' },
    ];
    expect(component.hasDetails(component.features[1])).toBe(false);

    component.toggleAllFeatures();
    expect(component.isFeatureExpanded(0)).toBe(true);
    expect(component.isFeatureExpanded(1)).toBe(false);
    expect(component.isFeatureExpanded(2)).toBe(true);
    expect(component.allFeaturesExpanded).toBe(true);

    component.toggleAllFeatures();
    expect(component.isFeatureExpanded(0)).toBe(false);
  });
});
