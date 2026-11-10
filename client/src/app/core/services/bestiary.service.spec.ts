import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { BestiaryService } from './bestiary.service';
import { BestiaryMonster, BestiaryCreateRequest, BestiaryUpdateRequest } from '../models/bestiary.model';
import { environment } from '../../../environments/environment';

describe('BestiaryService', () => {
  let service: BestiaryService;
  let httpMock: HttpTestingController;

  const mockMonster: BestiaryMonster = {
    id: 'srd_goblin_2014',
    name: 'Goblin',
    edition: '2014',
    origin: 'official',
    is_public: true,
    size: 'Small',
    type: 'humanoid',
    alignment: 'neutral evil',
    cr: '1/4',
    cr_numeric: 0.25,
    ac: 15,
    hp: 7,
    max_hp: 7,
    speed: '30 ft.',
    stats: { str: 8, dex: 14, con: 10, int: 10, wis: 8, cha: 8 },
    traits: [{ name: 'Nimble Escape', description: 'Can Disengage or Hide as bonus action.' }],
    actions: [{ name: 'Scimitar', attack_bonus: 4, damage_dice: '1d6+2', damage_type: 'slashing', description: 'Melee attack' }],
  };

  const mockMonster2: BestiaryMonster = {
    id: 'srd_dragon_2014',
    name: 'Adult Red Dragon',
    edition: '2014',
    origin: 'official',
    is_public: true,
    size: 'Huge',
    type: 'dragon',
    alignment: 'chaotic evil',
    cr: '17',
    cr_numeric: 17,
    ac: 19,
    hp: 256,
    max_hp: 256,
    speed: '40 ft., fly 80 ft.',
    stats: { str: 27, dex: 10, con: 25, int: 16, wis: 13, cha: 21 },
    traits: [{ name: 'Legendary Resistance', description: 'Can choose to succeed save.' }],
    actions: [{ name: 'Bite', attack_bonus: 14, damage_dice: '2d10+8', damage_type: 'piercing', description: 'Melee attack' }],
  };

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [
        BestiaryService,
        provideHttpClient(),
        provideHttpClientTesting(),
      ],
    });

    service = TestBed.inject(BestiaryService);
    httpMock = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    httpMock.verify();
  });

  it('should be created and have initial signal values', () => {
    expect(service).toBeTruthy();
    expect(service.monsters()).toEqual([]);
    expect(service.isLoading()).toBe(false);
    expect(service.error()).toBeNull();
    expect(service.selectedMonster()).toBeNull();
  });

  describe('getMonsters', () => {
    it('should query without parameters when empty filters provided', () => {
      service.getMonsters().subscribe((monsters) => {
        expect(monsters.length).toBe(1);
        expect(monsters[0].name).toBe('Goblin');
      });

      expect(service.isLoading()).toBe(true);

      const req = httpMock.expectOne(`${environment.apiBaseUrl}/bestiary`);
      expect(req.request.method).toBe('GET');
      expect(req.request.params.keys().length).toBe(0);

      req.flush([mockMonster]);

      expect(service.monsters()).toEqual([mockMonster]);
      expect(service.isLoading()).toBe(false);
      expect(service.error()).toBeNull();
    });

    it('should construct query params correctly and apply CR min/max filter', () => {
      service
        .getMonsters({
          edition: '2014',
          search: 'Goblin',
          cr: '1/4',
          monster_type: 'humanoid',
          include_official: true,
          include_mine: true,
          include_community: false,
          cr_min: 0,
          cr_max: 5,
        })
        .subscribe((monsters) => {
          expect(monsters.length).toBe(1);
          expect(monsters[0].id).toBe('srd_goblin_2014');
        });

      const req = httpMock.expectOne((request) => {
        return (
          request.url === `${environment.apiBaseUrl}/bestiary` &&
          request.params.get('edition') === '2014' &&
          request.params.get('search') === 'Goblin' &&
          request.params.get('cr') === '1/4' &&
          request.params.get('monster_type') === 'humanoid' &&
          request.params.get('include_official') === 'true' &&
          request.params.get('include_mine') === 'true' &&
          request.params.get('include_community') === 'false'
        );
      });
      expect(req.request.method).toBe('GET');

      req.flush([mockMonster, mockMonster2]); // mockMonster2 has cr_numeric 17, which should be filtered out by cr_max: 5
    });

    it('should handle errors and update error signal', () => {
      service.getMonsters().subscribe({
        next: () => fail('Should have failed'),
        error: (err) => {
          expect(err).toBeTruthy();
        },
      });

      const req = httpMock.expectOne(`${environment.apiBaseUrl}/bestiary`);
      req.flush({ detail: 'Database error' }, { status: 500, statusText: 'Server Error' });

      expect(service.isLoading()).toBe(false);
      expect(service.error()).toBe('Database error');
    });
  });

  describe('getMonsterById', () => {
    it('should fetch monster by ID and update selectedMonster signal', () => {
      service.getMonsterById('srd_goblin_2014').subscribe((monster) => {
        expect(monster.name).toBe('Goblin');
      });

      const req = httpMock.expectOne(`${environment.apiBaseUrl}/bestiary/srd_goblin_2014`);
      expect(req.request.method).toBe('GET');

      req.flush(mockMonster);
      expect(service.selectedMonster()).toEqual(mockMonster);
    });
  });

  describe('createMonster', () => {
    it('should POST new monster and prepend to monsters signal', () => {
      const payload: BestiaryCreateRequest = {
        name: 'Custom Orc',
        cr: '1',
        cr_numeric: 1,
        hp: 15,
        ac: 13,
      };

      const created: BestiaryMonster = {
        ...mockMonster,
        id: 'custom_orc_123',
        name: 'Custom Orc',
        origin: 'custom',
        cr: '1',
        cr_numeric: 1,
        hp: 15,
        ac: 13,
      };

      service.createMonster(payload).subscribe((res) => {
        expect(res.id).toBe('custom_orc_123');
      });

      const req = httpMock.expectOne(`${environment.apiBaseUrl}/bestiary`);
      expect(req.request.method).toBe('POST');
      expect(req.request.body).toEqual(payload);

      req.flush(created);
      expect(service.monsters()).toContain(created);
    });
  });

  describe('cloneMonster', () => {
    it('should fetch source monster and POST with based_on', () => {
      service.cloneMonster('srd_goblin_2014', { name: 'Goblin Chieftain' }).subscribe((cloned) => {
        expect(cloned.name).toBe('Goblin Chieftain');
        expect(cloned.based_on).toBe('srd_goblin_2014');
      });

      // 1. GET source monster
      const getReq = httpMock.expectOne(`${environment.apiBaseUrl}/bestiary/srd_goblin_2014`);
      expect(getReq.request.method).toBe('GET');
      getReq.flush(mockMonster);

      // 2. POST cloned monster
      const postReq = httpMock.expectOne(`${environment.apiBaseUrl}/bestiary`);
      expect(postReq.request.method).toBe('POST');
      expect(postReq.request.body.based_on).toBe('srd_goblin_2014');
      expect(postReq.request.body.name).toBe('Goblin Chieftain');

      const clonedResponse: BestiaryMonster = {
        ...mockMonster,
        id: 'custom_goblin_clone',
        name: 'Goblin Chieftain',
        origin: 'custom',
        based_on: 'srd_goblin_2014',
      };
      postReq.flush(clonedResponse);
    });
  });

  describe('updateMonster', () => {
    it('should PUT updated monster and update monsters signal', () => {
      service.monsters.set([mockMonster]);
      const updatePayload: BestiaryUpdateRequest = { hp: 10 };
      const updatedMonster: BestiaryMonster = { ...mockMonster, hp: 10 };

      service.updateMonster('srd_goblin_2014', updatePayload).subscribe((res) => {
        expect(res.hp).toBe(10);
      });

      const req = httpMock.expectOne(`${environment.apiBaseUrl}/bestiary/srd_goblin_2014`);
      expect(req.request.method).toBe('PUT');
      expect(req.request.body).toEqual(updatePayload);

      req.flush(updatedMonster);
      expect(service.monsters()[0].hp).toBe(10);
    });
  });

  describe('toggleVisibility', () => {
    it('should PATCH visibility and update is_public in signal list', () => {
      const customMonster: BestiaryMonster = { ...mockMonster, id: 'custom_m1', is_public: false };
      service.monsters.set([customMonster]);

      service.toggleVisibility('custom_m1', true).subscribe((res) => {
        expect(res.is_public).toBe(true);
      });

      const req = httpMock.expectOne(`${environment.apiBaseUrl}/bestiary/custom_m1/visibility`);
      expect(req.request.method).toBe('PATCH');
      expect(req.request.body).toEqual({ is_public: true });

      req.flush({ success: true, is_public: true });
      expect(service.monsters()[0].is_public).toBe(true);
    });
  });

  describe('deleteMonster', () => {
    it('should DELETE monster and remove from signal list', () => {
      service.monsters.set([mockMonster]);

      service.deleteMonster('srd_goblin_2014').subscribe((res) => {
        expect(res.success).toBe(true);
      });

      const req = httpMock.expectOne(`${environment.apiBaseUrl}/bestiary/srd_goblin_2014`);
      expect(req.request.method).toBe('DELETE');

      req.flush({ success: true, message: 'Deleted' });
      expect(service.monsters().length).toBe(0);
    });
  });
});
