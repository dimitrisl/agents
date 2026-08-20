import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { Subject } from 'rxjs';
import { DmComponent, PartyMember } from './dm.component';
import { RollToastService } from '../../core/services/roll-toast.service';
import { WebSocketService, WsMessage } from '../../core/services/websocket.service';
import { EncounterStorageService } from '../../core/services/encounter-storage.service';
import { InitiativeCombatant } from '../../core/models/initiative.model';
import { EncounterMonster } from '../../core/models/dm-tools.model';
import { CharacterStateService } from '../../core/services/character-state.service';

/**
 * The turn engine is exercised on the component instance directly — the fixture
 * is never change-detected, so `ngOnInit` and its campaign fetch stay out of the
 * way of what is under test here.
 */
function makeComponent(): DmComponent {
  return TestBed.createComponent(DmComponent).componentInstance;
}

function hero(name: string, level: number): PartyMember {
  return {
    char_id: name,
    name,
    char_class: 'Fighter',
    level,
    hp_current: 20,
    hp_max: 20,
    ac: 15,
    passive_perception: 10,
    conditions: [],
  };
}

function combatant(id: string, initiative: number, overrides: Partial<InitiativeCombatant> = {}) {
  return {
    id,
    name: id,
    initiative,
    hp: 10,
    max_hp: 10,
    ac: 12,
    dex: 10,
    is_player: false,
    conditions: [],
    ...overrides,
  } satisfies InitiativeCombatant;
}

