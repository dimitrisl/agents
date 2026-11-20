import { ComponentFixture, TestBed } from '@angular/core/testing';
import { MobileHeroViewComponent } from './mobile-hero-view.component';
import { CharacterSchema } from '../../../core/models/character.model';

describe('MobileHeroViewComponent', () => {
  let fixture: ComponentFixture<MobileHeroViewComponent>;
  let component: MobileHeroViewComponent;

  const mockChar: CharacterSchema = {
    char_id: 'hero-1',
    char_name: 'Kaelen Shadowstep',
    char_class: 'Rogue',
    subclass: 'Assassin',
    char_level: 7,
    race: 'Wood Elf',
    background: 'Criminal',
    dnd_edition: '2024 Revision (5.5e)',
    armor_class: 16,
    ac_breakdown: {
      base: 12,
      base_source: 'Studded Leather',
      dex_mod: 4,
      dex_applied: 4,
      shield_bonus: 0,
      defense_bonus: 0,
      total: 16,
      formula_text: '12 (Studded Leather) + 4 (DEX) = 16',
    },
    hp_max: 52,
    hp_current: 44,
    proficiency_bonus: 3,
    speed: 35,
    stats: { STR: 10, DEX: 18, CON: 14, INT: 12, WIS: 14, CHA: 10 },
    saving_throws: ['DEX', 'INT'],
    save_advantages: ['Fey Ancestry (vs Charmed)'],
    senses: ['Darkvision 60 ft.'],
    damage_resistances: ['Poison'],
    weapon_proficiencies: ['Simple Weapons', 'Finesse Weapons'],
    tool_proficiencies: ["Thieves' Tools"],
    languages: ['Common', 'Elvish', "Thieves' Cant"],
  };

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [MobileHeroViewComponent],
    }).compileComponents();

    fixture = TestBed.createComponent(MobileHeroViewComponent);
    component = fixture.componentInstance;
    component.char = JSON.parse(JSON.stringify(mockChar));
    component.edition = '2024 Revision (5.5e)';
    component.availableHitDice = 6;
    component.classHitDieSize = 8;
    component.passivePerception = 15;
    component.passiveInvestigation = 14;
    component.passiveInsight = 12;
    component.abilityEntries = [
      { key: 'STR', value: 10 },
      { key: 'DEX', value: 18 },
      { key: 'CON', value: 14 },
      { key: 'INT', value: 12 },
      { key: 'WIS', value: 14 },
      { key: 'CHA', value: 10 },
    ];
    fixture.detectChanges();
  });

  it('renders compact identity strip and 3x2 ability cards + 2-column saving throws matrix by default', () => {
    const el = fixture.nativeElement as HTMLElement;
    expect(el.textContent).toContain('Kaelen Shadowstep');
    expect(el.textContent).toContain('Rogue • Level 7');
    expect(el.textContent).toContain('Assassin');
    expect(el.querySelectorAll('[data-testid^="mobile-ability-card-"]').length).toBe(6);
    expect(el.querySelectorAll('[data-testid^="mobile-save-btn-"]').length).toBe(6);
    expect(el.textContent).toContain('Fey Ancestry (vs Charmed)');
  });

  it('emits abilityCheck when tapping an ability card and savingThrow when tapping a save button', () => {
    const checkSpy = jest.spyOn(component.abilityCheck, 'emit');
    const saveSpy = jest.spyOn(component.savingThrow, 'emit');
    const el = fixture.nativeElement as HTMLElement;

    (el.querySelector('[data-testid="mobile-ability-card-DEX"]') as HTMLButtonElement).click();
    expect(checkSpy).toHaveBeenCalledWith('DEX');

    (el.querySelector('[data-testid="mobile-save-btn-INT"]') as HTMLButtonElement).click();
    expect(saveSpy).toHaveBeenCalledWith('INT');
  });

  it('switches to Senses & Defenses sub-tab and displays 3 passives, senses, resistances, proficiencies and languages', () => {
    const subTabSpy = jest.spyOn(component.activeSubTabChange, 'emit');
    const el = fixture.nativeElement as HTMLElement;

    (el.querySelector('[data-testid="mobile-hero-subtab-senses"]') as HTMLButtonElement).click();
    expect(subTabSpy).toHaveBeenCalledWith('senses');

    fixture.componentRef.setInput('activeSubTab', 'senses');
    fixture.detectChanges();

    const text = el.textContent || '';
    expect(text).toContain('15'); // Passive Perception
    expect(text).toContain('14'); // Passive Investigation
    expect(text).toContain('12'); // Passive Insight
    expect(text).toContain('Darkvision 60 ft.');
    expect(text).toContain('Poison');
    expect(text).toContain("Thieves' Tools");
    expect(text).toContain('Elvish');
    expect(text).toContain('12 (Studded Leather) + 4 (DEX) = 16');
  });

  it('shows DIS badges on abilities and saves under 2014 Exhaustion 3', () => {
    fixture.componentRef.setInput('char', {
      ...mockChar,
      dnd_edition: '2014 Edition',
      exhaustion_level: 3,
    });
    fixture.detectChanges();

    const text = (fixture.nativeElement as HTMLElement).textContent || '';
    expect(text).toContain('DIS');
    expect(component.hasCheckDisadvantage).toBe(true);
    expect(component.hasSaveDisadvantage).toBe(true);
  });
});
