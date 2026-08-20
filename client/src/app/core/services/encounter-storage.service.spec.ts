import { TestBed } from '@angular/core/testing';
import { EncounterStorageService } from './encounter-storage.service';
import { EncounterState, InitiativeCombatant } from '../models/initiative.model';

const CAMPAIGN = 'Curse of Strahd';
const KEY = `dnd.encounter.v1.${CAMPAIGN}`;

function combatant(overrides: Partial<InitiativeCombatant> = {}): InitiativeCombatant {
  return {
    id: 'abc1234',
    name: 'Goblin Warlord',
    initiative: 17,
    hp: 12,
    max_hp: 20,
    ac: 15,
    dex: 14,
    is_player: false,
    conditions: [],
    ...overrides,
  };
}

function state(overrides: Partial<EncounterState> = {}): EncounterState {
  return {
    round: 3,
    activeCombatantId: 'abc1234',
    combatants: [combatant()],
    ...overrides,
  };
}

describe('EncounterStorageService', () => {
  let service: EncounterStorageService;

  beforeEach(() => {
    TestBed.configureTestingModule({});
    service = TestBed.inject(EncounterStorageService);
    localStorage.clear();
  });

  afterEach(() => {
    jest.restoreAllMocks();
    localStorage.clear();
  });

  it('returns null when the campaign has no saved encounter', () => {
    expect(service.load(CAMPAIGN)).toBeNull();
  });

  it('round-trips an encounter, conditions and death saves included', () => {
    const saved = state({
      combatants: [
        combatant({
          conditions: [
            { name: 'Poisoned', expiresAtRound: 5 },
            { name: 'Concentrating', expiresAtRound: null },
          ],
        }),
        combatant({
          id: 'hero999',
          name: 'Valeros',
          is_player: true,
          hp: 0,
          deathSaves: { successes: 2, failures: 1 },
        }),
      ],
    });

    service.save(CAMPAIGN, saved);

    expect(service.load(CAMPAIGN)).toEqual(saved);
  });

  it('keeps every campaign encounter to itself', () => {
    service.save(CAMPAIGN, state({ round: 4 }));
    service.save('Phyrexia Awakens', state({ round: 9 }));

    expect(service.load(CAMPAIGN)?.round).toBe(4);
    expect(service.load('Phyrexia Awakens')?.round).toBe(9);
  });

  it('clears only the campaign it was asked to clear', () => {
    service.save(CAMPAIGN, state());
    service.save('Phyrexia Awakens', state());

    service.clear(CAMPAIGN);

    expect(service.load(CAMPAIGN)).toBeNull();
    expect(service.load('Phyrexia Awakens')).not.toBeNull();
  });

  it('discards an entry that is not JSON at all', () => {
    localStorage.setItem(KEY, 'not json {');

    expect(service.load(CAMPAIGN)).toBeNull();
  });

  it('discards an entry written by another version', () => {
    localStorage.setItem(KEY, JSON.stringify({ v: 99, state: state() }));

    expect(service.load(CAMPAIGN)).toBeNull();
  });

  const brokenCombatants: [string, Record<string, unknown>][] = [
    ['a combatant missing its hit points', { hp: undefined }],
    ['a combatant with a non-numeric initiative', { initiative: 'fast' }],
    ['a combatant with no id', { id: '' }],
    ['a combatant whose conditions are not a list', { conditions: 'Poisoned' }],
    ['a combatant with a broken death-save tally', { deathSaves: { successes: 'two' } }],
  ];

  it.each(brokenCombatants)('discards the whole entry on %s', (_label, broken) => {
    localStorage.setItem(
      KEY,
      JSON.stringify({ v: 1, state: { ...state(), combatants: [{ ...combatant(), ...broken }] } })
    );

    expect(service.load(CAMPAIGN)).toBeNull();
  });

  it('drops a turn pointer aimed at a combatant who is no longer there', () => {
    localStorage.setItem(
      KEY,
      JSON.stringify({ v: 1, state: { ...state(), activeCombatantId: 'departed' } })
    );

    const loaded = service.load(CAMPAIGN);

    expect(loaded).not.toBeNull();
    expect(loaded?.activeCombatantId).toBeNull();
  });

  it('treats a missing conditions array as no conditions, not as corruption', () => {
    const legacy = { ...combatant() } as Partial<InitiativeCombatant>;
    delete legacy.conditions;
    localStorage.setItem(KEY, JSON.stringify({ v: 1, state: { ...state(), combatants: [legacy] } }));

    expect(service.load(CAMPAIGN)?.combatants[0].conditions).toEqual([]);
  });

  it('survives a storage that refuses to write', () => {
    jest.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new DOMException('QuotaExceededError');
    });

    expect(() => service.save(CAMPAIGN, state())).not.toThrow();
  });

  it('survives a storage that refuses to read', () => {
    jest.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
      throw new DOMException('SecurityError');
    });

    expect(service.load(CAMPAIGN)).toBeNull();
  });

  it('ignores a call with no campaign name', () => {
    service.save('', state());

    expect(service.load('')).toBeNull();
    expect(localStorage.length).toBe(0);
  });
});
