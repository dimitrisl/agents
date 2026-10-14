import { ComponentFixture, TestBed } from '@angular/core/testing';
import { HttpClientTestingModule } from '@angular/common/http/testing';
import { RouterTestingModule } from '@angular/router/testing';
import { NO_ERRORS_SCHEMA } from '@angular/core';
import { ManualFormComponent } from './manual-form.component';

describe('ManualFormComponent', () => {
  let component: ManualFormComponent;
  let fixture: ComponentFixture<ManualFormComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [HttpClientTestingModule, RouterTestingModule, ManualFormComponent],
      schemas: [NO_ERRORS_SCHEMA],
    }).compileComponents();

    fixture = TestBed.createComponent(ManualFormComponent);
    component = fixture.componentInstance;
    component.manualClass = 'Wizard';
    component.manualLevel = 3;
    component.availableFeats = [
      { name: 'Alert', category: 'Origin Feats', description: 'Initiative proficiency', prerequisites: { min_level: 0 } },
      { name: 'War Caster', category: 'General Feats', description: 'Concentration advantage', prerequisites: { min_level: 4 } },
    ];
    component.availableSpells = [
      { name: 'Fire Bolt', level: 0, school: 'evocation', castingTime: '1 action', description: 'Fire damage' },
      { name: 'Shield', level: 1, school: 'abjuration', castingTime: '1 reaction', description: '+5 AC' },
      { name: 'Misty Step', level: 2, school: 'conjuration', castingTime: '1 bonus action', description: 'Teleport 30ft' },
    ];
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });

  it('should toggle skill selection', () => {
    expect(component.isSkillSelected('Arcana')).toBe(false);
    component.toggleSkill('Arcana');
    expect(component.isSkillSelected('Arcana')).toBe(true);
    component.toggleSkill('Arcana');
    expect(component.isSkillSelected('Arcana')).toBe(false);
  });

  it('should load skill suggestions for class', () => {
    component.manualClass = 'Wizard';
    component.loadSkillSuggestions();
    expect(component.manualSkills).toContain('Arcana');
    expect(component.manualSkills).toContain('Investigation');
  });

  it('should toggle feat selection', () => {
    expect(component.isFeatSelected('Alert')).toBe(false);
    component.toggleFeat('Alert');
    expect(component.isFeatSelected('Alert')).toBe(true);
    component.toggleFeat('Alert');
    expect(component.isFeatSelected('Alert')).toBe(false);
  });

  it('should load recommended feat suggestions', () => {
    component.manualClass = 'Wizard';
    component.is2024 = true;
    component.loadFeatSuggestions();
    expect(component.manualFeats.length).toBeGreaterThan(0);
    expect(component.manualFeats).toContain('Alert');
  });

  it('should toggle spell selection and count by level', () => {
    expect(component.isSpellSelected('Fire Bolt')).toBe(false);
    component.toggleSpell('Fire Bolt');
    expect(component.isSpellSelected('Fire Bolt')).toBe(true);
    expect(component.getSelectedSpellsCountByLevel(0)).toBe(1);
    expect(component.getSelectedSpellsCountByLevel(1)).toBe(0);

    component.toggleSpell('Shield');
    expect(component.getSelectedSpellsCountByLevel(1)).toBe(1);
  });

  it('should load recommended spell suggestions', () => {
    component.manualClass = 'Wizard';
    component.loadSpellSuggestions();
    expect(component.manualSpells).toContain('Fire Bolt');
    expect(component.manualSpells).toContain('Shield');
    expect(component.manualSpells).toContain('Misty Step');
  });

  it('should correctly determine spellcaster status', () => {
    component.manualClass = 'Wizard';
    expect(component.isSpellcaster).toBe(true);

    component.manualClass = 'Barbarian';
    expect(component.isSpellcaster).toBe(false);
  });
});
