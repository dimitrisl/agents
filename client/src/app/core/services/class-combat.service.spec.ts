import { TestBed } from '@angular/core/testing';
import { HttpClientTestingModule, HttpTestingController } from '@angular/common/http/testing';
import { ClassCombatService } from './class-combat.service';
import { CharacterSchema } from '../models/character.model';
import { environment } from '../../../environments/environment';


describe('ClassCombatService', () => {
  let service: ClassCombatService;
  let httpMock: HttpTestingController;

  const mockChar: CharacterSchema = {
    char_id: 'c1',
    name: 'Test Hero',
    char_class: 'Fighter',
    char_level: 5,
    subclass: 'Champion',
    dnd_edition: '2014 Edition',
    stats: { STR: 18, DEX: 14, CON: 16, INT: 10, WIS: 12, CHA: 8 }
  } as any;

  beforeEach(() => {
    TestBed.configureTestingModule({
      imports: [HttpClientTestingModule],
      providers: [ClassCombatService]
    });
    service = TestBed.inject(ClassCombatService);
    httpMock = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    httpMock.verify();
  });

  it('should be created', () => {
    expect(service).toBeTruthy();
  });

  describe('buildContext', () => {
    it('should calculate modifiers and profBonus correctly', () => {
      const ctx = service.buildContext(mockChar);
      expect(ctx.level).toBe(5);
      expect(ctx.profBonus).toBeGreaterThanOrEqual(2); // Level 5 is +3
      expect(ctx.mods.STR).toBe(4);
      expect(ctx.mods.DEX).toBe(2);
      expect(ctx.mods.CON).toBe(3);
      expect(ctx.mods.INT).toBe(0);
      expect(ctx.mods.WIS).toBe(1);
      expect(ctx.mods.CHA).toBe(-1);
      expect(ctx.is2024).toBe(false);
    });

    it('should default stats to 10 if missing', () => {
      const emptyChar = { char_level: 1, dnd_edition: '2024 Edition' } as any;
      const ctx = service.buildContext(emptyChar);
      expect(ctx.mods.STR).toBe(0);
      expect(ctx.mods.DEX).toBe(0);
      expect(ctx.is2024).toBe(true);
    });
  });

  describe('getProfile', () => {
    it('should fetch combat profile from backend and append universal actions', () => {
      service.getProfile(mockChar).subscribe(profile => {
        expect(profile.cantripTier).toBe(2); // Level 5
        expect(profile.actions.length).toBe(2); // 1 from API + 1 universal (Hit Die)
        expect(profile.actions[0].id).toBe('action-1');
        expect(profile.actions[1].id).toBe('hit-die');
      });

      const req = httpMock.expectOne(`${environment.apiBaseUrl}/rules/combat-profile`);
      expect(req.request.method).toBe('POST');
      expect(req.request.body).toEqual({
        classes: [{ class_name: 'Fighter', level: 5, subclass: 'Champion' }],
        edition: '2014 Edition'
      });

      req.flush({
        actions: [{ id: 'action-1', name: 'Action Surge', kind: 'feature' }],
        extraCritDice: 0,
        critThreshold: 19,
        cantripTier: 2
      });
    });

    it('should return fallback profile if char_class is empty', () => {
      const emptyChar = { ...mockChar, char_class: '' } as any;
      service.getProfile(emptyChar).subscribe(profile => {
        expect(profile.actions.length).toBe(1);
        expect(profile.actions[0].id).toBe('hit-die');
      });
      httpMock.expectNone(`${environment.apiBaseUrl}/rules/combat-profile`);
    });

    it('should fallback to universal actions on HTTP error', () => {
      service.getProfile(mockChar).subscribe(profile => {
        expect(profile.actions.length).toBe(1);
        expect(profile.actions[0].id).toBe('hit-die');
      });

      const req = httpMock.expectOne(`${environment.apiBaseUrl}/rules/combat-profile`);
      req.error(new ProgressEvent('Network error'));
    });
  });

  describe('ridersOf', () => {
    it('should return only rider actions', () => {
      const profile = {
        actions: [
          { id: '1', kind: 'rider' },
          { id: '2', kind: 'attack' },
          { id: '3', kind: 'rider' },
        ],
        extraCritDice: 0,
        critThreshold: 20,
        cantripTier: 1
      } as any;
      const riders = service.ridersOf(profile);
      expect(riders.length).toBe(2);
      expect(riders[0].id).toBe('1');
      expect(riders[1].id).toBe('3');
    });
  });

  describe('universalActions', () => {
    it('should include Cantrip Scaling for casters', () => {
      const casterChar = { ...mockChar, char_class: 'Wizard', char_level: 11 } as any;
      service.getProfile(casterChar).subscribe(profile => {
        const hitDie = profile.actions.find(a => a.id === 'hit-die');
        const cantrip = profile.actions.find(a => a.id === 'cantrip-tier');

        expect(hitDie).toBeTruthy();
        expect(cantrip).toBeTruthy();
        expect(cantrip?.notation).toBe('×3 dice');
      });

      const req = httpMock.expectOne(`${environment.apiBaseUrl}/rules/combat-profile`);
      req.flush({ actions: [] });
    });
  });
});
