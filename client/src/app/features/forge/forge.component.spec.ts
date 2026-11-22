import { ComponentFixture, TestBed } from '@angular/core/testing';
import { HttpClientTestingModule, HttpTestingController } from '@angular/common/http/testing';
import { RouterTestingModule } from '@angular/router/testing';
import { NO_ERRORS_SCHEMA } from '@angular/core';
import { Router } from '@angular/router';
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

    const reqChoices = httpMock.expectOne((req) => req.url.includes('/rules/class-choices'));
    expect(reqChoices.request.method).toBe('GET');
    reqChoices.flush({ divine_orders: [{ name: 'Divine Order: Protector' }] });

    expect(component).toBeTruthy();
    expect(component.availableFeats.length).toBe(1);
    expect(component.availableSpells.length).toBe(1);
    expect(component.availableClassChoices['divine_orders']?.length).toBe(1);
  });

  it('should send chosen skills, feats, spells, and class choices in createManualCharacter payload', () => {
    fixture.detectChanges();

    // Flush initial init requests
    httpMock.expectOne((req) => req.url.includes('/rules/feats')).flush([]);
    httpMock.expectOne((req) => req.url.includes('/rules/spells')).flush([]);
    httpMock.expectOne((req) => req.url.includes('/rules/class-choices')).flush({});

    component.manualName = 'Cleric Tester';
    component.manualClass = 'Cleric';
    component.manualLevel = 3;
    component.manualSkills = ['Insight', 'Religion'];
    component.manualFeats = ['Alert'];
    component.manualSpells = ['Sacred Flame', 'Bless'];
    component.manualClassChoice = 'Divine Order: Thaumaturge';

    component.createManualCharacter();

    const enrichReq = httpMock.expectOne(`${environment.apiBaseUrl}/forge/enrich-manual`);
    expect(enrichReq.request.method).toBe('POST');
    expect(enrichReq.request.body.name).toBe('Cleric Tester');
    expect(enrichReq.request.body.skill_proficiencies).toEqual(['Insight', 'Religion']);
    expect(enrichReq.request.body.chosen_feats).toEqual(['Alert']);
    expect(enrichReq.request.body.chosen_spells).toEqual(['Sacred Flame', 'Bless']);
    expect(enrichReq.request.body.chosen_class_choices).toEqual(['Divine Order: Thaumaturge']);

    enrichReq.flush({
      char_name: 'Cleric Tester',
      char_class: 'Cleric',
      char_level: 3,
      skill_proficiencies: ['Insight', 'Religion'],
      spells: { cantrips: ['Sacred Flame'], level_1: ['Bless'] },
    });

    expect(component.tempForgedChar).toBeTruthy();
  });

  it('trims excess cantrips when switching away from Thaumaturge and ignores stale edition class-choices responses', () => {
    fixture.detectChanges();
    httpMock.expectOne((req) => req.url.includes('/rules/feats')).flush([]);
    httpMock.expectOne((req) => req.url.includes('/rules/spells')).flush([]);
    // Hold the 2014 class-choices response so we can test out-of-order resolution after toggling to 2024
    const stale2014Choices = httpMock.expectOne((req) => req.url.includes('/rules/class-choices'));

    component.toggleEditionAndRefresh();
    httpMock.expectOne((req) => req.url.includes('/rules/feats')).flush([]);
    httpMock.expectOne((req) => req.url.includes('/rules/spells')).flush([]);
    const fresh2024Choices = httpMock.expectOne((req) => req.url.includes('/rules/class-choices'));
    fresh2024Choices.flush({
      divine_orders: [{ name: 'Divine Order: Protector' }, { name: 'Divine Order: Thaumaturge' }],
    });
    // Late-arriving 2014 response must NOT overwrite 2024 choices
    stale2014Choices.flush({ pact_boons: [{ name: 'Pact of the Blade' }] });
    expect(component.availableClassChoices['divine_orders']?.length).toBe(2);
    expect(component.availableClassChoices['pact_boons']).toBeUndefined();

    // Selecting 4 cantrips under Thaumaturge, then switching to Protector prunes to 3 cantrips (preserving leveled spells)
    component.manualClass = 'Cleric';
    component.manualLevel = 1;
    component.availableSpells = [
      { name: 'Guidance', level: 0 },
      { name: 'Light', level: 0 },
      { name: 'Sacred Flame', level: 0 },
      { name: 'Thaumaturgy', level: 0 },
      { name: 'Bless', level: 1 },
    ];
    component.manualClassChoice = 'Divine Order: Thaumaturge';
    component.manualSpells = ['Guidance', 'Light', 'Sacred Flame', 'Thaumaturgy', 'Bless'];

    component.onManualClassChoiceChange('Divine Order: Protector');
    expect(component.manualSpells).toEqual(['Guidance', 'Light', 'Sacred Flame', 'Bless']);
  });

  it('should reset stale skills, feats, and spells when class changes and fetch Wizard spells for Eldritch Knight', () => {
    fixture.detectChanges();
    httpMock.expectOne((req) => req.url.includes('/rules/feats')).flush([]);
    httpMock.expectOne((req) => req.url.includes('/rules/spells')).flush([]);
    httpMock.expectOne((req) => req.url.includes('/rules/class-choices')).flush({});

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
    httpMock.expectOne((req) => req.url.includes('/rules/class-choices')).flush({});

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
    httpMock.expectOne((req) => req.url.includes('/rules/class-choices')).flush({});

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
    expect(component.forgePhases.every((p) => !/[\u0370-\u03FF]/.test(p.title + p.subtitle))).toBe(true);
    expect(component.forgePhases[5].title).toBe('Hero Forged!');

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
    httpMock.expectOne((req) => req.url.includes('/rules/class-choices')).flush({});

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
    httpMock.expectOne((req) => req.url.includes('/rules/class-choices')).flush({});

    component.generateAiCharacter();
    const genReq = httpMock.expectOne(`${environment.apiBaseUrl}/forge/generate`);
    genReq.flush({ detail: 'Rate limit exceeded' }, { status: 429, statusText: 'Too Many Requests' });

    expect(component.loading).toBe(false);
    expect(component.forgingError).toContain('Rate limit exceeded');
    expect(component.isForgingModalOpen).toBe(true);

    // onBeforeUnload should not block navigation when modal is showing an error
    const unloadEvent = { preventDefault: jest.fn(), returnValue: undefined } as any;
    component.onBeforeUnload(unloadEvent);
    expect(unloadEvent.preventDefault).not.toHaveBeenCalled();

    component.closeForgingModal();
    expect(component.isForgingModalOpen).toBe(false);
    expect(component.forgingError).toBeNull();
  });

  it('dispatches retryForging to createManualCharacter on manual tab and generateAiCharacter on ai tab', () => {
    const manualSpy = jest.spyOn(component, 'createManualCharacter').mockImplementation(() => {});
    const aiSpy = jest.spyOn(component, 'generateAiCharacter').mockImplementation(() => {});

    component.activeTab = 'manual';
    component.retryForging();
    expect(manualSpy).toHaveBeenCalledTimes(1);
    expect(aiSpy).not.toHaveBeenCalled();

    component.activeTab = 'ai';
    component.retryForging();
    expect(aiSpy).toHaveBeenCalledTimes(1);
  });

  describe('Import tab', () => {
    it('offers Import next to AI Forge and Manual Build', () => {
      expect(component.forgeTabs.map((t) => t.id)).toEqual(['ai', 'manual', 'import']);
    });

    it('imports a PDF as a new hero and opens the dashboard', () => {
      const router = TestBed.inject(Router);
      const navigate = jest.spyOn(router, 'navigate').mockResolvedValue(true);

      component.onImportPdf(new File(['%PDF'], 'sheet.pdf'));
      expect(component.importBusy).toBe(true);

      httpMock.expectOne((r) => r.url.endsWith('/characters/import-pdf')).flush({ char_id: 'new', char_name: 'Valeros', warnings: [] });
      httpMock.expectOne((r) => r.method === 'GET' && r.url.endsWith('/characters')).flush({ characters: [] });

      expect(component.importBusy).toBe(false);
      expect(navigate).toHaveBeenCalledWith(['/player']);
    });

    it('stays to show warnings, and opens the hero when they are acknowledged', () => {
      const router = TestBed.inject(Router);
      const navigate = jest.spyOn(router, 'navigate').mockResolvedValue(true);

      component.onImportDndBeyond('12345');
      httpMock
        .expectOne((r) => r.url.endsWith('/characters/import-dndbeyond'))
        .flush({ char_id: 'new', char_name: 'Valeros', warnings: ['Homebrew subclass not recognised'] });
      httpMock.expectOne((r) => r.method === 'GET' && r.url.endsWith('/characters')).flush({ characters: [] });

      expect(component.importWarnings).toEqual(['Homebrew subclass not recognised']);
      expect(navigate).not.toHaveBeenCalled();

      component.openImportedHero();
      expect(navigate).toHaveBeenCalledWith(['/player']);
    });

    it('shows the API error and stays on the tab', () => {
      component.onImportFoundry(new File(['{}'], 'actor.json'));
      httpMock
        .expectOne((r) => r.url.endsWith('/characters/import-foundry'))
        .flush({ detail: 'Not a dnd5e actor' }, { status: 400, statusText: 'Bad Request' });
      expect(component.importBusy).toBe(false);
      expect(component.importError).toBe('Not a dnd5e actor');
    });
  });

  describe('Portrait handling', () => {
    it('strips image.pollinations.ai URLs instead of persisting data URI SVGs to char_portrait', () => {
      fixture.detectChanges();
      httpMock.expectOne((req) => req.url.includes('/rules/feats')).flush([]);
      httpMock.expectOne((req) => req.url.includes('/rules/spells')).flush([]);
      httpMock.expectOne((req) => req.url.includes('/rules/class-choices')).flush({});

      component.manualName = 'Kael';
      component.manualClass = 'Fighter';
      component.createManualCharacter();

      const enrichReq = httpMock.expectOne(`${environment.apiBaseUrl}/forge/enrich-manual`);
      enrichReq.flush({
        char_id: 'unsaved-1',
        char_name: 'Kael',
        char_class: 'Fighter',
        char_level: 1,
        char_portrait: 'https://image.pollinations.ai/prompt/fighter',
      });

      expect(component.tempForgedChar?.char_portrait).toBeUndefined();
    });

    it('sends character_data for unsaved tempForgedChar when regenerating portrait and updates reference', () => {
      fixture.detectChanges();
      httpMock.expectOne((req) => req.url.includes('/rules/feats')).flush([]);
      httpMock.expectOne((req) => req.url.includes('/rules/spells')).flush([]);
      httpMock.expectOne((req) => req.url.includes('/rules/class-choices')).flush({});

      const initialHero: any = {
        char_id: 'unsaved-2',
        char_name: 'Lyra',
        char_class: 'Wizard',
        race: 'Elf',
      };
      component.tempForgedChar = initialHero;

      component.regeneratePortrait();

      const req = httpMock.expectOne(`${environment.apiBaseUrl}/forge/portrait`);
      expect(req.request.body.char_id).toBe('unsaved-2');
      expect(req.request.body.character_data).toEqual(initialHero);
      req.flush({ success: true, portrait_url: '/api/v1/portraits/lyra.png', version: 0 });

      expect(component.tempForgedChar?.char_portrait).toBe('/api/v1/portraits/lyra.png');
      expect(component.tempForgedChar).not.toBe(initialHero);
    });

    it('sanitizes legacy pollinations and SVG portraits from cached drafts on restore and save', () => {
      fixture.detectChanges();
      httpMock.expectOne((req) => req.url.includes('/rules/feats')).flush([]);
      httpMock.expectOne((req) => req.url.includes('/rules/spells')).flush([]);
      httpMock.expectOne((req) => req.url.includes('/rules/class-choices')).flush({});

      localStorage.setItem(
        'phyrexian_forge_temp_hero',
        JSON.stringify({
          char_id: 'cached-1',
          char_name: 'CachedHero',
          char_class: 'Rogue',
          stats: { STR: 10, DEX: 16, CON: 12, INT: 10, WIS: 10, CHA: 10 },
          char_portrait: 'data:image/svg+xml;utf8,%3Csvg%3E%3C/svg%3E',
        })
      );

      component.restoreTempHero();
      expect(component.tempForgedChar?.char_portrait).toBeUndefined();

      component.tempForgedChar!.char_portrait = 'https://image.pollinations.ai/prompt/legacy';
      const saveSpy = jest.spyOn(component.charState, 'saveCharacter');
      component.acceptAndEquipHero();

      expect(saveSpy).toHaveBeenCalledWith(
        expect.objectContaining({ char_id: 'cached-1', char_portrait: undefined })
      );
      const req = httpMock.expectOne(`${environment.apiBaseUrl}/characters`);
      expect(req.request.body.char_portrait).toBeUndefined();
      req.flush({ ...req.request.body, version: 1 });
      httpMock.match((r) => r.method === 'GET' && r.url.endsWith('/characters')).forEach((r) =>
        r.flush({ characters: [], unreadable: [] })
      );
    });

    it('keeps aiGender at default when restoring a stale draft with removed gender options', () => {
      fixture.detectChanges();
      httpMock.expectOne((req) => req.url.includes('/rules/feats')).flush([]);
      httpMock.expectOne((req) => req.url.includes('/rules/spells')).flush([]);
      httpMock.expectOne((req) => req.url.includes('/rules/class-choices')).flush({});

      localStorage.setItem(
        'phyrexian_forge_ai_draft',
        JSON.stringify({ aiGender: 'Non-binary', aiRace: 'Aasimar', aiClass: 'Wizard' })
      );

      component.restoreAiDraft();
      expect(component.aiClass).toBe('Wizard');
      expect(component.aiGender).toBe('AI Choice');
      expect(component.aiRace).toBe('AI Choice');
    });

    it('separates 2014 vs 2024 races/backgrounds, resets stale aiRace on toggle, and applies 2014 racial stat bonuses', () => {
      fixture.detectChanges();
      httpMock.expectOne((req) => req.url.includes('/rules/feats')).flush([]);
      httpMock.expectOne((req) => req.url.includes('/rules/spells')).flush([]);
      httpMock.expectOne((req) => req.url.includes('/rules/class-choices')).flush({});

      // 2014 Edition: Variant Human & canonical subraces present, Warforged absent
      expect(component.raceOptions).toContain('Variant Human');
      expect(component.raceOptions).toContain('High Elf');
      expect(component.raceOptions).toContain('Wood Elf');
      expect(component.raceOptions).toContain('Dark Elf (Drow)');
      expect(component.raceOptions).toContain('Half-Elf');
      expect(component.raceOptions).toContain('Hill Dwarf');
      expect(component.raceOptions).toContain('Mountain Dwarf');
      expect(component.raceOptions).toContain('Lightfoot Halfling');
      expect(component.raceOptions).toContain('Stout Halfling');
      expect(component.raceOptions).toContain('Forest Gnome');
      expect(component.raceOptions).toContain('Rock Gnome');
      expect(component.raceOptions).not.toContain('Warforged');
      // 2014 Human gets +1 to all 6 stats when Step 4 overrides remain None
      expect(component.getFinalStat('STR')).toBe(16);
      expect(component.getFinalStat('CHA')).toBe(9);

      // Selecting High Elf in 2014 pre-fills +2 DEX, +1 INT
      component.onManualRaceChange('High Elf');
      expect(component.adjPlus2).toBe('DEX');
      expect(component.adjPlus1).toBe('INT');
      expect(component.getFinalStat('DEX')).toBe(16);
      expect(component.getFinalStat('INT')).toBe(13);

      // Selecting Mountain Dwarf in 2014 pre-fills +2 CON, +2 STR
      component.onManualRaceChange('Mountain Dwarf');
      expect(component.adjPlus2).toBe('CON');
      expect(component.adjPlus1).toBe('STR');
      expect(component.adjPlus1Alt).toBe('STR');
      expect(component.getFinalStat('CON')).toBe(15);
      expect(component.getFinalStat('STR')).toBe(17);

      // Legacy Dwarf preset fallback still pre-fills +2 CON
      component.onManualRaceChange('Dwarf');
      expect(component.adjPlus2).toBe('CON');
      expect(component.getFinalStat('CON')).toBe(15);

      // Selecting Half-Elf in 2014 AI Forge and toggling to 2024 resets aiRace instead of blanking
      component.aiRace = 'Half-Elf';
      component.toggleEditionAndRefresh();
      httpMock.expectOne((req) => req.url.includes('/rules/feats')).flush([]);
      httpMock.expectOne((req) => req.url.includes('/rules/spells')).flush([]);
      httpMock.expectOne((req) => req.url.includes('/rules/class-choices')).flush({});

      expect(component.is2024).toBe(true);
      expect(component.raceOptions).toContain('Warforged');
      expect(component.raceOptions).not.toContain('Half-Elf');
      expect(component.aiRace).toBe('AI Choice');
      expect(component.bgOptions).toContain('Farmer');
    });

    it('includes Artificer in classOptions, classColors, and primaryStatsMap', () => {
      expect(component.classOptions).toContain('Artificer');
      expect(component.classColors['Artificer']).toBeTruthy();
      expect(component.primaryStatsMap['Artificer']).toEqual(['INT', 'CON']);
    });
  });
});