describe('DmComponent — initiative rounds', () => {
  let component: DmComponent;
  let storage: EncounterStorageService;

  beforeEach(() => {
    // The socket is stubbed: this suite is about the round engine, and a real
    // connect would reach for a server that is not there.
    const wsStub: Partial<WebSocketService> = {
      messages$: new Subject<WsMessage>(),
      opened$: new Subject<string>(),
      connect: () => undefined,
    };

    TestBed.configureTestingModule({
      imports: [DmComponent],
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        { provide: WebSocketService, useValue: wsStub },
      ],
    });

    localStorage.clear();
    storage = TestBed.inject(EncounterStorageService);
    component = makeComponent();
    component.campaignName = 'Curse of Strahd';
    component.combatants = [
      combatant('first', 20),
      combatant('second', 15),
      combatant('third', 10),
    ];
  });

  afterEach(() => localStorage.clear());

  describe('nextTurn', () => {
    it('opens round 1 on the first advance', () => {
      expect(component.round).toBe(0);

      component.nextTurn();

      expect(component.round).toBe(1);
      expect(component.activeCombatantId).toBe('first');
    });

    it('holds the round while the order is still being walked', () => {
      component.nextTurn();
      component.nextTurn();
      component.nextTurn();

      expect(component.round).toBe(1);
      expect(component.activeCombatantId).toBe('third');
    });

    it('counts a new round only when the order wraps to the top', () => {
      // 7 advances over 3 combatants: first → third, wrap, wrap.
      for (let i = 0; i < 7; i++) component.nextTurn();

      expect(component.round).toBe(3);
      expect(component.activeCombatantId).toBe('first');
    });

    it('starts no round at all on an empty table', () => {
      component.combatants = [];

      component.nextTurn();

      expect(component.round).toBe(0);
      expect(component.activeCombatantId).toBeNull();
    });
  });

  describe('previousTurn', () => {
    it('is the exact inverse of advancing', () => {
      for (let i = 0; i < 5; i++) component.nextTurn();
      expect(component.round).toBe(2);
      expect(component.activeCombatantId).toBe('second');

      for (let i = 0; i < 4; i++) component.previousTurn();

      expect(component.round).toBe(1);
      expect(component.activeCombatantId).toBe('first');
    });

    it('walks the round counter back when it steps off the top of the order', () => {
      for (let i = 0; i < 4; i++) component.nextTurn();
      expect(component.round).toBe(2);

      component.previousTurn();

      expect(component.round).toBe(1);
      expect(component.activeCombatantId).toBe('third');
    });

    it('closes the encounter rather than reaching behind round 1', () => {
      component.nextTurn();

      component.previousTurn();

      expect(component.round).toBe(0);
      expect(component.activeCombatantId).toBeNull();
    });

    it('does nothing before combat has started', () => {
      component.previousTurn();

      expect(component.round).toBe(0);
      expect(component.activeCombatantId).toBeNull();
    });
  });

  describe('conditions', () => {
    it('anchors a duration to the round it lapses on', () => {
      component.nextTurn(); // round 1

      component.applyCombatantCondition(component.combatants[0], 'Poisoned', 2);

      expect(component.combatants[0].conditions).toEqual([
        { name: 'Poisoned', expiresAtRound: 3 },
      ]);
    });

    it('records an indefinite condition when no duration is given', () => {
      component.applyCombatantCondition(component.combatants[0], 'Concentrating', 0);

      expect(component.combatants[0].conditions[0].expiresAtRound).toBeNull();
    });

    it('re-applying a condition replaces its timer instead of stacking it', () => {
      component.nextTurn();
      component.applyCombatantCondition(component.combatants[0], 'Poisoned', 2);
      component.applyCombatantCondition(component.combatants[0], 'Poisoned', 5);

      expect(component.combatants[0].conditions).toEqual([
        { name: 'Poisoned', expiresAtRound: 6 },
      ]);
    });

    it('survives a round walked forwards and back, so a mis-click costs nothing', () => {
      component.nextTurn();
      component.applyCombatantCondition(component.combatants[0], 'Poisoned', 1);
      const applied = component.combatants[0].conditions[0];

      for (let i = 0; i < 3; i++) component.nextTurn();
      component.previousTurn();

      expect(component.round).toBe(1);
      expect(component.combatants[0].conditions).toEqual([applied]);
    });
  });

  describe('hit points and death saves', () => {
    beforeEach(() => {
      component.combatants = [combatant('hero', 18, { is_player: true, hp: 6, max_hp: 24 })];
    });

    it('clamps hit points to the combatant’s own range', () => {
      component.setCombatantHp(component.combatants[0], -12);
      expect(component.combatants[0].hp).toBe(0);

      component.setCombatantHp(component.combatants[0], 99);
      expect(component.combatants[0].hp).toBe(24);
    });

    it('clears the death-save tally the moment the hero is healed', () => {
      component.setCombatantHp(component.combatants[0], 0);
      component.setDeathSave(component.combatants[0], 'failures', 2);
      expect(component.combatants[0].deathSaves).toEqual({ successes: 0, failures: 2 });

      component.setCombatantHp(component.combatants[0], 4);

      expect(component.combatants[0].deathSaves).toBeUndefined();
    });

    it('takes back the last dot when it is clicked a second time', () => {
      component.setDeathSave(component.combatants[0], 'successes', 2);
      component.setDeathSave(component.combatants[0], 'successes', 2);

      expect(component.combatants[0].deathSaves?.successes).toBe(1);
    });
  });

  describe('persistence', () => {
    it('saves the encounter as the turn advances', () => {
      component.nextTurn();
      component.nextTurn();

      expect(storage.load('Curse of Strahd')).toEqual({
        round: 1,
        activeCombatantId: 'second',
        combatants: component.combatants,
      });
    });

    it('ending combat clears the table and the saved entry', () => {
      component.nextTurn();
      expect(storage.load('Curse of Strahd')).not.toBeNull();

      component.endCombat();

      expect(component.combatants).toEqual([]);
      expect(component.round).toBe(0);
      expect(component.activeCombatantId).toBeNull();
      expect(storage.load('Curse of Strahd')).toBeNull();
    });

    it('removing the last combatant closes the encounter', () => {
      component.combatants = [combatant('only', 12)];
      component.nextTurn();

      component.removeCombatant(0);

      expect(component.round).toBe(0);
      expect(storage.load('Curse of Strahd')).toBeNull();
    });

    /**
     * The regression this guards: the party fetch used to seed the tracker on
     * every campaign select, dropping all player combatants and voiding the
     * turn — which would erase a restored fight a moment after it reappeared.
     */
    it('the party fetch leaves a restored encounter alone', () => {
      const http = TestBed.inject(HttpTestingController);
      storage.save('Curse of Strahd', {
        round: 4,
        activeCombatantId: 'valeros',
        combatants: [
          combatant('valeros', 20, { is_player: true, hp: 3, max_hp: 30 }),
          combatant('goblin', 15),
        ],
      });

      const restored = makeComponent();
      restored.campaignName = 'Curse of Strahd';
      restored.onCampaignSelect();

      // The roster lands after the restore, carrying a hero the fight never had.
      http
        .expectOne((req) => req.url.includes('/party'))
        .flush([
          { char_id: 'v1', char_name: 'valeros', hp_current: 30, hp_max: 30, armor_class: 16 },
          { char_id: 'e1', char_name: 'Ezren', hp_current: 22, hp_max: 22, armor_class: 12 },
        ]);

      expect(restored.round).toBe(4);
      expect(restored.activeCombatantId).toBe('valeros');
      expect(restored.combatants.map((c) => c.id)).toEqual(['valeros', 'goblin']);
      // Damage taken in the restored fight is not overwritten by the roster's full HP.
      expect(restored.combatants[0].hp).toBe(3);
    });

    it('carries no combatant across a campaign switch', () => {
      const http = TestBed.inject(HttpTestingController);
      component.onCampaignSelect();
      http.expectOne((req) => req.url.includes('/party')).flush([]);

      // A monster added under the first campaign must not follow the DM to the
      // next one — nor end up saved under its name.
      component.newCombatantName = 'Strahd';
      component.addCombatant();

      component.campaignName = 'Phyrexia Awakens';
      component.onCampaignSelect();

      expect(component.combatants).toEqual([]);
      expect(component.round).toBe(0);

      http.expectOne((req) => req.url.includes('/party')).flush([]);
      expect(storage.load('Phyrexia Awakens')).toBeNull();
      expect(storage.load('Curse of Strahd')?.combatants.map((c) => c.name)).toEqual(['Strahd']);
    });

    it('seeds the tracker from the party when nothing was saved', () => {
      const http = TestBed.inject(HttpTestingController);

      const fresh = makeComponent();
      fresh.campaignName = 'Phyrexia Awakens';
      fresh.onCampaignSelect();

      http
        .expectOne((req) => req.url.includes('/party'))
        .flush([{ char_id: 'e1', char_name: 'Ezren', hp_current: 22, hp_max: 22, armor_class: 12 }]);

      expect(fresh.combatants.map((c) => c.name)).toEqual(['Ezren']);
      expect(fresh.round).toBe(0);
      expect(fresh.activeCombatantId).toBeNull();
    });
  });

  describe('one hero, one state', () => {
    let http: HttpTestingController;
    let hero: PartyMember;

    beforeEach(() => {
      jest.useFakeTimers();
      http = TestBed.inject(HttpTestingController);
      component.onCampaignSelect();
      // The inbox fetch is not what these tests are about, but it has to be
      // answered for `verify()` to mean "no stray writes".
      http
        .expectOne((req) => req.url.includes('/messages'))
        .flush({ campaign_name: 'Curse of Strahd', whispers: [], roll_requests: [] });
      http.expectOne((req) => req.url.includes('/party')).flush([
        {
          char_id: 'lyra1',
          char_name: 'Lyra Meadowlark',
          hp_current: 17,
          hp_max: 17,
          armor_class: 13,
          conditions: ['Invisible'],
        },
      ]);
      hero = component.partyMembers[0];
    });

    afterEach(() => {
      jest.useRealTimers();
      http.verify();
    });

    /** The DM's writes are coalesced, so tests have to let the timer run. */
    function flushWrites(): void {
      jest.advanceTimersByTime(500);
    }

    it('reads the conditions the sheet already carried', () => {
      expect(hero.conditions).toEqual(['Invisible']);
      expect(component.combatants[0].conditions).toEqual([
        { name: 'Invisible', expiresAtRound: null },
      ]);
    });

    it('damage recorded in the tracker shows in the roster and reaches the sheet', () => {
      component.setCombatantHp(component.combatants[0], 4);

      expect(hero.hp_current).toBe(4);
      expect(component.combatants[0].hp).toBe(4);

      flushWrites();
      const req = http.expectOne((r) => r.method === 'PATCH');
      expect(req.request.body).toEqual({ hp_current: 4 });
      req.flush({ success: true });
    });

    it('damage recorded in the roster shows in the tracker', () => {
      component.adjustHp(hero, -5);

      expect(component.combatants[0].hp).toBe(12);

      flushWrites();
      http.expectOne((r) => r.method === 'PATCH').flush({ success: true });
    });

    it('coalesces a held hit-point button into one write', () => {
      for (let i = 0; i < 6; i++) component.adjustHp(hero, -1);

      expect(hero.hp_current).toBe(11);

      flushWrites();
      const req = http.expectOne((r) => r.method === 'PATCH');
      expect(req.request.body).toEqual({ hp_current: 11 });
      req.flush({ success: true });
    });

    it('a condition set in either tab lands in both, and on the sheet', () => {
      component.applyCombatantCondition(component.combatants[0], 'Poisoned', 2);

      expect(hero.conditions).toContain('Poisoned');

      flushWrites();
      const req = http.expectOne((r) => r.method === 'PATCH');
      expect(req.request.body).toEqual({ conditions: ['Invisible', 'Poisoned'] });
      req.flush({ success: true });

      component.toggleCondition(hero, 'Poisoned');
      expect(component.combatants[0].conditions.map((c) => c.name)).toEqual(['Invisible']);

      flushWrites();
      http.expectOne((r) => r.method === 'PATCH').flush({ success: true });
    });

    it('a condition that runs out is taken off the sheet too', () => {
      component.nextTurn();
      component.applyCombatantCondition(component.combatants[0], 'Poisoned', 1);
      flushWrites();
      http.expectOne((r) => r.method === 'PATCH').flush({ success: true });

      // Round 2 opens: the one-round condition is spent.
      component.nextTurn();
      expect(hero.conditions).toEqual(['Invisible']);

      flushWrites();
      const req = http.expectOne((r) => r.method === 'PATCH');
      expect(req.request.body).toEqual({ conditions: ['Invisible'] });
      req.flush({ success: true });
    });

    it('walking the round back puts a lapsed condition back on the sheet', () => {
      component.nextTurn();
      component.applyCombatantCondition(component.combatants[0], 'Poisoned', 1);
      flushWrites();
      http.expectOne((r) => r.method === 'PATCH').flush({ success: true });

      component.nextTurn();
      flushWrites();
      http.expectOne((r) => r.method === 'PATCH').flush({ success: true });
      expect(hero.conditions).toEqual(['Invisible']);

      component.previousTurn();

      expect(hero.conditions).toEqual(['Invisible', 'Poisoned']);
      flushWrites();
      http.expectOne((r) => r.method === 'PATCH').flush({ success: true });
    });

    it('says so out loud when the sheet refuses the write', () => {
      const toast = jest.spyOn(TestBed.inject(RollToastService), 'showMessage');

      component.adjustHp(hero, -3);
      flushWrites();
      http
        .expectOne((r) => r.method === 'PATCH')
        .flush({ detail: 'nope' }, { status: 500, statusText: 'Server Error' });

      expect(toast).toHaveBeenCalledWith('⚠️ NOT SAVED', expect.stringContaining('Lyra'));
    });

    it('writes nothing for a hero the DM invented by hand', () => {
      component.partyMembers = [
        { name: 'Nameless', char_class: 'Fighter', level: 1, hp_current: 8, hp_max: 8, ac: 12, passive_perception: 10, conditions: [] },
      ];

      component.adjustHp(component.partyMembers[0], -2);
      flushWrites();

      http.expectNone((r) => r.method === 'PATCH');
    });
  });
});

