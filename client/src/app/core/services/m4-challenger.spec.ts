import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting } from '@angular/common/http/testing';
import { Subject } from 'rxjs';
import { DmComponent } from '../../features/dm/dm.component';
import { EncounterStorageService } from './encounter-storage.service';
import { WebSocketService, WsMessage } from './websocket.service';
import { BestiaryMonster } from '../models/bestiary.model';
import { EncounterState, InitiativeCombatant } from '../models/initiative.model';

describe('Milestone 4 Challenger Adversarial Harness', () => {
  let dm: DmComponent;
  let storage: EncounterStorageService;
  const CAMPAIGN = 'ChallengerCampaign';

  beforeEach(() => {
    localStorage.clear();
    const wsStub: Partial<WebSocketService> = {
      messages$: new Subject<WsMessage>(),
      connectionState$: new Subject<string>(),
      connect: () => undefined,
      disconnect: () => undefined,
      sendVttToggle: jest.fn(),
    };

    TestBed.configureTestingModule({
      imports: [DmComponent],
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        { provide: WebSocketService, useValue: wsStub },
      ],
    });

    const fixture = TestBed.createComponent(DmComponent);
    dm = fixture.componentInstance;
    dm.campaignName = CAMPAIGN;
    storage = TestBed.inject(EncounterStorageService);
  });

  afterEach(() => {
    localStorage.clear();
    jest.restoreAllMocks();
  });

  // =========================================================================
  // FOCUS 1: Stress-test Monster Name Deduplication / Auto-Numbering Logic
  // =========================================================================
  describe('Focus 1: Deduplication & Auto-Numbering Stress Tests', () => {
    it('1.1 Standard unnumbered monster progression: Goblin -> Goblin 2 -> Goblin 3 -> Goblin 4', () => {
      const monster: BestiaryMonster = { id: 'm1', name: 'Goblin', edition: '2024', type: 'humanoid' };
      dm.addMonsterToInitiative(monster);
      dm.addMonsterToInitiative(monster);
      dm.addMonsterToInitiative(monster);
      dm.addMonsterToInitiative(monster);

      const names = dm.combatants.map((c) => c.name);
      expect(names).toEqual(expect.arrayContaining(['Goblin', 'Goblin 2', 'Goblin 3', 'Goblin 4']));
      expect(names.length).toBe(4);
    });

    it('1.2 Monster starting with numbered suffix: Skeleton 1 -> Skeleton 2 -> Skeleton 3', () => {
      const monster: BestiaryMonster = { id: 'm2', name: 'Skeleton 1', edition: '2024', type: 'undead' };
      dm.addMonsterToInitiative(monster);
      dm.addMonsterToInitiative(monster);
      dm.addMonsterToInitiative(monster);

      const names = dm.combatants.map((c) => c.name);
      expect(names).toEqual(expect.arrayContaining(['Skeleton 1', 'Skeleton 2', 'Skeleton 3']));
      expect(names.length).toBe(3);
    });

    it('1.3 Case insensitivity deduplication: "goblin" then "Goblin" then "GOBLIN"', () => {
      dm.addMonsterToInitiative({ id: 'm3a', name: 'goblin', edition: '2024', type: 'humanoid' });
      dm.addMonsterToInitiative({ id: 'm3b', name: 'Goblin', edition: '2024', type: 'humanoid' });
      dm.addMonsterToInitiative({ id: 'm3c', name: 'GOBLIN', edition: '2024', type: 'humanoid' });

      const names = dm.combatants.map((c) => c.name);
      expect(names).toHaveLength(3);
      expect(names[0].toLowerCase()).toBe('goblin');
      // The subsequent ones should be numbered 2 and 3
      expect(names.filter((n) => /goblin\s+2/i.test(n))).toHaveLength(1);
      expect(names.filter((n) => /goblin\s+3/i.test(n))).toHaveLength(1);
    });

    it('1.4 Special characters in monster name: regex escape safety', () => {
      const specialMonsters = [
        { id: 's1', name: 'Will-o\'-Wisp', edition: '2024', type: 'undead' },
        { id: 's2', name: 'Adult Red Dragon (Flying)', edition: '2024', type: 'dragon' },
        { id: 's3', name: 'Mind Flayer [Elite]', edition: '2024', type: 'aberration' },
        { id: 's4', name: 'Creature *Special* + Bonus', edition: '2024', type: 'monstrosity' },
      ];

      for (const m of specialMonsters) {
        expect(() => {
          dm.addMonsterToInitiative(m);
          dm.addMonsterToInitiative(m);
        }).not.toThrow();
      }

      const names = dm.combatants.map((c) => c.name);
      expect(names).toContain('Will-o\'-Wisp');
      expect(names).toContain('Will-o\'-Wisp 2');
      expect(names).toContain('Adult Red Dragon (Flying)');
      expect(names).toContain('Adult Red Dragon (Flying) 2');
      expect(names).toContain('Mind Flayer [Elite]');
      expect(names).toContain('Mind Flayer [Elite] 2');
      expect(names).toContain('Creature *Special* + Bonus');
      expect(names).toContain('Creature *Special* + Bonus 2');
    });

    it('1.5 Existing gaps in numbers: if Goblin 1 and Goblin 5 exist in combatants, next is Goblin 6', () => {
      // Seed combatants with existing gap (e.g. Goblin 2, 3, 4 were defeated and removed)
      dm.combatants = [
        {
          id: 'g1',
          name: 'Goblin 1',
          initiative: 12,
          hp: 7,
          max_hp: 7,
          ac: 15,
          dex: 14,
          is_player: false,
          conditions: [],
        },
        {
          id: 'g5',
          name: 'Goblin 5',
          initiative: 12,
          hp: 7,
          max_hp: 7,
          ac: 15,
          dex: 14,
          is_player: false,
          conditions: [],
        },
      ];

      // Add a new Goblin
      dm.addMonsterToInitiative({ id: 'g_next', name: 'Goblin', edition: '2024', type: 'humanoid' });

      const names = dm.combatants.map((c) => c.name);
      expect(names).toContain('Goblin 1');
      expect(names).toContain('Goblin 5');
      // Takes max existing number (5) + 1 = 6, avoiding collision with Goblin 5
      expect(names).toContain('Goblin 6');
    });

    it('1.6 Substring protection: "Goblin Archer" must NOT collide with "Goblin"', () => {
      dm.addMonsterToInitiative({ id: 'g', name: 'Goblin', edition: '2024', type: 'humanoid' });
      dm.addMonsterToInitiative({ id: 'ga', name: 'Goblin Archer', edition: '2024', type: 'humanoid' });

      const names = dm.combatants.map((c) => c.name);
      expect(names).toContain('Goblin');
      expect(names).toContain('Goblin Archer');
      expect(names).not.toContain('Goblin Archer 2');
      expect(names).not.toContain('Goblin 2');
    });

    it('1.7 Fallback for empty or whitespace-only monster names (demonstrating whitespace name bug)', () => {
      // Empty string falls back to 'Unknown Monster'
      dm.addMonsterToInitiative({ id: 'blank1', name: '', edition: '2024', type: 'unknown' });
      expect(dm.combatants.map((c) => c.name)).toContain('Unknown Monster');

      // Whitespace-only string '   ':
      // Because `(monster.name || 'Unknown Monster').trim()` evaluates ('   ' || ...) to '   ',
      // which trims to '', this produces an empty name combatant rather than 'Unknown Monster 2'.
      dm.addMonsterToInitiative({ id: 'blank2', name: '   ', edition: '2024', type: 'unknown' });
      const addedWhitespaceCombatant = dm.combatants.find((c) => c.id !== dm.combatants[0].id);
      expect(addedWhitespaceCombatant?.name).toBe('');
    });

    it('1.8 Consequence of whitespace name bug: corrupts localStorage reload', () => {
      // Adding a monster with whitespace name produces a combatant with name: ""
      dm.addMonsterToInitiative({ id: 'blank_bug', name: '   ', edition: '2024', type: 'unknown' });
      // Saving happens automatically via persistEncounter()
      // Now when EncounterStorageService attempts to load:
      const loaded = storage.load(CAMPAIGN);
      // Because parseCombatant requires typeof name === 'string' && name !== '',
      // the entire encounter fails validation and returns null!
      expect(loaded).toBeNull();
    });
  });

  // =========================================================================
  // FOCUS 2: Stress-test DEX Modifier Initiative Calculation
  // =========================================================================
  describe('Focus 2: DEX Modifier Initiative Calculation Stress Tests', () => {
    it('2.1 Negative DEX: Zombie (DEX 6 -> mod -2 -> init 8)', () => {
      dm.addMonsterToInitiative({
        id: 'zomb',
        name: 'Zombie',
        edition: '2024',
        type: 'undead',
        stats: { str: 13, dex: 6, con: 16, int: 3, wis: 6, cha: 5 },
      });

      const zombie = dm.combatants.find((c) => c.name === 'Zombie');
      expect(zombie?.dex).toBe(6);
      expect(zombie?.initiative).toBe(8);
    });

    it('2.2 High DEX: DEX 18 -> mod +4 -> init 14', () => {
      dm.addMonsterToInitiative({
        id: 'elf',
        name: 'Elf Scout',
        edition: '2024',
        type: 'humanoid',
        stats: { str: 10, dex: 18, con: 12, int: 11, wis: 13, cha: 11 },
      });

      const elf = dm.combatants.find((c) => c.name === 'Elf Scout');
      expect(elf?.dex).toBe(18);
      expect(elf?.initiative).toBe(14);
    });

    it('2.3 Neutral DEX: DEX 10 -> mod 0 -> init 10', () => {
      dm.addMonsterToInitiative({
        id: 'guard',
        name: 'Town Guard',
        edition: '2024',
        type: 'humanoid',
        stats: { str: 12, dex: 10, con: 12, int: 10, wis: 10, cha: 10 },
      });

      const guard = dm.combatants.find((c) => c.name === 'Town Guard');
      expect(guard?.dex).toBe(10);
      expect(guard?.initiative).toBe(10);
    });

    it('2.4 Edge values: DEX 1 (-5 -> init 5), DEX 7 (-2 -> init 8), DEX 9 (-1 -> init 9), DEX 11 (0 -> init 10), DEX 30 (+10 -> init 20)', () => {
      const cases = [
        { dex: 1, expectedInit: 5 },
        { dex: 7, expectedInit: 8 },
        { dex: 8, expectedInit: 9 },
        { dex: 9, expectedInit: 9 },
        { dex: 11, expectedInit: 10 },
        { dex: 12, expectedInit: 11 },
        { dex: 13, expectedInit: 11 },
        { dex: 30, expectedInit: 20 },
      ];

      for (const tc of cases) {
        dm.combatants = [];
        dm.addMonsterToInitiative({
          id: `monster_${tc.dex}`,
          name: `Creature DEX ${tc.dex}`,
          edition: '2024',
          type: 'monstrosity',
          stats: { str: 10, dex: tc.dex, con: 10, int: 10, wis: 10, cha: 10 },
        });

        const created = dm.combatants[0];
        expect(created.initiative).toBe(tc.expectedInit);
      }
    });

    it('2.5 Missing or corrupted stats fallback safely to DEX 10 (init 10)', () => {
      const corruptCases: any[] = [
        { stats: undefined },
        { stats: null },
        { stats: { dex: undefined } },
        { stats: { dex: null } },
        { stats: { dex: NaN } },
        { stats: { dex: Infinity } },
        { stats: { dex: 'not a number' } },
      ];

      for (let i = 0; i < corruptCases.length; i++) {
        dm.combatants = [];
        dm.addMonsterToInitiative({
          id: `corrupt_${i}`,
          name: `Corrupt ${i}`,
          edition: '2024',
          type: 'monstrosity',
          ...corruptCases[i],
        });

        expect(dm.combatants.length).toBe(1);
        expect(dm.combatants[0].dex).toBe(10);
        expect(dm.combatants[0].initiative).toBe(10);
      }
    });

    it('2.6 Fractional DEX: DEX 15.5 -> floor((15.5-10)/2) = floor(2.75) = 2 -> init 12', () => {
      dm.addMonsterToInitiative({
        id: 'fract',
        name: 'Fractional Dex Monster',
        edition: '2024',
        type: 'monstrosity',
        stats: { str: 10, dex: 15.5, con: 10, int: 10, wis: 10, cha: 10 },
      });

      expect(dm.combatants[0].dex).toBe(15.5);
      expect(dm.combatants[0].initiative).toBe(12);
    });
  });

  // =========================================================================
  // FOCUS 3: Stress-test Mid-Round Monster Addition
  // =========================================================================
  describe('Focus 3: Mid-Round Monster Addition Stress Tests', () => {
    it('3.1 Adding a monster during round 3 preserves round counter at 3', () => {
      dm.combatants = [
        {
          id: 'hero1',
          name: 'Hero 1',
          initiative: 20,
          hp: 25,
          max_hp: 25,
          ac: 16,
          dex: 14,
          is_player: true,
          conditions: [],
        },
        {
          id: 'hero2',
          name: 'Hero 2',
          initiative: 15,
          hp: 20,
          max_hp: 20,
          ac: 14,
          dex: 10,
          is_player: true,
          conditions: [],
        },
      ];
      dm.round = 3;
      dm.activeCombatantId = 'hero1';

      // Add reinforcement monster
      dm.addMonsterToInitiative({
        id: 'orc1',
        name: 'Orc',
        edition: '2024',
        type: 'humanoid',
        stats: { str: 16, dex: 12, con: 16, int: 7, wis: 11, cha: 10 },
      });

      expect(dm.round).toBe(3);
      expect(dm.combatants.length).toBe(3);
      // Active combatant remains pointing to hero1
      expect(dm.activeCombatantId).toBe('hero1');
    });

    it('3.2 Turn advancement continues normally after mid-round monster insertion', () => {
      dm.combatants = [
        {
          id: 'c1',
          name: 'First',
          initiative: 20,
          hp: 20,
          max_hp: 20,
          ac: 10,
          dex: 10,
          is_player: false,
          conditions: [],
        },
        {
          id: 'c2',
          name: 'Last',
          initiative: 10,
          hp: 20,
          max_hp: 20,
          ac: 10,
          dex: 10,
          is_player: false,
          conditions: [],
        },
      ];
      dm.round = 3;
      dm.activeCombatantId = 'c1';

      // Add middle monster with init 15
      dm.addMonsterToInitiative({
        id: 'c_mid',
        name: 'Middle',
        edition: '2024',
        type: 'humanoid',
        stats: { str: 10, dex: 20, con: 10, int: 10, wis: 10, cha: 10 }, // init = 10 + 5 = 15
      });

      expect(dm.round).toBe(3);
      expect(dm.activeCombatantId).toBe('c1');

      // Next turn advances from First -> Middle (still round 3)
      dm.nextTurn();
      expect(dm.round).toBe(3);
      expect(dm.activeCombatantId).not.toBe('c1');
      expect(dm.combatants.find((c) => c.id === dm.activeCombatantId)?.name).toBe('Middle');

      // Next turn advances from Middle -> Last (still round 3)
      dm.nextTurn();
      expect(dm.round).toBe(3);
      expect(dm.combatants.find((c) => c.id === dm.activeCombatantId)?.name).toBe('Last');

      // Next turn wraps from Last -> First (advances to round 4!)
      dm.nextTurn();
      expect(dm.round).toBe(4);
      expect(dm.combatants.find((c) => c.id === dm.activeCombatantId)?.name).toBe('First');
    });
  });

  // =========================================================================
  // FOCUS 4: Stress-test EncounterStorageService
  // =========================================================================
  describe('Focus 4: EncounterStorageService Persistence & Compatibility', () => {
    it('4.1 Full structured data preservation: actions, traits, stats, cr, size, xp', () => {
      const fullCombatant: InitiativeCombatant = {
        id: 'complex_monster',
        name: 'Ancient Red Dragon',
        initiative: 15,
        hp: 546,
        max_hp: 546,
        ac: 22,
        dex: 10,
        is_player: false,
        conditions: [{ name: 'Frightful Presence', expiresAtRound: null }],
        cr: '24',
        size: 'Gargantuan',
        xp: 62000,
        stats: { str: 30, dex: 10, con: 29, int: 18, wis: 15, cha: 23 },
        traits: [
          { name: 'Legendary Resistance (3/Day)', description: 'If the dragon fails a saving throw, it can choose to succeed instead.' },
        ],
        actions: [
          {
            name: 'Multiattack',
            description: 'The dragon can use its Frightful Presence. It then makes three attacks: one with its bite and two with its claws.',
          },
          {
            name: 'Bite',
            attack_bonus: 17,
            damage_dice: '2d10+10',
            damage_type: 'piercing',
            description: 'Plus 4d6 fire damage.',
          },
          {
            name: 'Tail Attack',
            attack_bonus: 0, // Explicit 0 bonus
            damage_dice: '2d8+10',
            damage_type: 'bludgeoning',
          },
          {
            name: 'Negative Bonus Strike',
            attack_bonus: -1, // Negative attack bonus
            damage_dice: '1d4',
          },
        ],
      };

      const encounter: EncounterState = {
        round: 5,
        activeCombatantId: 'complex_monster',
        combatants: [fullCombatant],
      };

      storage.save(CAMPAIGN, encounter);
      const reloaded = storage.load(CAMPAIGN);

      expect(reloaded).not.toBeNull();
      expect(reloaded?.round).toBe(5);
      expect(reloaded?.activeCombatantId).toBe('complex_monster');

      const c = reloaded!.combatants[0];
      expect(c.name).toBe('Ancient Red Dragon');
      expect(c.cr).toBe('24');
      expect(c.size).toBe('Gargantuan');
      expect(c.xp).toBe(62000);
      expect(c.stats).toEqual({ str: 30, dex: 10, con: 29, int: 18, wis: 15, cha: 23 });
      expect(c.traits).toEqual([
        { name: 'Legendary Resistance (3/Day)', description: 'If the dragon fails a saving throw, it can choose to succeed instead.' },
      ]);
      expect(c.actions).toHaveLength(4);
      expect(c.actions![0].name).toBe('Multiattack');
      expect(c.actions![1].attack_bonus).toBe(17);
      expect(c.actions![1].damage_dice).toBe('2d10+10');
      expect(c.actions![2].attack_bonus).toBe(0);
      expect(c.actions![3].attack_bonus).toBe(-1);
    });

    it('4.2 Legacy combatant deserialization (without stats, traits, actions) loads cleanly without errors', () => {
      const legacyPayload = {
        v: 1,
        state: {
          round: 2,
          activeCombatantId: 'leg_1',
          combatants: [
            {
              id: 'leg_1',
              name: 'Old Player Character',
              initiative: 14,
              hp: 28,
              max_hp: 28,
              ac: 15,
              dex: 12,
              is_player: true,
              conditions: [],
            },
            {
              id: 'leg_2',
              name: 'Old Monster',
              initiative: 11,
              hp: 15,
              max_hp: 15,
              ac: 12,
              dex: 10,
              is_player: false,
              conditions: [{ name: 'Blinded', expiresAtRound: 4 }],
            },
          ],
        },
      };

      localStorage.setItem(`dnd.encounter.v1.${CAMPAIGN}`, JSON.stringify(legacyPayload));

      const reloaded = storage.load(CAMPAIGN);
      expect(reloaded).not.toBeNull();
      expect(reloaded?.round).toBe(2);
      expect(reloaded?.combatants).toHaveLength(2);
      expect(reloaded?.combatants[0].name).toBe('Old Player Character');
      expect(reloaded?.combatants[0].stats).toBeUndefined();
      expect(reloaded?.combatants[0].traits).toBeUndefined();
      expect(reloaded?.combatants[0].actions).toBeUndefined();
      expect(reloaded?.combatants[1].conditions).toEqual([{ name: 'Blinded', expiresAtRound: 4 }]);
    });

    it('4.3 Invalid or partially corrupt actions / traits / stats discard entire corrupted encounter cleanly', () => {
      const corruptPayloads = [
        // Non-object trait
        { traits: ['not an object'] },
        // Trait without name
        { traits: [{ description: 'No name' }] },
        // Non-object action
        { actions: ['not an object'] },
        // Action without name
        { actions: [{ damage_dice: '1d6' }] },
        // Corrupt stats (string inside stats)
        { stats: { str: 10, dex: 'fast', con: 10, int: 10, wis: 10, cha: 10 } },
        // Incomplete stats (missing wis)
        { stats: { str: 10, dex: 10, con: 10, int: 10, cha: 10 } },
      ];

      for (const badProp of corruptPayloads) {
        const payload = {
          v: 1,
          state: {
            round: 1,
            activeCombatantId: 'bad_c',
            combatants: [
              {
                id: 'bad_c',
                name: 'Bad Combatant',
                initiative: 10,
                hp: 10,
                max_hp: 10,
                ac: 10,
                dex: 10,
                is_player: false,
                conditions: [],
                ...badProp,
              },
            ],
          },
        };

        localStorage.setItem(`dnd.encounter.v1.${CAMPAIGN}`, JSON.stringify(payload));
        expect(storage.load(CAMPAIGN)).toBeNull();
      }
    });

    it('4.4 Preserves fractional and string CR ("1/8", "1/4", "1/2", "0") and numeric CR (5)', () => {
      const crList = ['1/8', '1/4', '1/2', '0', 5];

      for (let i = 0; i < crList.length; i++) {
        const crVal = crList[i];
        const encounter: EncounterState = {
          round: 1,
          activeCombatantId: `cr_${i}`,
          combatants: [
            {
              id: `cr_${i}`,
              name: `CR Creature ${crVal}`,
              initiative: 10,
              hp: 10,
              max_hp: 10,
              ac: 10,
              dex: 10,
              is_player: false,
              conditions: [],
              cr: crVal,
            },
          ],
        };

        storage.save(CAMPAIGN, encounter);
        const reloaded = storage.load(CAMPAIGN);
        expect(reloaded?.combatants[0].cr).toBe(crVal);
      }
    });
  });
});
