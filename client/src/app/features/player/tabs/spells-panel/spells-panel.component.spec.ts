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

    component.initiateCast('Fire Bolt', 0, new MouseEvent('click'));
    expect(castSpy).toHaveBeenCalledWith({ spellName: 'Fire Bolt', level: 0, isRitual: false });
    expect(slotSpy).not.toHaveBeenCalled();
  });

  it('should trigger upcast dialog when multiple slots are available', () => {
    // Magic Missile (level 1): slots available at level 1 and 2
    component.initiateCast('Magic Missile', 1, new MouseEvent('click'));
    expect(component.upcastTarget()).toEqual({ spellName: 'Magic Missile', baseLevel: 1 });

    const castSpy = jest.spyOn(component.castSpell, 'emit');
    const slotSpy = jest.spyOn(component.useSpellSlot, 'emit');

    // Confirm upcast at level 2
    component.confirmUpcast(2);
    expect(slotSpy).toHaveBeenCalledWith(2);
    expect(castSpy).toHaveBeenCalledWith({ spellName: 'Magic Missile', level: 2, isRitual: false });
    expect(component.upcastTarget()).toBeNull();
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
});
