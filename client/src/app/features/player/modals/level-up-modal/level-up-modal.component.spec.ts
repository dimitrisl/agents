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

  it('treats numbered sibling choice types like spell_secret_1 and spell_secret_2 as one group', () => {
    fixture.componentRef.setInput('nextLevel', 10);
    fixture.componentRef.setInput('levelUpAnalysis', {
      new_total_level: 10,
      class_upgraded: 'Bard',
      new_class_level: 10,
      hp_increase: 7,
      new_total_hp: 70,
      automatic_features: [],
      choices_required: [
        {
          type: 'spell_secret_1',
          label: 'Magical Secrets Spell #1',
          options: ['Counterspell', 'Fireball', 'Find Greater Steed'],
        },
        {
          type: 'spell_secret_2',
          label: 'Magical Secrets Spell #2',
          options: ['Counterspell', 'Fireball', 'Find Greater Steed'],
        },
      ],
      updated_proficiency_bonus: 4,
      updated_spell_slots: {},
    });
    fixture.componentRef.setInput('open', true);

    const choices = component.levelUpAnalysis!.choices_required!;
    fixture.componentRef.setInput('userChoices', {
      level_up_class: 'Bard',
      spell_secret_1_0: 'Counterspell',
      spell_secret_2_1: 'Fireball',
    });
    fixture.detectChanges();

    expect(component.availableOptionsFor(choices[1], 1)).not.toContain('Counterspell');
    expect(component.hasDuplicateSiblingChoices).toBe(false);

    fixture.componentRef.setInput('userChoices', {
      level_up_class: 'Bard',
      spell_secret_1_0: 'Counterspell',
      spell_secret_2_1: 'Counterspell',
    });
    fixture.detectChanges();
    expect(component.hasDuplicateSiblingChoices).toBe(true);
  });

  it('supports optional Spell Swap while enforcing pair completeness and preventing duplicates with learned spells', () => {
    fixture.componentRef.setInput('nextLevel', 12);
    fixture.componentRef.setInput('character', {
      ...mockCharacter,
      char_class: 'Ranger',
      char_level: 11,
      classes: [{ class_name: 'Ranger', level: 11, subclass: 'Horizon Walker' }],
    });
    const spellChoice = {
      type: 'spell',
      label: 'Learn/Prepare a Ranger Spell',
      options: ['Revivify', 'Conjure Barrage', 'Pass without Trace'],
    };
    fixture.componentRef.setInput('levelUpAnalysis', {
      hp_increase: 8,
      new_total_hp: 100,
      automatic_changes: [],
      choices_required: [spellChoice],
      replaceable_spells: ['Speak with Animals', 'Silence'],
      spell_swap_options: ['Revivify', 'Conjure Barrage', 'Pass without Trace'],
    });
    fixture.componentRef.setInput('open', true);

    // Optional by default: leaving both empty is valid
    fixture.componentRef.setInput('userChoices', { level_up_class: 'Ranger', spell_0: 'Conjure Barrage' });
    fixture.detectChanges();
    expect(component.hasSpellSwapAvailable).toBe(true);
    expect(component.hasIncompleteSpellSwap).toBe(false);
    expect(component.filteredSwapInOptions).not.toContain('Conjure Barrage');
    expect(component.filteredSwapInOptions).toContain('Revivify');

    // Picking only spell_swap_out marks swap incomplete & disables Apply
    component.onChoiceChange('spell_swap_out', 'Silence');
    fixture.detectChanges();
    expect(component.hasIncompleteSpellSwap).toBe(true);
    let applyBtn = Array.from(document.body.querySelectorAll('button')).find((b) =>
      b.textContent?.includes('Apply Level Up')
    ) as HTMLButtonElement | null;
    expect(applyBtn?.disabled).toBe(true);

    // Picking spell_swap_in completes swap and excludes it from spell_0 choice
    component.onChoiceChange('spell_swap_in', 'Revivify');
    fixture.detectChanges();
    expect(component.hasIncompleteSpellSwap).toBe(false);
    expect(component.availableOptionsFor(spellChoice, 0)).not.toContain('Revivify');
    applyBtn = Array.from(document.body.querySelectorAll('button')).find((b) =>
      b.textContent?.includes('Apply Level Up')
    ) as HTMLButtonElement | null;
    expect(applyBtn?.disabled).toBe(false);

    // Clearing spell_swap_out back to None resets both swap keys
    component.onChoiceChange('spell_swap_out', '');
    fixture.detectChanges();
    expect(component.userChoices['spell_swap_out']).toBeUndefined();
    expect(component.userChoices['spell_swap_in']).toBeUndefined();
    expect(component.hasIncompleteSpellSwap).toBe(false);
  });

  it('clears stale spell swap and spell choices when changing subclass and blocks Magical Secrets swap duplicates', () => {
    fixture.componentRef.setInput('nextLevel', 3);
    fixture.componentRef.setInput('character', {
      ...mockCharacter,
      char_class: 'Fighter',
      char_level: 2,
      classes: [{ class_name: 'Fighter', level: 2 }],
    });
    fixture.componentRef.setInput('levelUpAnalysis', {
      hp_increase: 8,
      new_total_hp: 28,
      automatic_changes: [],
      choices_required: [
        { type: 'subclass', label: 'Subclass', options: ['Eldritch Knight', 'Champion'] },
        { type: 'spell', label: 'Learn Spell', options: ['Shield', 'Magic Missile'] },
      ],
      replaceable_spells: ['Grease'],
      spell_swap_options: ['Shield', 'Magic Missile'],
    });
    fixture.componentRef.setInput('userChoices', {
      level_up_class: 'Fighter',
      subclass_0: 'Eldritch Knight',
      spell_1: 'Shield',
      spell_swap_out: 'Grease',
      spell_swap_in: 'Magic Missile',
    });
    fixture.componentRef.setInput('open', true);
    fixture.detectChanges();

    component.onChoiceChange('subclass_0', 'Champion');
    fixture.detectChanges();
    expect(component.userChoices['spell_swap_out']).toBeUndefined();
    expect(component.userChoices['spell_swap_in']).toBeUndefined();
    expect(component.userChoices['spell_1']).toBeUndefined();

    // Bard Magical Secrets overlap with Spell Swap
    const secretChoice = {
      type: 'spell_secret_1',
      label: 'Magical Secrets',
      options: ['Counterspell', 'Fireball'],
    };
    fixture.componentRef.setInput('levelUpAnalysis', {
      hp_increase: 7,
      new_total_hp: 70,
      automatic_changes: [],
      choices_required: [secretChoice],
      replaceable_spells: ['Bane'],
      spell_swap_options: ['Counterspell', 'Hypnotic Pattern'],
    });
    fixture.componentRef.setInput('userChoices', {
      level_up_class: 'Bard',
      spell_secret_1_0: 'Counterspell',
      spell_swap_out: 'Bane',
      spell_swap_in: 'Hypnotic Pattern',
    });
    fixture.detectChanges();

    expect(component.filteredSwapInOptions).not.toContain('Counterspell');
    expect(component.availableOptionsFor(secretChoice, 0)).not.toContain('Hypnotic Pattern');
    expect(component.hasDuplicateSiblingChoices).toBe(false);

    fixture.componentRef.setInput('userChoices', {
      level_up_class: 'Bard',
      spell_secret_1_0: 'Counterspell',
      spell_swap_out: 'Bane',
      spell_swap_in: 'Counterspell',
    });
    fixture.detectChanges();
    expect(component.hasDuplicateSiblingChoices).toBe(true);
  });

  it('locks ineligible multiclass options, prevents switching to locked classes, and renders Level 1 summary & 13-class matrix', () => {
    // Thorin: Fighter 3, STR 16, DEX 12, CON 16, INT 10, WIS 12, CHA 8
    // Meets STR 13 -> Barbarian (STR 13) is eligible; Rogue (DEX 13), Wizard (INT 13), Paladin (STR 13 & CHA 13) are locked
    fixture.componentRef.setInput('character', {
      ...mockCharacter,
      classes: [{ class_name: 'Fighter', level: 3 }],
      saving_throws: ['STR', 'CON'],
    });
    fixture.componentRef.setInput('nextLevel', 4);
    fixture.componentRef.setInput('userChoices', { level_up_class: 'Fighter' });
    fixture.componentRef.setInput('open', true);
    fixture.detectChanges();

    const options = Array.from(
      document.body.querySelectorAll('select option')
    ) as HTMLOptionElement[];
    const wizardOpt = options.find((o) => o.value === 'Wizard');
    const barbOpt = options.find((o) => o.value === 'Barbarian');
    const paladinOpt = options.find((o) => o.value === 'Paladin');

    expect(wizardOpt?.disabled).toBe(true);
    expect(wizardOpt?.textContent).toContain('🔒 Wizard');
    expect(wizardOpt?.textContent).toContain('INT 13');
    expect(paladinOpt?.disabled).toBe(true);
    expect(barbOpt?.disabled).toBe(false);
    expect(barbOpt?.textContent).toContain('✓ Barbarian');

    // Guard blocks switching directly to an ineligible class
    const emitSpy = jest.spyOn(component.userChoicesChange, 'emit');
    component.onClassChange('Wizard');
    expect(emitSpy).not.toHaveBeenCalled();

    // Expand 13-Class Matrix
    const matrixToggle = document.body.querySelector(
      '[data-testid="toggle-multiclass-matrix"]'
    ) as HTMLButtonElement | null;
    expect(matrixToggle).not.toBeNull();
    matrixToggle!.click();
    fixture.detectChanges();

    const matrix = document.body.querySelector('[data-testid="multiclass-eligibility-matrix"]');
    expect(matrix?.textContent).toContain('Multiclass Eligibility Overview (13 Classes)');
    expect(matrix?.textContent).toContain('INT 13');

    // Select eligible Barbarian from matrix -> switches level_up_class and shows Level 1 summary card
    const matrixButtons = Array.from(
      matrix!.querySelectorAll('button')
    ) as HTMLButtonElement[];
    const barbMatrixBtn = matrixButtons.find((b) => b.textContent?.includes('Barbarian'));
    expect(barbMatrixBtn?.disabled).toBe(false);
    barbMatrixBtn!.click();
    fixture.detectChanges();

    expect(emitSpy).toHaveBeenCalledWith({ level_up_class: 'Barbarian' });
    const summaryCard = document.body.querySelector('[data-testid="multiclass-summary-card"]');
    expect(summaryCard?.textContent).toContain('Multiclassing into Barbarian (Level 1)');
    expect(summaryCard?.textContent).toContain('Hit Die d12');
    expect(summaryCard?.textContent).toContain('Shields');
    expect(summaryCard?.textContent).toContain('Simple Weapons');
    expect(summaryCard?.textContent).toContain('Martial Weapons');
    expect(summaryCard?.textContent).toContain('STR, CON');
  });

  it('requires PHB multiclass bonus skill selection before enabling Apply Level Up and warns when current class lacks 13+', () => {
    fixture.componentRef.setInput('character', {
      ...mockCharacter,
      stats: { STR: 10, DEX: 10, CON: 14, INT: 16, WIS: 14, CHA: 14 },
      classes: [{ class_name: 'Fighter', level: 3 }],
    });
    fixture.componentRef.setInput('nextLevel', 4);
    fixture.componentRef.setInput('open', true);
    fixture.detectChanges();

    const warning = document.body.querySelector('[data-testid="multiclass-current-warning"]');
    expect(warning?.textContent).toContain('Fighter requires STR 13 or DEX 13');

    // Now test eligible Fighter -> Rogue L1 requiring a bonus skill pick
    fixture.componentRef.setInput('character', {
      ...mockCharacter,
      stats: { STR: 16, DEX: 14, CON: 14, INT: 10, WIS: 12, CHA: 8 },
      classes: [{ class_name: 'Fighter', level: 4 }],
    });
    fixture.componentRef.setInput('nextLevel', 5);
    fixture.componentRef.setInput('levelUpAnalysis', {
      hp_increase: 7,
      new_total_hp: 45,
      automatic_changes: [
        { name: 'Multiclass Proficiencies (Rogue)', description: "Light Armor, Thieves' Tools" },
      ],
      choices_required: [
        { type: 'skill', label: 'Multiclass Bonus Skill (Rogue)', options: ['Acrobatics', 'Stealth'] },
      ],
    });
    fixture.componentRef.setInput('userChoices', { level_up_class: 'Rogue' });
    fixture.detectChanges();

    let applyBtn = Array.from(document.body.querySelectorAll('button')).find((b) =>
      b.textContent?.includes('Apply Level Up')
    ) as HTMLButtonElement | null;
    expect(component.hasIncompleteMulticlassSkillChoice).toBe(true);
    expect(applyBtn?.disabled).toBe(true);

    fixture.componentRef.setInput('userChoices', { level_up_class: 'Rogue', skill_0: 'Acrobatics' });
    fixture.detectChanges();

    applyBtn = Array.from(document.body.querySelectorAll('button')).find((b) =>
      b.textContent?.includes('Apply Level Up')
    ) as HTMLButtonElement | null;
    expect(component.hasIncompleteMulticlassSkillChoice).toBe(false);
    expect(applyBtn?.disabled).toBe(false);
  });

  it('resets transient UI state across modal close/hero switch and preserves custom classes & lowercase matching', () => {
    fixture.componentRef.setInput('character', {
      ...mockCharacter,
      char_id: 'hero-a',
      char_class: 'fighter',
      classes: [
        { class_name: 'fighter', level: 3 },
        { class_name: 'Blood Hunter', level: 1 },
      ],
    });
    fixture.componentRef.setInput('open', true);
    fixture.detectChanges();

    // Canonical lowercase matching + non-canonical custom class preservation
    expect(component.levelUpClass).toBe('Fighter');
    expect(component.existingClassOptions.map((o) => o.class_name)).toContain('Blood Hunter');

    component.showMulticlassMatrix = true;
    component.showRecommendations = true;
    component.planningLevel = 7;

    // Closing modal resets transient state
    fixture.componentRef.setInput('open', false);
    fixture.detectChanges();
    expect(component.showMulticlassMatrix).toBe(false);
    expect(component.showRecommendations).toBe(false);
    expect(component.planningLevel).toBeNull();

    // Switching hero while open also resets transient state
    fixture.componentRef.setInput('open', true);
    fixture.detectChanges();
    component.showMulticlassMatrix = true;
    component.showRecommendations = true;
    fixture.componentRef.setInput('character', {
      ...mockCharacter,
      char_id: 'hero-b',
      char_name: 'Lyra',
      char_class: 'Wizard',
      classes: [{ class_name: 'Wizard', level: 4 }],
    });
    fixture.detectChanges();
    expect(component.showMulticlassMatrix).toBe(false);
    expect(component.showRecommendations).toBe(false);
  });

  it('disables Apply during isAnalyzing/isApplying, cancels in-flight recommendations, and requires Bard instrument tool pick', () => {
    fixture.componentRef.setInput('character', {
      ...mockCharacter,
      stats: { STR: 16, DEX: 14, CON: 14, INT: 10, WIS: 12, CHA: 14 },
      classes: [{ class_name: 'Fighter', level: 4 }],
    });
    fixture.componentRef.setInput('nextLevel', 5);
    fixture.componentRef.setInput('levelUpAnalysis', {
      hp_increase: 7,
      new_total_hp: 45,
      automatic_changes: [],
      choices_required: [
        { type: 'skill', label: 'Multiclass Bard: Choose 1 Bonus Skill Proficiency', options: ['Arcana'] },
        { type: 'tool', label: 'Multiclass Bard: Choose 1 Musical Instrument', options: ['Lute', 'Flute'] },
      ],
    });
    fixture.componentRef.setInput('userChoices', { level_up_class: 'Bard', skill_0: 'Arcana' });
    fixture.componentRef.setInput('open', true);
    fixture.detectChanges();

    // Missing tool_1 keeps Apply disabled even with skill_0 filled
    let applyBtn = Array.from(document.body.querySelectorAll('button')).find((b) =>
      b.textContent?.includes('Apply Level Up')
    ) as HTMLButtonElement | null;
    expect(component.hasIncompleteMulticlassChoices).toBe(true);
    expect(applyBtn?.disabled).toBe(true);

    // Selecting tool_1 enables Apply
    fixture.componentRef.setInput('userChoices', { level_up_class: 'Bard', skill_0: 'Arcana', tool_1: 'Lute' });
    fixture.detectChanges();
    expect(component.hasIncompleteMulticlassChoices).toBe(false);
    expect(applyBtn?.disabled).toBe(false);

    // isAnalyzing shows spinner indicator and locks Apply
    fixture.componentRef.setInput('isAnalyzing', true);
    fixture.detectChanges();
    expect(document.body.querySelector('[data-testid="level-up-analyzing-indicator"]')).not.toBeNull();
    expect(applyBtn?.disabled).toBe(true);

    // isApplying sets aria-busy & disables both Cancel and Apply
    fixture.componentRef.setInput('isAnalyzing', false);
    fixture.componentRef.setInput('isApplying', true);
    fixture.detectChanges();
    expect(applyBtn?.disabled).toBe(true);
    expect(applyBtn?.getAttribute('aria-busy')).toBe('true');

    // Resetting isApplying re-enables; in-flight recommendations cancel on modal close
    fixture.componentRef.setInput('isApplying', false);
    component.fetchRecommendations();
    expect(component.isLoadingRecommendations).toBe(true);
    const recReq = httpMock.expectOne((r) => r.url.includes('/forge/level-up-recommendations'));

    fixture.componentRef.setInput('open', false);
    fixture.detectChanges();
    expect(component.isLoadingRecommendations).toBe(false);
    expect(recReq.cancelled).toBe(true);
  });
});