/**
 * The generator used to post `party_size: 4`, `difficulty: 'Medium'` and a level
 * that started at 5 and never moved — a party of six level-12 heroes was handed
 * a fight balanced for four level-5 ones.
 */
describe('DmComponent — encounter generator', () => {
  let component: DmComponent;
  let http: HttpTestingController;

  beforeEach(() => {
    const wsStub: Partial<WebSocketService> = {
      messages$: new Subject<WsMessage>(),
      opened$: new Subject<string>(),
      connect: () => undefined,
    };

    TestBed.configureTestingModule({
      imports: [DmComponent],
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        { provide: WebSocketService, useValue: wsStub },
      ],
    });

    localStorage.clear();
    http = TestBed.inject(HttpTestingController);
    component = makeComponent();
    component.campaignName = 'Curse of Strahd';
  });

  afterEach(() => {
    http.verify();
    localStorage.clear();
  });

  it('balances the request against the party actually at the table', () => {
    component.partyMembers = [hero('Ezren', 12), hero('Valeros', 12), hero('Merisiel', 11)];
    component.location = 'Sunken Cathedral';
    component.encounterDifficulty = 'Deadly';

    component.generateEncounter();

    const req = http.expectOne((r) => r.url.includes('/dm/encounter'));
    expect(req.request.body).toEqual({
      party_size: 3,
      avg_level: 12,
      location: 'Sunken Cathedral',
      edition: '2014 Edition',
      difficulty: 'Deadly',
    });
    req.flush({ encounter_text: 'Ghouls', monsters: [] });
  });

  it('lets the DM overrule the average level', () => {
    component.partyMembers = [hero('Ezren', 3), hero('Valeros', 3)];
    expect(component.avgLevel).toBe(3);

    component.avgLevel = 9;

    component.generateEncounter();

    const req = http.expectOne((r) => r.url.includes('/dm/encounter'));
    expect(req.request.body.avg_level).toBe(9);
    req.flush({ encounter_text: 'Wights', monsters: [] });
  });

  it('drops a level typed for the previous table when the campaign changes', () => {
    component.partyMembers = [hero('Ezren', 3)];
    component.avgLevel = 9;

    component.onCampaignSelect();
    http.expectOne((r) => r.url.includes('/messages')).flush({
      campaign_name: 'Curse of Strahd',
      whispers: [],
      roll_requests: [],
    });
    http
      .expectOne((r) => r.url.includes('/party'))
      .flush([{ char_id: 'e1', char_name: 'Ezren', char_level: 4, hp_current: 22, hp_max: 22 }]);

    expect(component.avgLevel).toBe(4);
  });

  it('says so instead of quietly asking for a fight for nobody', () => {
    const toast = jest.spyOn(TestBed.inject(RollToastService), 'showMessage');
    component.partyMembers = [];

    component.generateEncounter();

    http.expectNone((r) => r.url.includes('/dm/encounter'));
    expect(toast).toHaveBeenCalledWith('⚠️ NO PARTY', expect.stringContaining('roster'));
  });

  it('resolves the encounter against the ruleset the campaign is played under', () => {
    component.userCampaigns = [
      { campaign_name: 'Curse of Strahd', dnd_edition: '2024 Revision (5.5e)' },
    ];
    component.onCampaignSelect();
    http.expectOne((r) => r.url.includes('/messages')).flush({
      campaign_name: 'Curse of Strahd',
      whispers: [],
      roll_requests: [],
    });
    http.expectOne((r) => r.url.includes('/party')).flush([]);
    component.partyMembers = [hero('Ezren', 5)];

    component.generateEncounter();

    const encounter = http.expectOne((r) => r.url.includes('/dm/encounter'));
    expect(encounter.request.body.edition).toBe('2024 Revision (5.5e)');
    encounter.flush({ encounter_text: 'Ghouls', monsters: [] });

    component.generateNpc();

    const npc = http.expectOne((r) => r.url.includes('/dm/npc'));
    expect(npc.request.body.edition).toBe('2024 Revision (5.5e)');
    npc.flush({ npc_markdown: 'A broker' });

    expect(component.editionShort).toBe('2024');
  });

  it('falls back to the edition toggle for a campaign saved before the field existed', () => {
    TestBed.inject(CharacterStateService).dndEdition.set('2024 Revision (5.5e)');
    component.userCampaigns = [{ campaign_name: 'Curse of Strahd' }];
    component.onCampaignSelect();
    http.expectOne((r) => r.url.includes('/messages')).flush({
      campaign_name: 'Curse of Strahd',
      whispers: [],
      roll_requests: [],
    });
    http.expectOne((r) => r.url.includes('/party')).flush([]);
    component.partyMembers = [hero('Ezren', 5)];

    component.generateEncounter();

    const req = http.expectOne((r) => r.url.includes('/dm/encounter'));
    expect(req.request.body.edition).toBe('2024 Revision (5.5e)');
    req.flush({ encounter_text: 'Ghouls', monsters: [] });
  });

  it('forges a new campaign under the ruleset the DM is playing', () => {
    TestBed.inject(CharacterStateService).dndEdition.set('2024 Revision (5.5e)');
    component.newCampaignTitle = 'Phyrexia Awakens';

    component.createNewCampaign();

    const req = http.expectOne((r) => r.method === 'POST' && r.url.endsWith('/campaigns/'));
    expect(req.request.body.dnd_edition).toBe('2024 Revision (5.5e)');
    // Answering it would pull the whole workspace load in behind it; the body is
    // the contract under test.
    req.flush({ campaign_name: 'Phyrexia Awakens' }, { status: 500, statusText: 'Server Error' });
  });

  it('gives a monster with no DEX an average initiative rather than NaN', () => {
    component.encounterResult = {
      encounter_text: 'Something lurks',
      monsters: [
        { name: 'Ghoul', hp: 22, ac: 12, quantity: 1, statblock_summary: '' } as EncounterMonster,
      ],
    };

    component.addEncounterMonstersToInitiative();

    expect(component.combatants[0].initiative).toBe(10);
    expect(component.combatants[0].dex).toBe(10);
  });
});
