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
    component.is2024 = true;
    component.manualRace = 'Human';
    component.manualClass = 'Wizard';
    component.manualLevel = 3;
    component.availableFeats = [
      { name: 'Alert', category: 'Origin Feats', description: 'Initiative proficiency', prerequisites: { min_level: 0 } },
      { name: 'Tough', category: 'Origin Feats', description: 'Extra hit points', prerequisites: { min_level: 0 } },
      { name: 'Lucky', category: 'Origin Feats', description: 'Rerolls', prerequisites: { min_level: 0 } },
      { name: 'War Caster', category: 'General Feats', description: 'Concentration advantage', prerequisites: { min_level: 4 } },
    ];
    component.availableSpells = [
      { name: 'Fire Bolt', level: 0, school: 'evocation', castingTime: '1 action', description: 'Fire damage' },
      { name: 'Ray of Frost', level: 0, school: 'evocation', castingTime: '1 action', description: 'Cold damage' },
      { name: 'Light', level: 0, school: 'evocation', castingTime: '1 action', description: 'Light' },
      { name: 'Mage Hand', level: 0, school: 'conjuration', castingTime: '1 action', description: 'Spectral hand' },
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
    component.manualBackground = 'Sage'; // Sage grants Arcana & History
    component.loadSkillSuggestions();
    // Sage grants Arcana, so suggestions should pick other class skills
    expect(component.manualSkills.length).toBe(2);
  });

  it('should identify background skills and prioritize non-background skills in suggestions', () => {
    component.manualBackground = 'Soldier'; // grants Athletics & Intimidation
    expect(component.isBackgroundSkill('Athletics')).toBe(true);
    expect(component.isBackgroundSkill('Intimidation')).toBe(true);
    expect(component.isBackgroundSkill('Arcana')).toBe(false);

    component.manualClass = 'Fighter'; // standard recommended is Athletics & Perception
    component.loadSkillSuggestions();
    // Since Athletics is already granted by Soldier, it should pick Perception and another allowed skill
    expect(component.manualSkills).not.toContain('Athletics');
    expect(component.manualSkills).toContain('Perception');
    expect(component.manualSkills.length).toBe(2);
  });

  it('should cap unlockedSpellLevels by maxCastableLevel', () => {
    component.manualClass = 'Wizard';
    component.manualLevel = 1;
    // Level 1 Wizard can only cast cantrips (0) and 1st-level spells (1)
    expect(component.maxCastableLevel).toBe(1);
    expect(component.unlockedSpellLevels).toEqual([0, 1]);

    component.manualLevel = 3;
    // Level 3 Wizard can cast up to 2nd-level spells
    expect(component.maxCastableLevel).toBe(2);
    expect(component.unlockedSpellLevels).toEqual([0, 1, 2]);
  });

  it('should toggle feat selection', () => {
    expect(component.isFeatSelected('Alert')).toBe(false);
    component.toggleFeat('Alert');
    expect(component.isFeatSelected('Alert')).toBe(true);
    component.toggleFeat('Alert');
    expect(component.isFeatSelected('Alert')).toBe(false);
  });

  it('should enforce origin and general feat capacity limits', () => {
    // 2024 Human has max 2 origin feats, and at level 3 Wizard has 0 general feats
    expect(component.maxOriginFeats).toBe(2);
    expect(component.maxGeneralFeats).toBe(0);

    component.toggleFeat('Alert');
    component.toggleFeat('Tough');
    expect(component.manualFeats.length).toBe(2);
    expect(component.featLimitWarning).toBeNull();

    // Trying to add a 3rd origin feat should be rejected
    component.toggleFeat('Lucky');
    expect(component.manualFeats.length).toBe(2);
    expect(component.manualFeats).not.toContain('Lucky');
    expect(component.featLimitWarning).toContain('Origin Feat limit reached');

    // General feat selection should be rejected at level 3 (requires level 4 ASI)
    component.toggleFeat('War Caster');
    expect(component.manualFeats).not.toContain('War Caster');
    expect(component.featLimitWarning).toContain('General Feats unlock at Level 4');
  });

  it('should calculate canAddFeat correctly', () => {
    const originFeat = { name: 'Alert', category: 'Origin Feats' };
    const generalFeat = { name: 'War Caster', category: 'General Feats' };

    expect(component.canAddFeat(originFeat)).toBe(true);
    expect(component.canAddFeat(generalFeat)).toBe(false); // level 3 wizard has 0 general feats

    component.manualFeats = ['Alert', 'Tough'];
    expect(component.canAddFeat(originFeat)).toBe(false); // limit 2 reached
  });

  it('should load recommended feat suggestions up to capacity', () => {
    component.manualClass = 'Wizard';
    component.loadFeatSuggestions();
    expect(component.manualFeats.length).toBeLessThanOrEqual(component.maxOriginFeats + component.maxGeneralFeats);
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

  it('should enforce cantrip capacity limit', () => {
    // Level 3 Wizard has 3 cantrips max
    expect(component.maxCantrips).toBe(3);

    component.toggleSpell('Fire Bolt');
    component.toggleSpell('Ray of Frost');
    component.toggleSpell('Light');
    expect(component.cantripsCount).toBe(3);
    expect(component.spellLimitWarning).toBeNull();

    // 4th cantrip should be blocked
    component.toggleSpell('Mage Hand');
    expect(component.cantripsCount).toBe(3);
    expect(component.manualSpells).not.toContain('Mage Hand');
    expect(component.spellLimitWarning).toContain('Cantrip limit reached');
  });

  it('should enforce prepared spell capacity limit', () => {
    // Level 3 Wizard in 2024 has 6 prepared spells
    expect(component.maxPreparedSpells).toBe(6);

    const leveledSpells = [
      'Spell 1', 'Spell 2', 'Spell 3', 'Spell 4', 'Spell 5', 'Spell 6'
    ];
    component.manualSpells = [...leveledSpells];
    expect(component.leveledSpellsCount).toBe(6);

    // Adding 7th leveled spell
    component.toggleSpell('Spell 7');
    expect(component.leveledSpellsCount).toBe(6);
    expect(component.spellLimitWarning).toContain('Prepared spell limit reached');
  });

  it('should load recommended spell suggestions up to capacity', () => {
    component.manualClass = 'Wizard';
    component.loadSpellSuggestions();
    expect(component.cantripsCount).toBeLessThanOrEqual(component.maxCantrips);
    expect(component.leveledSpellsCount).toBeLessThanOrEqual(component.maxPreparedSpells);
    expect(component.manualSpells).toContain('Fire Bolt');
    expect(component.manualSpells).toContain('Shield');
  });

  it('should correctly determine spellcaster status', () => {
    component.manualClass = 'Wizard';
    expect(component.isSpellcaster).toBe(true);

    component.manualClass = 'Barbarian';
    expect(component.isSpellcaster).toBe(false);
  });
});
