import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting } from '@angular/common/http/testing';
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
      providers: [provideHttpClient(), provideHttpClientTesting(), HapticsService, RollToastService],
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

  it('displays Warlock Pact Magic summary and per-level short rest indicator for Sorcerer 5 / Warlock 3', () => {
    component.char = {
      ...mockChar,
      char_class: 'Sorcerer',
      char_level: 8,
      classes: [
        { class_name: 'Sorcerer', level: 5 },
        { class_name: 'Warlock', level: 3 },
      ],
      spell_slots: {
        level_1: { max: 4, used: 0 },
        level_2: { max: 5, used: 1, pact_max: 2, pact_used: 1 },
        level_3: { max: 2, used: 0 },
        pact: { max: 2, used: 1, level: 2 },
      },
    };
    component.getSpellSlotUsed = (lvl: number) => component.char.spell_slots?.[`level_${lvl}`]?.used ?? 0;
    component.getSpellSlotMax = (lvl: number) => component.char.spell_slots?.[`level_${lvl}`]?.max ?? 0;
    fixture.detectChanges();

    const text = (fixture.nativeElement as HTMLElement).textContent || '';
    expect(component.pactPool).toEqual({ max: 2, used: 1, remaining: 1, level: 2 });
    expect(component.pactCountAtLevel(2)).toBe(2);
    expect(component.pactRemainingAtLevel(2)).toBe(1);
    expect(component.pactCountAtLevel(1)).toBe(0);
    expect(text).toContain('1/2 Pact (Lvl 2 · Short Rest)');
    expect(text).toContain('1/2 Pact');
  });

  it('detects Pact Magic slots for a single-class Warlock without an explicit pact key', () => {
    component.char = {
      ...mockChar,
      char_class: 'Warlock',
      char_level: 3,
      classes: [{ class_name: 'Warlock', level: 3 }],
      spell_slots: {
        level_2: { max: 2, used: 0 },
      },
    };
    component.getSpellSlotUsed = (lvl: number) => component.char.spell_slots?.[`level_${lvl}`]?.used ?? 0;
    component.getSpellSlotMax = (lvl: number) => component.char.spell_slots?.[`level_${lvl}`]?.max ?? 0;
    fixture.detectChanges();

    const text = (fixture.nativeElement as HTMLElement).textContent || '';
    expect(component.pactPool).toEqual({ max: 2, used: 0, remaining: 2, level: 2 });
    expect(text).toContain('2/2 Pact (Lvl 2 · Short Rest)');
  });

  it('caps Warlock Pact Magic display to Warlock pactSlotCount on third-caster multiclass sheets without pact keys', () => {
    component.char = {
      ...mockChar,
      char_class: 'Fighter',
      char_level: 10,
      classes: [
        { class_name: 'Fighter', level: 7, subclass: 'Eldritch Knight' },
        { class_name: 'Warlock', level: 3 },
      ],
      spell_slots: {
        level_1: { max: 4, used: 0 },
        level_2: { max: 4, used: 1 },
      },
    };
    component.getSpellSlotUsed = (lvl: number) => component.char.spell_slots?.[`level_${lvl}`]?.used ?? 0;
    component.getSpellSlotMax = (lvl: number) => component.char.spell_slots?.[`level_${lvl}`]?.max ?? 0;
    fixture.detectChanges();

    const text = (fixture.nativeElement as HTMLElement).textContent || '';
    expect(component.pactPool).toEqual({ max: 2, used: 1, remaining: 1, level: 2 });
    expect(component.pactCountAtLevel(2)).toBe(2);
    expect(text).toContain('1/2 Pact (Lvl 2 · Short Rest)');
    expect(text).not.toContain('4/4 Pact');
  });

  describe('Mobile Companion compactMobile mode', () => {
    beforeEach(() => {
      component.char = {
        ...JSON.parse(JSON.stringify(mockChar)),
        spell_ability: 'INT',
        spell_save_dc: 15,
        spell_attack_bonus: '+7',
      };
      component.getSpellSlotMax = (lvl: number) => component.char.spell_slots?.[String(lvl)]?.max ?? 0;
      component.getSpellSlotUsed = (lvl: number) => component.char.spell_slots?.[String(lvl)]?.used ?? 0;
      fixture.componentRef.setInput('compactMobile', true);
      fixture.detectChanges();
    });

    it('renders compact 1-line spellcasting header and filters by level & prepared pills', () => {
      const el = fixture.nativeElement as HTMLElement;
      const statsText = el.querySelector('[data-testid="mobile-spell-stats"]')?.textContent || '';
      expect(statsText).toContain('INT');
      expect(statsText).toContain('15');
      expect(statsText).toContain('+7');

      (el.querySelector('[data-testid="mobile-spell-filter-2"]') as HTMLButtonElement).click();
      fixture.detectChanges();
      expect(component.mobileFilteredSpellGroups.map((g) => g.level)).toEqual([2]);
      expect(component.mobileFilteredSpellGroups[0].spells).toEqual(['Misty Step', 'Scorching Ray']);

      (el.querySelector('[data-testid="mobile-spell-filter-prepared"]') as HTMLButtonElement).click();
      fixture.detectChanges();
      const allPrepared = component.mobileFilteredSpellGroups.flatMap((g) => g.spells);
      expect(allPrepared).toContain('Shield');
      expect(allPrepared).not.toContain('Detect Magic');
    });

    it('spends or restores spell slots via inline clickable slot pips on level headers', () => {
      const useSpy = jest.spyOn(component.useSpellSlot, 'emit');
      const restoreSpy = jest.spyOn(component.restoreSpellSlot, 'emit');
      const el = fixture.nativeElement as HTMLElement;

      // Level 1 has max 4, used 1 => 3 remaining (pips 1,2,3 filled; pip 4 empty)
      (el.querySelector('[data-testid="mobile-slot-pip-1-3"]') as HTMLButtonElement).click();
      expect(useSpy).toHaveBeenCalledWith(1);

      (el.querySelector('[data-testid="mobile-slot-pip-1-4"]') as HTMLButtonElement).click();
      expect(restoreSpy).toHaveBeenCalledWith(1);
    });

    it('opens spell detail with spell level and supports casting from detail helper', () => {
      const castSpy = jest.spyOn(component.castSpell, 'emit');
      const slotSpy = jest.spyOn(component.useSpellSlot, 'emit');

      component.openSpellDetail('Magic Missile', 1);
      expect(component.selectedSpell()).toBe('Magic Missile');
      expect(component.selectedSpellLevel()).toBe(1);

      component.castFromDetail('Magic Missile', 1);
      expect(slotSpy).toHaveBeenCalledWith(1);
      expect(castSpy).toHaveBeenCalledWith({ spellName: 'Magic Missile', level: 1, isRitual: false });
    });

    it('resets active spell filters and open sheets when hero changes', () => {
      component.mobileLevelFilter.set(1);
      component.openSpellDetail('Magic Missile', 1);
      expect(component.selectedSpell()).toBe('Magic Missile');

      fixture.componentRef.setInput('char', { ...component.char, char_id: 'wizard-2', char_name: 'Elminster' });
      fixture.detectChanges();
      expect(component.mobileLevelFilter()).toBe('all');
      expect(component.selectedSpell()).toBeNull();
    });

    it('renders Warlock Pact + level_N schema slots in compactMobile mode and sequences detail -> upcast cleanly', async () => {
      fixture.componentRef.setInput('char', {
        ...component.char,
        char_id: 'hexlock-1',
        char_class: 'Warlock',
        spells: { level_1: ['Hex'], level_2: ['Misty Step'] },
        spell_slots: {
          pact: { max: 2, used: 1, level: 2 },
          level_1: { max: 2, used: 0 },
          level_2: { max: 2, used: 1, pact_max: 2, pact_used: 1 },
        },
      });
      component.getSpellSlotMax = (lvl: number) => component.char.spell_slots?.[`level_${lvl}`]?.max ?? 0;
      component.getSpellSlotUsed = (lvl: number) => component.char.spell_slots?.[`level_${lvl}`]?.used ?? 0;
      fixture.detectChanges();

      const text = (fixture.nativeElement as HTMLElement).textContent || '';
      expect(text).toContain('1/2 Pact');
      expect(component.mobileLevelPills).toEqual([1, 2]);

      component.openSpellDetail('Hex', 1);
      expect(component.selectedSpell()).toBe('Hex');
      component.openUpcastFromDetail('Hex', 1);
      expect(component.selectedSpell()).toBeNull();
      await Promise.resolve();
      expect(component.upcastTarget()).toEqual({ spellName: 'Hex', baseLevel: 1 });
    });
  });

  describe('Prepared Cap, Always-Prepared Split & Ritual Casting (#261)', () => {
    function buildPreparedHero(overrides: Partial<CharacterSchema> = {}): CharacterSchema {
      return {
        char_id: 'cleric-261',
        char_name: 'Aria',
        char_class: 'Cleric',
        subclass: 'Life Domain',
        char_level: 3,
        race: 'Human',
        background: 'Acolyte',
        armor_class: 18,
        hp_max: 24,
        proficiency_bonus: 2,
        speed: 30,
        dnd_edition: '2014 Edition',
        stats: { STR: 14, DEX: 10, CON: 14, INT: 10, WIS: 14, CHA: 12 },
        spells: {
          cantrips: ['Sacred Flame'],
          level_1: ['Bless', 'Detect Magic', 'Guiding Bolt', 'Healing Word', 'Command'],
          level_2: ['Aid', 'Hold Person'],
        },
        prepared_spells: ['Guiding Bolt'],
        always_prepared_spells: ['Bless'],
        max_prepared_spells: 2,
        spell_slots: {
          level_1: { max: 4, used: 0 },
          level_2: { max: 2, used: 0 },
        },
        ...overrides,
      };
    }

    it('displays Prepared count excluding cantrips/always-prepared and locks always-prepared toggles', () => {
      fixture.componentRef.setInput('char', buildPreparedHero());
      fixture.detectChanges();

      const el = fixture.nativeElement as HTMLElement;
      expect(el.textContent).toContain('Prepared: 1 / 2');
      expect(el.textContent).toContain('Always');
      expect(component.isAlwaysPrepared('Bless')).toBe(true);
      expect(component.preparedCount).toBe(1);
      expect(component.maxPreparedCount).toBe(2);

      // Always-prepared spell cannot be unprepared via togglePrepared
      jest.spyOn(component.save, 'emit');
      component.togglePrepared('Bless', 1);
      expect(component.save.emit).not.toHaveBeenCalled();
    });

    it('enforces max_prepared_spells cap when toggling preparation', () => {
      fixture.componentRef.setInput('char', buildPreparedHero());
      fixture.detectChanges();
      jest.spyOn(component.save, 'emit');

      // 1/2 -> can prepare Healing Word cleanly
      component.togglePrepared('Healing Word', 1);
      expect(component.preparedCount).toBe(2);
      expect(component.save.emit).toHaveBeenCalledTimes(1);

      // 2/2 -> preparing a 3rd manual spell is blocked at cap
      expect(component.canPrepareToggle).toBe(true);
      component.togglePrepared('Command', 1);
      expect(component.preparedCount).toBe(2);
      expect(component.save.emit).toHaveBeenCalledTimes(1);
    });

    it('gates ritual casting per 2014 edition rules (Wizard book ok vs unprepared Cleric blocked vs non-ritual blocked)', () => {
      // Unprepared 2014 Cleric cannot cast Detect Magic as ritual, nor Hold Person
      fixture.componentRef.setInput('char', buildPreparedHero());
      fixture.detectChanges();
      expect(component.canRitualCast('Detect Magic')).toBe(false);
      expect(component.canRitualCast('Hold Person')).toBe(false);

      // Preparing Detect Magic unlocks ritual casting in 2014 Cleric
      fixture.componentRef.setInput(
        'char',
        buildPreparedHero({ prepared_spells: ['Detect Magic'] })
      );
      fixture.detectChanges();
      expect(component.canRitualCast('Detect Magic')).toBe(true);

      // 2014 Wizard can cast unprepared Detect Magic from spellbook, but never Hold Person
      fixture.componentRef.setInput(
        'char',
        buildPreparedHero({
          char_class: 'Wizard',
          prepared_spells: [],
          always_prepared_spells: [],
        })
      );
      fixture.detectChanges();
      expect(component.canRitualCast('Detect Magic')).toBe(true);
      expect(component.canRitualCast('Hold Person')).toBe(false);
    });

    it('renders mobile prepared counter in 2024 Revision and resets filters on hero switch', () => {
      fixture.componentRef.setInput('compactMobile', true);
      fixture.componentRef.setInput(
        'char',
        buildPreparedHero({
          char_class: 'Ranger',
          dnd_edition: '2024 Revision (5.5e)',
          prepared_spells: ['Detect Magic'],
          always_prepared_spells: ["Hunter's Mark"],
          max_prepared_spells: 4,
        })
      );
      component.selectedFilter.set('prepared');
      component.searchQuery.set('Detect');
      fixture.detectChanges();

      const badge = (fixture.nativeElement as HTMLElement).querySelector(
        '[data-testid="mobile-prepared-counter"]'
      );
      expect(badge?.textContent).toContain('Prep 1/4');
      expect(component.canRitualCast('Detect Magic')).toBe(true);

      // Switching hero resets searchQuery & selectedFilter
      fixture.componentRef.setInput(
        'char',
        buildPreparedHero({
          char_id: 'other-hero',
          char_name: 'Kael',
          dnd_edition: '2014 Edition',
          char_class: 'Bard',
          max_prepared_spells: null,
        })
      );
      fixture.detectChanges();
      expect(component.selectedFilter()).toBe('all');
      expect(component.searchQuery()).toBe('');
    });
  });
});
