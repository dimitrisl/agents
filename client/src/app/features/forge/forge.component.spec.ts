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
    await TestBed.configureTestingModule({
      imports: [HttpClientTestingModule, RouterTestingModule, ForgeComponent],
      schemas: [NO_ERRORS_SCHEMA],
    }).compileComponents();

    httpMock = TestBed.inject(HttpTestingController);
    fixture = TestBed.createComponent(ForgeComponent);
    component = fixture.componentInstance;
  });

  afterEach(() => {
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
});
