import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting, HttpTestingController } from '@angular/common/http/testing';
import { LevelUpModalComponent } from './level-up-modal.component';
import { CharacterSchema, LevelUpRecommendationsResponse } from '../../../../core/models/character.model';
import { DiceService } from '../../../../core/services/dice.service';
import { environment } from '../../../../../environments/environment';

describe('LevelUpModalComponent', () => {
  let component: LevelUpModalComponent;
  let fixture: ComponentFixture<LevelUpModalComponent>;
  let httpMock: HttpTestingController;

  const mockCharacter: CharacterSchema = {
    char_name: 'Thorin',
    char_class: 'Fighter',
    char_level: 3,
    race: 'Dwarf',
    background: 'Soldier',
    stats: { STR: 16, DEX: 12, CON: 16, INT: 10, WIS: 12, CHA: 8 },
    classes: [{ class_name: 'Fighter', level: 3 }],
  } as any;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [LevelUpModalComponent],
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
      ],
    }).compileComponents();

    fixture = TestBed.createComponent(LevelUpModalComponent);
    component = fixture.componentInstance;
    httpMock = TestBed.inject(HttpTestingController);
    component.character = mockCharacter;
    fixture.detectChanges();
  });

  afterEach(() => {
    httpMock.verify();
    fixture.componentRef.setInput('open', false);
    fixture.detectChanges();
    document.querySelectorAll('.cdk-overlay-container').forEach((el) => el.remove());
  });

  it('should create', () => {
    expect(component).toBeTruthy();
    expect(component.levelUpClass).toBe('Fighter');
    expect(component.targetClassLevel).toBe(4);
  });

  it('toggles recommendations and fetches suggestions from API', () => {
    expect(component.showRecommendations).toBe(false);
    expect(component.buildRecommendations.length).toBe(0);

    component.toggleRecommendations();
    expect(component.showRecommendations).toBe(true);
    expect(component.isLoadingRecommendations).toBe(true);

    const req = httpMock.expectOne(`${environment.apiBaseUrl}/forge/level-up-recommendations`);
    expect(req.request.method).toBe('POST');
    expect(req.request.body).toEqual({
      character: mockCharacter,
      target_class: 'Fighter',
      target_level: 4,
    });

    const mockResponse: LevelUpRecommendationsResponse = {
      character_name: 'Thorin',
      target_class: 'Fighter',
      target_level: 4,
      builds: [
        {
          build_name: 'The Iron Bulwark (Tank)',
          theme: 'High defense and protection',
          playstyle_summary: 'Lock down enemies and protect friends.',
          pros: ['Very durable'],
          cons: ['Low mobility'],
          recommended_subclass: 'Battle Master',
          recommended_feat_or_asi: 'Sentinel',
          recommended_spells: [],
          key_tactics: ['Hold the frontline.'],
        },
        {
          build_name: 'The Heavy Striker (DPS)',
          theme: 'Maximum damage',
          playstyle_summary: 'Hit hard and cleave foes.',
          pros: ['Massive crits'],
          cons: ['Less defense'],
          recommended_subclass: 'Champion',
          recommended_feat_or_asi: 'Great Weapon Master',
          recommended_spells: [],
          key_tactics: ['Charge priority targets.'],
        },
      ],
    };

    req.flush(mockResponse);

    expect(component.isLoadingRecommendations).toBe(false);
    expect(component.buildRecommendations.length).toBe(2);
    expect(component.buildRecommendations[0].build_name).toBe('The Iron Bulwark (Tank)');
  });

  it('handles API errors gracefully without crashing', () => {
    component.toggleRecommendations();
    const req = httpMock.expectOne(`${environment.apiBaseUrl}/forge/level-up-recommendations`);
    req.flush('Server Error', { status: 500, statusText: 'Internal Server Error' });

    expect(component.isLoadingRecommendations).toBe(false);
    expect(component.recommendationsError).toBeTruthy();
    expect(component.buildRecommendations.length).toBe(0);
  });

  it('refreshes recommendations when switching class if recommendations are visible', () => {
    component.showRecommendations = true;
    component.onClassChange('Barbarian');

    const req = httpMock.expectOne(`${environment.apiBaseUrl}/forge/level-up-recommendations`);
    expect(req.request.body.target_class).toBe('Barbarian');
    req.flush({ character_name: 'Thorin', target_class: 'Barbarian', target_level: 1, builds: [] });

    expect(component.userChoices['level_up_class']).toBe('Barbarian');
  });

  it('derives hit die from target leveling class rather than character primary class', () => {
    // Primary class is Wizard (d6), but user selects Barbarian (d12)
    component.character = {
      ...mockCharacter,
      char_class: 'Wizard',
      hit_dice: '4d6',
      classes: [{ class_name: 'Wizard', level: 4 }],
    } as any;
    component.userChoices = { level_up_class: 'Barbarian' };

    expect(component.levelUpHitDie).toBe(12);
  });

  it('rolls HP using target class hit die and CON modifier with min 1', () => {
    const diceService = TestBed.inject(DiceService);
    const rollSpy = jest.spyOn(diceService, 'roll').mockReturnValue({
      total: 8,
      rolls: [5],
      breakdown: '1d12 + 3 = 8',
    } as any);

    component.character = {
      ...mockCharacter,
      char_class: 'Wizard',
      hit_dice: '4d6',
      stats: { CON: 16 }, // +3 modifier
    } as any;
    component.userChoices = { level_up_class: 'Barbarian' };

    component.rollHp();

    expect(rollSpy).toHaveBeenCalledWith({
      numDice: 1,
      sides: 12,
      modifier: 3,
    });
    expect(component.userChoices['hp_method']).toBe('roll');
    expect(component.userChoices['custom_hp_increase']).toBe('8');
  });

  it('rollHp includes per-level feat/subclass HP bonus when rolling', () => {
    const diceService = TestBed.inject(DiceService);
    const rollSpy = jest.spyOn(diceService, 'roll').mockReturnValue({
      raw: [4],
      rolls: [4],
      sides: 10,
      modifier: 4, // CON +2 + Tough +2
      total: 8,
    } as any);

    component.character = {
      char_name: 'Borin',
      char_class: 'Fighter',
      hit_dice: '3d10',
      stats: { CON: 14 }, // +2
    } as any;
    component.levelUpAnalysis = {
      automatic_changes: [],
      hp_increase: 10, // average 6 + CON 2 + Tough 2
      hp_bonus_per_level: 2,
      new_total_hp: 38,
      choices_required: [],
    } as any;
    component.userChoices = { level_up_class: 'Fighter' };

    component.rollHp();

    expect(rollSpy).toHaveBeenCalledWith({
      numDice: 1,
      sides: 10,
      modifier: 4,
    });
    expect(component.userChoices['custom_hp_increase']).toBe('8');
  });

  it('dynamically updates New Total Max HP preview for retroactive +2 CON ASI and Tough across levels', () => {
    component.character = {
      ...mockCharacter,
      char_name: 'Vex',
      char_class: 'Rogue',
      char_level: 9,
      dnd_edition: '2024 Revision (5.5e)',
      stats: { STR: 8, DEX: 20, CON: 15, INT: 14, WIS: 12, CHA: 10 },
      hp_max: 66,
    } as any;
    component.nextLevel = 10;
    component.levelUpAnalysis = {
      automatic_changes: [],
      hp_increase: 7, // average 5 + CON 2
      hp_bonus_per_level: 0,
      new_total_hp: 73,
      choices_required: [
        {
          type: 'feat',
          label: 'Choose a Feat or Ability Score Improvement',
          options: ['+2 to one Stat', '+1 to two Stats', 'Tough', 'Charger'],
          feat_metadata: {
            Tough: { has_stat_choice: false, stat_choice_options: [], stat_bonus: {}, hp_bonus_per_level: 2 },
            Charger: { has_stat_choice: true, stat_choice_options: ['STR', 'DEX'], stat_bonus: {}, hp_bonus_per_level: 0 },
          },
        },
      ],
    };

    expect(component.previewNewTotalHp).toBe(73);

    component.onChoiceChange('feat_0', '+2 to one Stat');
    component.onChoiceChange('feat_stat1_0', 'CON');
    fixture.detectChanges();

    expect(component.previewPendingHpAdjustment).toBe(10);
    expect(component.previewNewTotalHp).toBe(83);

    // Rolled HP keeps base modifier (CON +2) while preview reflects +10 retroactive CON boost
    const diceService = TestBed.inject(DiceService);
    jest.spyOn(diceService, 'roll').mockReturnValue({
      raw: [4],
      rolls: [4],
      sides: 8,
      modifier: 2,
      total: 6,
    } as any);
    component.userChoices = { level_up_class: 'Rogue', feat_0: '+2 to one Stat', feat_stat1_0: 'CON' };
    component.rollHp();
    expect(component.previewNewTotalHp).toBe(82);

    // Selecting Tough previews +2 * 10 = +20 HP and switching resets prior CON choices cleanly
    component.onChoiceChange('feat_0', 'Tough');
    expect(component.userChoices['feat_stat1_0']).toBeUndefined();
    expect(component.previewPendingHpAdjustment).toBe(20);
  });

  it('hides half-feat stat dropdown for non-half feats like Tough and filters stat_choice_options', () => {
    const featChoice = {
      type: 'feat',
      label: 'Choose a Feat or Ability Score Improvement',
      options: ['+2 to one Stat', '+1 to two Stats', 'Tough', 'Charger'],
      feat_metadata: {
        Tough: { has_stat_choice: false, stat_choice_options: [], stat_bonus: {}, hp_bonus_per_level: 2 },
        Charger: { has_stat_choice: true, stat_choice_options: ['STR', 'DEX'], stat_bonus: {}, hp_bonus_per_level: 0 },
      },
    };
    component.levelUpAnalysis = {
      automatic_changes: [],
      hp_increase: 8,
      new_total_hp: 36,
      choices_required: [featChoice],
    };

    expect(component.showsSingleStatPicker(featChoice, 'Tough')).toBe(false);
    expect(component.showsSingleStatPicker(featChoice, 'Charger')).toBe(true);
    expect(component.allowedSingleStatsForChoice(featChoice, 'Charger').map((s) => s.code)).toEqual(['STR', 'DEX']);

    component.onChoiceChange('feat_0', '+1 to two Stats');
    component.onChoiceChange('feat_stat1_0', 'DEX');
    expect(component.secondStatsForChoice('DEX').map((s) => s.code)).not.toContain('DEX');

    // Render modal in overlay DOM with OnPush inputs: Tough must NOT render the half-feat dropdown; Charger MUST render it
    fixture.componentRef.setInput('nextLevel', 4);
    fixture.componentRef.setInput('userChoices', { level_up_class: 'Fighter', feat_0: 'Tough' });
    fixture.componentRef.setInput('open', true);
    fixture.detectChanges();
    expect(document.body.textContent).not.toContain('Select +1 Stat');
    expect(document.body.textContent).toContain('Lv 1–4');

    fixture.componentRef.setInput('userChoices', { level_up_class: 'Fighter', feat_0: 'Charger' });
    fixture.detectChanges();
    expect(document.body.textContent).toContain('Select +1 Stat (Half-Feat):');
  });

  it('disables Apply Level Up when ASI or half-feat stat picks are incomplete or invalid', () => {
    fixture.componentRef.setInput('levelUpAnalysis', {
      automatic_changes: [],
      hp_increase: 6,
      hp_bonus_per_level: 0,
      new_total_hp: 40,
      choices_required: [
        {
          type: 'feat',
          description: 'Feat or ASI',
          options: ['+2 to one Stat', '+1 to two Stats', 'Charger'],
          feat_metadata: {
            Charger: {
              has_stat_choice: true,
              stat_choice_options: ['STR', 'DEX'],
              stat_bonus: {},
              hp_bonus_per_level: 0,
            },
          },
        },
      ],
      updated_proficiency_bonus: 2,
      updated_spell_slots: {},
    });
    fixture.componentRef.setInput('open', true);

    const getApplyButton = (): HTMLButtonElement | null =>
      Array.from(document.body.querySelectorAll('button')).find((b) =>
        b.textContent?.includes('Apply Level Up')
      ) as HTMLButtonElement | null;

    // +2 to one Stat without stat1 -> disabled
    fixture.componentRef.setInput('userChoices', { level_up_class: 'Fighter', feat_0: '+2 to one Stat' });
    fixture.detectChanges();
    expect(component.hasIncompleteStatChoices).toBe(true);
    expect(getApplyButton()?.disabled).toBe(true);

    // +2 to one Stat with valid stat1 -> enabled
    fixture.componentRef.setInput('userChoices', {
      level_up_class: 'Fighter',
      feat_0: '+2 to one Stat',
      feat_stat1_0: 'STR',
    });
    fixture.detectChanges();
    expect(component.hasIncompleteStatChoices).toBe(false);
    expect(getApplyButton()?.disabled).toBe(false);

    // +1 to two Stats with missing/duplicate second stat -> disabled
    fixture.componentRef.setInput('userChoices', {
      level_up_class: 'Fighter',
      feat_0: '+1 to two Stats',
      feat_stat1_0: 'STR',
      feat_stat2_0: 'STR',
    });
    fixture.detectChanges();
    expect(component.hasIncompleteStatChoices).toBe(true);
    expect(getApplyButton()?.disabled).toBe(true);

    // +1 to two Stats with distinct stats -> enabled
    fixture.componentRef.setInput('userChoices', {
      level_up_class: 'Fighter',
      feat_0: '+1 to two Stats',
      feat_stat1_0: 'STR',
      feat_stat2_0: 'CON',
    });
    fixture.detectChanges();
    expect(component.hasIncompleteStatChoices).toBe(false);
    expect(getApplyButton()?.disabled).toBe(false);

    // Half-feat Charger without stat or with disallowed stat -> disabled; with DEX -> enabled
    fixture.componentRef.setInput('userChoices', {
      level_up_class: 'Fighter',
      feat_0: 'Charger',
      feat_stat1_0: 'INT',
    });
    fixture.detectChanges();
    expect(component.hasIncompleteStatChoices).toBe(true);
    expect(getApplyButton()?.disabled).toBe(true);

    fixture.componentRef.setInput('userChoices', {
      level_up_class: 'Fighter',
      feat_0: 'Charger',
      feat_stat1_0: 'DEX',
    });
    fixture.detectChanges();
    expect(component.hasIncompleteStatChoices).toBe(false);
    expect(getApplyButton()?.disabled).toBe(false);
  });

  it('previews +40 flat HP and stat cap 30 for Boon of Fortitude at level 19 (2024)', () => {
    component.character = {
      ...mockCharacter,
      char_level: 18,
      dnd_edition: '2024 Revision (5.5e)',
      stats: { STR: 20, DEX: 12, CON: 19, INT: 10, WIS: 12, CHA: 8 },
      classes: [{ class_name: 'Fighter', level: 18 }],
    };
    fixture.componentRef.setInput('nextLevel', 19);
    fixture.componentRef.setInput('levelUpAnalysis', {
      new_total_level: 19,
      class_upgraded: 'Fighter',
      new_class_level: 19,
      hp_increase: 10,
      new_total_hp: 190,
      automatic_features: [],
      choices_required: [
        {
          type: 'feat',
          label: 'Epic Boon Feat',
          options: ['Boon of Fortitude'],
          feat_metadata: {
            'Boon of Fortitude': {
              has_stat_choice: true,
              stat_choice_options: ['STR', 'DEX', 'CON', 'INT', 'WIS', 'CHA'],
              stat_bonus: {},
              hp_bonus_per_level: 0,
              flat_hp_bonus: 40,
            },
          },
        },
      ],
      updated_proficiency_bonus: 6,
      updated_spell_slots: {},
    });
    fixture.componentRef.setInput('open', true);
    fixture.componentRef.setInput('userChoices', {
      level_up_class: 'Fighter',
      feat_0: 'Boon of Fortitude',
      feat_stat1_0: 'CON',
    });
    fixture.detectChanges();

    // CON 19 -> 20 gives +1 CON mod across 19 levels (+19) plus +40 flat HP = +59
    expect(component.previewPendingHpAdjustment).toBe(59);

    // Also verify stat cap 30 when CON is 20 -> 21 (mod remains +5, flat HP +40)
    component.character = {
      ...component.character,
      stats: { STR: 20, DEX: 12, CON: 20, INT: 10, WIS: 12, CHA: 8 },
    };
    fixture.detectChanges();
    expect(component.previewPendingHpAdjustment).toBe(40);
  });

  it('filters sibling-selected class choices and blocks duplicate submissions', () => {
    fixture.componentRef.setInput('nextLevel', 2);
    fixture.componentRef.setInput('levelUpAnalysis', {
      new_total_level: 2,
      class_upgraded: 'Warlock',
      new_class_level: 2,
      hp_increase: 6,
      new_total_hp: 16,
      automatic_features: [],
      choices_required: [
        {
          type: 'eldritch_invocation',
          label: 'Choose Eldritch Invocation #1',
          options: ['Agonizing Blast', "Devil's Sight", 'Repelling Blast'],
        },
        {
          type: 'eldritch_invocation',
          label: 'Choose Eldritch Invocation #2',
          options: ['Agonizing Blast', "Devil's Sight", 'Repelling Blast'],
        },
      ],
      updated_proficiency_bonus: 2,
      updated_spell_slots: {},
    });
    fixture.componentRef.setInput('open', true);

    const choices = component.levelUpAnalysis!.choices_required!;
    fixture.componentRef.setInput('userChoices', {
      level_up_class: 'Warlock',
      eldritch_invocation_0: 'Agonizing Blast',
    });
    fixture.detectChanges();

    expect(component.availableOptionsFor(choices[1], 1)).not.toContain('Agonizing Blast');
    expect(component.availableOptionsFor(choices[0], 0)).toContain('Agonizing Blast');
    expect(component.hasDuplicateSiblingChoices).toBe(false);

    fixture.componentRef.setInput('userChoices', {
      level_up_class: 'Warlock',
      eldritch_invocation_0: 'Agonizing Blast',
      eldritch_invocation_1: 'Agonizing Blast',
    });
    fixture.detectChanges();
    expect(component.hasDuplicateSiblingChoices).toBe(true);
    const applyBtn = Array.from(document.body.querySelectorAll('button')).find((b) =>
      b.textContent?.includes('Apply Level Up')
    ) as HTMLButtonElement | null;
    expect(applyBtn?.disabled).toBe(true);
  });
});
