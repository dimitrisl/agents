import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting, HttpTestingController } from '@angular/common/http/testing';
import { LevelUpModalComponent } from './level-up-modal.component';
import { CharacterSchema, LevelUpRecommendationsResponse } from '../../../../core/models/character.model';
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
});
