import { ComponentFixture, TestBed } from '@angular/core/testing';
import { HttpClientTestingModule, HttpTestingController } from '@angular/common/http/testing';
import { RouterTestingModule } from '@angular/router/testing';
import { NO_ERRORS_SCHEMA } from '@angular/core';
import { ForgeComponent } from './forge.component';
import { environment } from '../../../environments/environment';

describe('ForgeComponent', () => {
  let component: ForgeComponent;
  let fixture: ComponentFixture<ForgeComponent>;
  let httpMock: HttpTestingController;

  beforeEach(async () => {
    localStorage.clear();
    await TestBed.configureTestingModule({
      imports: [HttpClientTestingModule, RouterTestingModule, ForgeComponent],
      schemas: [NO_ERRORS_SCHEMA],
    }).compileComponents();

    httpMock = TestBed.inject(HttpTestingController);
    fixture = TestBed.createComponent(ForgeComponent);
    component = fixture.componentInstance;
  });

  afterEach(() => {
    localStorage.clear();
    httpMock.verify();
  });

  it('should create and fetch rules data on init', () => {
    fixture.detectChanges();

    const reqFeats = httpMock.expectOne((req) => req.url.includes('/rules/feats'));
    expect(reqFeats.request.method).toBe('GET');
    reqFeats.flush([{ name: 'Alert' }]);

    const reqSpells = httpMock.expectOne((req) => req.url.includes('/rules/spells'));
    expect(reqSpells.request.method).toBe('GET');
    reqSpells.flush([{ name: 'Shield' }]);

    expect(component).toBeTruthy();
    expect(component.availableFeats.length).toBe(1);
    expect(component.availableSpells.length).toBe(1);
  });

  it('should send chosen skills, feats, and spells in createManualCharacter payload', () => {
    fixture.detectChanges();

    // Flush initial init requests
    httpMock.expectOne((req) => req.url.includes('/rules/feats')).flush([]);
    httpMock.expectOne((req) => req.url.includes('/rules/spells')).flush([]);

    component.manualName = 'Mage Tester';
    component.manualClass = 'Wizard';
    component.manualLevel = 3;
    component.manualSkills = ['Arcana', 'Investigation'];
    component.manualFeats = ['Alert'];
    component.manualSpells = ['Fire Bolt', 'Shield'];

    component.createManualCharacter();

    const enrichReq = httpMock.expectOne(`${environment.apiBaseUrl}/forge/enrich-manual`);
    expect(enrichReq.request.method).toBe('POST');
    expect(enrichReq.request.body.name).toBe('Mage Tester');
    expect(enrichReq.request.body.skill_proficiencies).toEqual(['Arcana', 'Investigation']);
    expect(enrichReq.request.body.chosen_feats).toEqual(['Alert']);
    expect(enrichReq.request.body.chosen_spells).toEqual(['Fire Bolt', 'Shield']);

    enrichReq.flush({
      char_name: 'Mage Tester',
      char_class: 'Wizard',
      char_level: 3,
      skill_proficiencies: ['Arcana', 'Investigation'],
      spells: { cantrips: ['Fire Bolt'], level_1: ['Shield'] },
    });

    expect(component.tempForgedChar).toBeTruthy();
  });

  it('should reset stale skills, feats, and spells when class changes and fetch Wizard spells for Eldritch Knight', () => {
    fixture.detectChanges();
    httpMock.expectOne((req) => req.url.includes('/rules/feats')).flush([]);
    httpMock.expectOne((req) => req.url.includes('/rules/spells')).flush([]);

    component.manualSkills = ['Arcana', 'Investigation'];
    component.manualFeats = ['War Caster'];
    component.manualSpells = ['Fire Bolt', 'Shield'];

    component.onManualClassChange('Fighter');
    httpMock.expectOne((req) => req.url.includes('/rules/spells')).flush([]);
    expect(component.manualSkills).toEqual([]);
    expect(component.manualFeats).toEqual([]);
    expect(component.manualSpells).toEqual([]);
    expect(component.availableSpells).toEqual([]);

    // Selecting Eldritch Knight at level 3 should fetch Wizard spells
    component.manualLevel = 3;
    component.onManualSubclassChange('Eldritch Knight');
    const spellReq = httpMock.expectOne((req) => req.url.includes('/rules/spells'));
    expect(spellReq.request.params.get('char_class')).toBe('Wizard');
    spellReq.flush([{ name: 'Shield', level: 1 }]);
    expect(component.availableSpells.length).toBe(1);
  });

  it('should clear subclass and over-level spells when level is lowered below unlock threshold', () => {
    fixture.detectChanges();
    httpMock.expectOne((req) => req.url.includes('/rules/feats')).flush([]);
    httpMock.expectOne((req) => req.url.includes('/rules/spells')).flush([
      { name: 'Fire Bolt', level: 0 },
      { name: 'Shield', level: 1 },
      { name: 'Fireball', level: 3 },
    ]);

    component.manualClass = 'Wizard';
    component.manualLevel = 5;
    component.manualSubclass = 'School of Evocation';
    component.manualSpells = ['Fire Bolt', 'Shield', 'Fireball'];

    // Lowering level to 1 should lock subclass ('None') and prune Fireball (level 3 spell)
    component.onManualLevelChange(1);
    httpMock.expectOne((req) => req.url.includes('/rules/spells')).flush([
      { name: 'Fire Bolt', level: 0 },
      { name: 'Shield', level: 1 },
    ]);
    expect(component.manualSubclass).toBe('None');
    expect(component.manualSpells).toEqual(['Fire Bolt', 'Shield']);
  });

  it('should manage forging progress modal and state during AI character generation', () => {
    fixture.detectChanges();
    httpMock.expectOne((req) => req.url.includes('/rules/feats')).flush([]);
    httpMock.expectOne((req) => req.url.includes('/rules/spells')).flush([]);

    expect(component.isForgingModalOpen).toBe(false);
    expect(component.loading).toBe(false);

    component.aiRace = 'Elf';
    component.aiClass = 'Ranger';
    component.aiLevel = 2;
    component.aiConcept = 'Forest scout with a loyal falcon';

    component.generateAiCharacter();

    expect(component.loading).toBe(true);
    expect(component.isForgingModalOpen).toBe(true);
    expect(component.forgeProgress).toBeGreaterThanOrEqual(3);
    expect(component.forgingError).toBeNull();

    const genReq = httpMock.expectOne(`${environment.apiBaseUrl}/forge/generate`);
    expect(genReq.request.method).toBe('POST');
    expect(genReq.request.body.race).toBe('Elf');
    expect(genReq.request.body.char_class).toBe('Ranger');

    genReq.flush({
      char_name: 'Aeris',
      race: 'Elf',
      char_class: 'Ranger',
      char_level: 2,
      stats: { STR: 10, DEX: 16, CON: 14, INT: 10, WIS: 14, CHA: 10 },
      hp_max: 20,
      armor_class: 15,
    });

    expect(component.tempForgedChar).toBeTruthy();
    expect(component.tempForgedChar?.char_name).toBe('Aeris');
    expect(component.forgeProgress).toBe(100);
    expect(component.forgeCurrentPhaseIndex).toBe(5);

    // Verify temp hero was persisted to localStorage
    const saved = localStorage.getItem('phyrexian_forge_temp_hero');
    expect(saved).toBeTruthy();
    expect(JSON.parse(saved!).char_name).toBe('Aeris');

    // Discarding clears temp hero from state and localStorage
    component.discardHero();
    expect(component.tempForgedChar).toBeNull();
    expect(localStorage.getItem('phyrexian_forge_temp_hero')).toBeNull();
  });

  it('should persist and restore AI form draft across page reloads', () => {
    fixture.detectChanges();
    httpMock.expectOne((req) => req.url.includes('/rules/feats')).flush([]);
    httpMock.expectOne((req) => req.url.includes('/rules/spells')).flush([]);

    component.aiRace = 'Tiefling';
    component.aiClass = 'Warlock';
    component.aiLevel = 4;
    component.aiConcept = 'Fiend pact scholar of dark secrets';
    component.saveAiDraft();

    const draftStr = localStorage.getItem('phyrexian_forge_ai_draft');
    expect(draftStr).toBeTruthy();
    expect(JSON.parse(draftStr!).aiClass).toBe('Warlock');

    // Reset component values and restore
    component.aiClass = 'Fighter';
    component.restoreAiDraft();
    expect(component.aiClass).toBe('Warlock');
    expect(component.aiRace).toBe('Tiefling');
    expect(component.aiConcept).toBe('Fiend pact scholar of dark secrets');
  });

  it('should handle forging errors gracefully without unhandled crashes', () => {
    fixture.detectChanges();
    httpMock.expectOne((req) => req.url.includes('/rules/feats')).flush([]);
    httpMock.expectOne((req) => req.url.includes('/rules/spells')).flush([]);

    component.generateAiCharacter();
    const genReq = httpMock.expectOne(`${environment.apiBaseUrl}/forge/generate`);
    genReq.flush({ detail: 'Rate limit exceeded' }, { status: 429, statusText: 'Too Many Requests' });

    expect(component.loading).toBe(false);
    expect(component.forgingError).toContain('Rate limit exceeded');
    expect(component.isForgingModalOpen).toBe(true);

    component.closeForgingModal();
    expect(component.isForgingModalOpen).toBe(false);
    expect(component.forgingError).toBeNull();
  });
});
