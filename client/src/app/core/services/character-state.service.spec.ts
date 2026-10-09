import { TestBed } from '@angular/core/testing';
import { HttpClientTestingModule, HttpTestingController } from '@angular/common/http/testing';
import { CharacterStateService } from './character-state.service';
import { CharacterSchema } from '../models/character.model';
import { environment } from '../../../environments/environment';

describe('CharacterStateService', () => {
  let service: CharacterStateService;
  let httpMock: HttpTestingController;

  const mockChar2014 = { char_id: 'c1', name: 'Hero 2014', dnd_edition: '2014 Edition', stats: { STR: 10, DEX: 12, CON: 14, INT: 16, WIS: 8, CHA: 10 }, passive_perception: 12 } as any;
  const mockChar2024 = { char_id: 'c2', name: 'Hero 2024', dnd_edition: '2024 Revision (5.5e)', stats: { STR: 18, DEX: 10, CON: 14, INT: 8, WIS: 10, CHA: 12 }, passive_perception: 10 } as any;

  beforeEach(() => {
    TestBed.configureTestingModule({
      imports: [HttpClientTestingModule],
      providers: [CharacterStateService]
    });
    service = TestBed.inject(CharacterStateService);
    httpMock = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    httpMock.verify();
  });

  it('should be created', () => {
    expect(service).toBeTruthy();
  });

  describe('loadCharacters', () => {
    it('should fetch and update characters', () => {
      service.loadCharacters().subscribe();

      const req = httpMock.expectOne(`${environment.apiBaseUrl}/characters`);
      expect(req.request.method).toBe('GET');

      req.flush({
        characters: [mockChar2014, mockChar2024],
        unreadable: []
      });

      expect(service.characters().length).toBe(2);
      expect(service.activeCharacter()).toEqual(mockChar2014); // 2014 is default edition
    });

    it('should handle API errors by resetting state', () => {
      service.loadCharacters().subscribe({ error: () => {} });

      const req = httpMock.expectOne(`${environment.apiBaseUrl}/characters`);
      req.error(new ProgressEvent('Network error'));

      expect(service.characters().length).toBe(0);
      expect(service.activeCharacter()).toBeNull();
    });
  });

  describe('ensureLoaded', () => {
    it('should only fetch once if called multiple times', () => {
      service.ensureLoaded().subscribe();
      service.ensureLoaded().subscribe();

      const req = httpMock.expectOne(`${environment.apiBaseUrl}/characters`);
      req.flush({ characters: [], unreadable: [] });

      // Should return from cache now
      service.ensureLoaded().subscribe();
      httpMock.expectNone(`${environment.apiBaseUrl}/characters`);
    });
  });

  describe('toggleEdition', () => {
    it('should switch editions and automatically update active character', () => {
      service.characters.set([mockChar2014, mockChar2024]);
      service.activeCharacter.set(mockChar2014);
      service.dndEdition.set('2014 Edition');

      service.toggleEdition();
      expect(service.dndEdition()).toBe('2024 Revision (5.5e)');
      expect(service.activeCharacter()).toEqual(mockChar2024);

      service.toggleEdition();
      expect(service.dndEdition()).toBe('2014 Edition');
      expect(service.activeCharacter()).toEqual(mockChar2014);
    });
  });

  describe('selectCharacter', () => {
    it('should select character if edition matches', () => {
      service.characters.set([mockChar2014]);
      service.dndEdition.set('2014 Edition');

      const success = service.selectCharacter('c1');
      expect(success).toBe(true);
      expect(service.activeCharacter()).toEqual(mockChar2014);
    });

    it('should not select character if edition mismatch', () => {
      service.characters.set([mockChar2024]);
      service.dndEdition.set('2014 Edition');

      const success = service.selectCharacter('c2');
      expect(success).toBe(false);
      expect(service.activeCharacter()).toBeNull();
    });
  });

  describe('CRUD operations', () => {
    it('should save a new character', () => {
      service.saveCharacter(mockChar2014).subscribe();
      const req = httpMock.expectOne(`${environment.apiBaseUrl}/characters`);
      expect(req.request.method).toBe('POST');
      req.flush(mockChar2014);

      expect(service.activeCharacter()).toEqual(mockChar2014);
      expect(service.characters()).toContainEqual(mockChar2014);
    });

    it('should update an existing character', () => {
      service.updateCharacter('c1', mockChar2014).subscribe();
      const req = httpMock.expectOne(`${environment.apiBaseUrl}/characters/c1`);
      expect(req.request.method).toBe('PUT');
      req.flush(mockChar2014);

      expect(service.activeCharacter()).toEqual(mockChar2014);
    });

    it('should delete a character and select next available', () => {
      service.characters.set([mockChar2014, { ...mockChar2014, char_id: 'c3' }]);
      service.activeCharacter.set(mockChar2014);
      service.dndEdition.set('2014 Edition');

      service.deleteCharacter('c1').subscribe();
      const req = httpMock.expectOne(`${environment.apiBaseUrl}/characters/c1`);
      expect(req.request.method).toBe('DELETE');
      req.flush({});

      expect(service.characters().length).toBe(1);
      expect(service.activeCharacter()?.char_id).toBe('c3');
    });

    it('should add homebrew to a character', () => {
      service.addHomebrewToCharacter('c1', 'h1').subscribe();
      const req = httpMock.expectOne(`${environment.apiBaseUrl}/characters/c1/homebrew/h1`);
      expect(req.request.method).toBe('POST');
      req.flush(mockChar2014);
      expect(service.activeCharacter()).toEqual(mockChar2014);
    });
  });

  describe('Computed Properties', () => {
    it('should compute abilityModifiers correctly', () => {
      service.activeCharacter.set(mockChar2014);
      // STR 10 -> 0, DEX 12 -> 1, CON 14 -> 2, INT 16 -> 3, WIS 8 -> -1, CHA 10 -> 0
      const mods = service.abilityModifiers();
      expect(mods.STR).toBe(0);
      expect(mods.DEX).toBe(1);
      expect(mods.CON).toBe(2);
      expect(mods.INT).toBe(3);
      expect(mods.WIS).toBe(-1);
      expect(mods.CHA).toBe(0);
    });

    it('should compute passivePerception correctly', () => {
      service.activeCharacter.set(mockChar2014);
      expect(service.passivePerception()).toBe(12);

      service.activeCharacter.set(null);
      expect(service.passivePerception()).toBe(10);
    });
  });
});
