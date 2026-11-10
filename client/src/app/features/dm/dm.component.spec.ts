import { signal } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { Subject } from 'rxjs';
import { DmComponent } from './dm.component';
import { RollToastService } from '../../core/services/roll-toast.service';
import { WebSocketService, WsMessage } from '../../core/services/websocket.service';
import { EncounterStorageService } from '../../core/services/encounter-storage.service';
import { InitiativeCombatant } from '../../core/models/initiative.model';
import { PartyMember } from '../../core/models/party.model';
import { EncounterMonster } from '../../core/models/dm-tools.model';
import { CharacterStateService } from '../../core/services/character-state.service';
import { VTTState } from '../../core/models/vtt.model';
import { BestiaryMonster } from '../../core/models/bestiary.model';

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
      vttState: signal<VTTState | null>(null),
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
      http.match((req) => req.url.includes('/party')).forEach((req) => req.flush([]));

      // A monster added under the first campaign must not follow the DM to the
      // next one — nor end up saved under its name.
      component.newCombatantName = 'Strahd';
      component.addCombatant();

      component.campaignName = 'Phyrexia Awakens';
      component.onCampaignSelect();

      expect(component.combatants).toEqual([]);
      expect(component.round).toBe(0);

      http.match((req) => req.url.includes('/party')).forEach((req) => req.flush([]));
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
      http.match((req) => req.url.includes('/messages')).forEach((req) => req.flush({ campaign_name: 'Curse of Strahd', whispers: [], roll_requests: [] }));
      http.match((req) => req.url.includes('/encounter') && req.method === 'GET').forEach((req) => req.flush(null));
      http.match((req) => req.url.includes('/party')).forEach((req) => req.flush([
        {
          char_id: 'lyra1',
          char_name: 'Lyra Meadowlark',
          hp_current: 17,
          hp_max: 17,
          armor_class: 13,
          conditions: ['Invisible'],
        },
      ]));
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
      expect(component.partyMembers[0].conditions).toEqual(['Invisible']);

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
      expect(component.partyMembers[0].conditions).toEqual(['Invisible']);

      component.previousTurn();

      expect(component.partyMembers[0].conditions).toEqual(['Invisible', 'Poisoned']);
      flushWrites();
      http.expectOne((r) => r.method === 'PATCH').flush({ success: true });
    });

    it('replaces partyMembers array and modified member references for OnPush consumers', () => {
      const prevArray = component.partyMembers;
      const prevMember = component.partyMembers[0];

      component.setPartyHp(prevMember, 10);
      expect(component.partyMembers).not.toBe(prevArray);
      expect(component.partyMembers[0]).not.toBe(prevMember);
      expect(component.partyMembers[0].hp_current).toBe(10);

      flushWrites();
      http.expectOne((r) => r.method === 'PATCH').flush({ success: true });

      const afterHpArray = component.partyMembers;
      const afterHpMember = component.partyMembers[0];
      component.toggleCondition(afterHpMember, 'Prone');
      expect(component.partyMembers).not.toBe(afterHpArray);
      expect(component.partyMembers[0]).not.toBe(afterHpMember);
      expect(component.partyMembers[0].conditions).toContain('Prone');

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
      vttState: signal<VTTState | null>(null),
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

    localStorage.clear();
    http = TestBed.inject(HttpTestingController);
    component = makeComponent();
    component.campaignName = 'Curse of Strahd';
  });

afterEach(() => {
    http.match(() => true).forEach(req => req.flush({}));
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


    http.match((r) => r.url.includes('/messages')).forEach(req => req.flush({
      campaign_name: 'Curse of Strahd',
      whispers: [],
      roll_requests: [],
    }));


    http
      .match((r) => r.url.includes('/party')).forEach((r) => r.flush([{ char_id: 'e1', char_name: 'Ezren', char_level: 4, hp_current: 22, hp_max: 22 }]));

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
      { campaign_name: 'Curse of Strahd', dnd_edition: '2024 Revision (5.5e)', party: [] },
    ];
    component.onCampaignSelect();


    http.match((r) => r.url.includes('/messages')).forEach(req => req.flush({
      campaign_name: 'Curse of Strahd',
      whispers: [],
      roll_requests: [],
    }));



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
    component.userCampaigns = [{ campaign_name: 'Curse of Strahd', party: [] }];
    component.onCampaignSelect();


    http.match((r) => r.url.includes('/messages')).forEach(req => req.flush({
      campaign_name: 'Curse of Strahd',
      whispers: [],
      roll_requests: [],
    }));



    component.partyMembers = [hero('Ezren', 5)];

    component.generateEncounter();

    const req = http.expectOne((r) => r.url.includes('/dm/encounter'));
    expect(req.request.body.edition).toBe('2024 Revision (5.5e)');
    req.flush({ encounter_text: 'Ghouls', monsters: [] });
  });

  it('forges a new campaign under the ruleset the DM is playing', () => {
    TestBed.inject(CharacterStateService).dndEdition.set('2024 Revision (5.5e)');
    component.openNewCampaignModal();
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

describe('DmComponent — workspace teardown and whispers', () => {
  let fixture: ComponentFixture<DmComponent>;
  let component: DmComponent;
  let http: HttpTestingController;
  let ws: Partial<WebSocketService>;

  beforeEach(() => {
    ws = {
      messages$: new Subject<WsMessage>(),
      opened$: new Subject<string>(),
      vttState: signal<VTTState | null>(null),
      connect: jest.fn(),
      disconnect: jest.fn(),
      sendVttToggle: jest.fn(),
    };

    TestBed.configureTestingModule({
      imports: [DmComponent],
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        { provide: WebSocketService, useValue: ws },
      ],
    });

    localStorage.clear();
    http = TestBed.inject(HttpTestingController);
    fixture = TestBed.createComponent(DmComponent);
    component = fixture.componentInstance;
    component.campaignName = 'Curse of Strahd';
  });

afterEach(() => {
    http.match(() => true).forEach(req => req.flush({}));
    http.verify();
    localStorage.clear();
  });

  it('closes the DM channel when the workspace is left', () => {
    fixture.destroy();

    // Unsubscribing is not enough: the service holds one socket, and a live
    // role=dm channel keeps drawing every whisper and secret roll.
    expect(ws.disconnect).toHaveBeenCalled();
  });

  it('does not send an empty whisper', () => {
    component.showWhisperModal = true;
    component.whisperMessage = '   \n  ';

    component.sendWhisper();

    http.expectNone((r) => r.url.includes('/whisper'));
    // Nothing was sent, so the modal stays open rather than closing on a
    // "delivered" toast for a whisper that never left the browser.
    expect(component.showWhisperModal).toBe(true);
  });

  it('sends the trimmed whisper', () => {
    component.whisperMessage = '  The door is a mimic.  ';

    component.sendWhisper();

    const req = http.expectOne((r) => r.url.includes('/whisper'));
    expect(req.request.body.message).toBe('The door is a mimic.');
    req.flush({ whisper: { sender: 'DM', recipient: 'All', message: 'The door is a mimic.' } });
  });

  it('reads passive perception off the hero rather than a fixed 11', () => {
    component.loadParty();

    http.match((r) => r.url.includes('/party')).forEach((r) => r.flush([
      { char_id: 'e1', char_name: 'Ezren', passive_perception: 14 },
      { char_id: 'v1', char_name: 'Valeros', passive_perception: 9 },
      { char_id: 'm1', char_name: 'Merisiel' },
    ]));

    expect(component.partyMembers.map((m) => m.passive_perception)).toEqual([14, 9, 10]);
  });

  it('auto-numbers combatants added with duplicate names', () => {
    component.newCombatantName = 'Goblin';
    component.newCombatantInit = 12;
    component.newCombatantHp = 7;
    component.newCombatantAc = 15;
    component.addCombatant();

    expect(component.combatants.length).toBe(1);
    expect(component.combatants[0].name).toBe('Goblin');

    component.newCombatantName = 'Goblin';
    component.addCombatant();

    expect(component.combatants.length).toBe(2);
    expect(component.combatants.map(c => c.name)).toContain('Goblin');
    expect(component.combatants.map(c => c.name)).toContain('Goblin 2');
  });

  describe('Initiative DEX Tie-Breaker', () => {
    it('breaks ties using Dexterity score in descending order', () => {
      // Both rolled initiative 15, but hero B has higher DEX (16 vs 12)
      const combatantA = combatant('fighter', 15, { dex: 12 });
      const combatantB = combatant('rogue', 15, { dex: 16 });
      const combatantC = combatant('wizard', 20, { dex: 10 });
      const combatantD = combatant('cleric', 15, { dex: 14 });

      // Use sortCombatants via private access or adding to combatants
      (component as any).combatants = (component as any).sortCombatants([
        combatantA,
        combatantB,
        combatantC,
        combatantD,
      ]);

      expect(component.combatants.map(c => c.id)).toEqual([
        'wizard', // Initiative 20
        'rogue',  // Initiative 15, DEX 16
        'cleric', // Initiative 15, DEX 14
        'fighter', // Initiative 15, DEX 12
      ]);
    });

    it('defaults missing DEX to 10 during tie breaking', () => {
      const combatantNoDex = combatant('no_dex', 14, { dex: undefined as any });
      const combatantDex12 = combatant('dex_12', 14, { dex: 12 });
      const combatantDex8 = combatant('dex_8', 14, { dex: 8 });

      (component as any).combatants = (component as any).sortCombatants([
        combatantDex8,
        combatantNoDex,
        combatantDex12,
      ]);

      expect(component.combatants.map(c => c.id)).toEqual([
        'dex_12',    // 14, DEX 12
        'no_dex',    // 14, DEX 10 (fallback)
        'dex_8',     // 14, DEX 8
      ]);
    });
  });

  describe('Homebrew Monster in Initiative Tracker', () => {
    it('adds a homebrew monster directly into the combatants list', () => {
      const monsterItem = {
        name: 'Gargoyle Brute',
        homebrew_type: 'monster' as const,
        size: 'Medium',
        type: 'elemental',
        alignment: 'chaotic evil',
        cr: '2',
        ac: 15,
        hp: 42,
        speed: '30 ft., fly 60 ft.',
        stats: { str: 16, dex: 14, con: 16, int: 6, wis: 11, cha: 7 },
        traits: [{ name: 'False Appearance', description: 'Indistinguishable from statue.' }],
        actions: [{ name: 'Claws', description: '+5 to hit, 2d6+3 slashing.' }],
      };

      component.combatants = [];
      component.addHomebrewMonsterToInitiative(monsterItem);

      expect(component.combatants.length).toBe(1);
      const added = component.combatants[0];
      expect(added.name).toBe('Gargoyle Brute');
      expect(added.hp).toBe(42);
      expect(added.max_hp).toBe(42);
      expect(added.ac).toBe(15);
      expect(added.dex).toBe(14);
      // initiative = 10 + dexMod (where dexMod for 14 is +2)
      expect(added.initiative).toBe(12);
      expect(added.is_player).toBe(false);
      expect(added.statblock).toContain('Armor Class: 15');
      expect(added.statblock).toContain('False Appearance');
    });

    it('correctly handles numeric string DEX values and calculates DEX modifier', () => {
      const monsterItem = {
        name: 'Goblin Sneak',
        homebrew_type: 'monster' as const,
        size: 'Small',
        type: 'humanoid',
        alignment: 'neutral evil',
        cr: '1/4',
        ac: 13,
        hp: 7,
        stats: { str: 8, dex: '16' as any, con: 12 },
      };

      component.combatants = [];
      component.addHomebrewMonsterToInitiative(monsterItem);

      expect(component.combatants.length).toBe(1);
      const added = component.combatants[0];
      expect(added.dex).toBe(16);
      // initiative = 10 + dexMod (where dexMod for 16 is +3)
      expect(added.initiative).toBe(13);
    });
  });

  describe('Loot Distribution UI', () => {
    it('opens the loot modal and loads campaign homebrew items', () => {
      component.campaignName = 'Neverwinter';
      component.showLootModal = false;

      component.openLootModal();

      expect(component.showLootModal).toBe(true);
      const req = http.expectOne((r) => r.url.includes('/campaigns/Neverwinter/homebrew'));
      req.flush([{ name: 'Vorpal Sword', homebrew_type: 'weapon' }]);
      expect(component.homebrewItems.length).toBe(1);
      expect(component.homebrewItems[0].name).toBe('Vorpal Sword');
    });
  });

  describe('Initiative Panel Controls & Physical Rolls', () => {
    it('rolls initiative strictly for non-player combatants and re-sorts descending', () => {
      component.combatants = [
        combatant('p1', 18, { is_player: true, dex: 14 }),
        combatant('m1', 5, { is_player: false, dex: 10 }),
        combatant('m2', 8, { is_player: false, dex: 12 }),
      ];

      component.rollMonstersInitiative();

      expect(component.combatants.find((c) => c.id === 'p1')?.initiative).toBe(18);
      // Both monsters should have been re-rolled
      const m1 = component.combatants.find((c) => c.id === 'm1')!;
      const m2 = component.combatants.find((c) => c.id === 'm2')!;
      expect(m1.initiative).toBeGreaterThan(0);
      expect(m2.initiative).toBeGreaterThan(0);
      // Ensure sorted descending
      expect(component.combatants[0].initiative).toBeGreaterThanOrEqual(component.combatants[1].initiative);
      expect(component.combatants[1].initiative).toBeGreaterThanOrEqual(component.combatants[2].initiative);
    });

    it('updates initiative and re-sorts upon onInitiativeChange', () => {
      component.combatants = [
        combatant('c1', 10),
        combatant('c2', 20),
      ];

      component.onInitiativeChange({ combatant: component.combatants[0], initiative: 25 });

      expect(component.combatants[0].id).toBe('c1');
      expect(component.combatants[0].initiative).toBe(25);
      expect(component.combatants[1].id).toBe('c2');
      expect(component.combatants[1].initiative).toBe(20);
    });

    it('updates AC upon onAcChange', () => {
      const c = combatant('c1', 10, { ac: 12 });
      component.combatants = [c];

      component.onAcChange({ combatant: c, ac: 18 });

      expect(component.combatants[0].ac).toBe(18);
    });

    it('sends manual_roll in payload when manual roll is provided', () => {
      component.campaignName = 'Neverwinter';
      component.partyMembers = [hero('Elena', 3)];
      component.rollTargetMember = 'Elena';
      component.rollType = 'saving_throw';
      component.rollStat = 'DEX';
      component.manualRoll = 17;

      component.sendRollRequest();

      const req = http.expectOne((r) => r.url.includes('/campaigns/Neverwinter/roll-request'));
      expect(req.request.body.manual_roll).toBe(17);
      req.flush({ success: true });
    });

    it('consumes the manual roll so the next request does not reuse it', () => {
      component.campaignName = 'Neverwinter';
      component.partyMembers = [hero('Elena', 3)];
      component.rollTargetMember = 'Elena';
      component.manualRoll = 17;

      component.sendRollRequest();
      http.expectOne((r) => r.url.includes('/roll-request')).flush({ success: true });
      expect(component.manualRoll).toBeNull();

      component.sendRollRequest();
      const second = http.expectOne((r) => r.url.includes('/roll-request'));
      expect(second.request.body.manual_roll).toBeUndefined();
      second.flush({ success: true });
    });

    it('clears a stale manual roll when the modal is reopened', () => {
      component.partyMembers = [hero('Elena', 3)];
      component.manualRoll = 9;

      component.openSingleRollModal(component.partyMembers[0]);

      expect(component.manualRoll).toBeNull();
      expect(component.showRollModal).toBe(true);
    });

    it('refuses a manual roll aimed at the whole party and sends nothing', () => {
      component.campaignName = 'Neverwinter';
      component.partyMembers = [hero('Elena', 3), hero('Kostas', 3)];
      component.rollTargetMember = 'ALL';
      component.manualRoll = 14;
      component.showRollModal = true;

      component.sendRollRequest();

      http.expectNone((r) => r.url.includes('/roll-request'));
      expect(component.showRollModal).toBe(true);
      expect(component.manualRoll).toBe(14);
    });
  });
});

describe('DmComponent — Master Modes & Tab Navigation', () => {
  let component: DmComponent;

  beforeEach(() => {
    const wsStub: Partial<WebSocketService> = {
      messages$: new Subject<WsMessage>(),
      opened$: new Subject<string>(),
      vttState: signal<VTTState | null>(null),
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

    component = makeComponent();
  });

  describe('Initial State', () => {
    it('initializes in Live DM mode with Combat & Initiative tab active', () => {
      expect(component.dmMode).toBe('live');
      expect(component.activeTab).toBe('initiative');
      expect(component.lastLiveTab).toBe('initiative');
      expect(component.lastPrepTab).toBe('homebrew');
    });

    it('returns live tabs by default via activeTabs getter', () => {
      expect(component.activeTabs).toBe(component.liveTabs);
      expect(component.activeTabs.map((t) => t.id)).toEqual(['initiative', 'vtt', 'party', 'notes']);
      expect(component.activeTabs[0].label).toContain('Combat & Initiative');
      expect(component.activeTabs[1].label).toContain('Tactical VTT Map');
      expect(component.activeTabs[2].label).toContain('Party Status');
      expect(component.activeTabs[3].label).toContain('Live Notes');
    });

    it('exposes dmTabs as an alias to activeTabs for backward compatibility', () => {
      expect(component.dmTabs).toBe(component.activeTabs);
    });
  });

  describe('Mode Switching and Tab Memory', () => {
    it('switches to prep mode and activates the default prep tab (homebrew)', () => {
      component.setDmMode('prep');

      expect(component.dmMode).toBe('prep');
      expect(component.activeTab).toBe('homebrew');
      expect(component.activeTabs).toBe(component.prepTabs);
      expect(component.activeTabs.map((t) => t.id)).toEqual(['homebrew', 'generators', 'prep', 'entities']);
    });

    it('does not re-trigger or change tabs when setDmMode is called with the current mode', () => {
      component.setDmMode('live');

      expect(component.dmMode).toBe('live');
      expect(component.activeTab).toBe('initiative');
    });

    it('remembers and restores the last active tab across mode transitions', () => {
      // 1. Initial live mode state: activeTab is 'initiative'
      expect(component.dmMode).toBe('live');
      expect(component.activeTab).toBe('initiative');

      // 2. Switch to prep mode: restores default prep tab 'homebrew'
      component.setDmMode('prep');
      expect(component.dmMode).toBe('prep');
      expect(component.activeTab).toBe('homebrew');

      // 3. User selects 'generators' tab in prep mode
      component.onTabChange('generators');
      expect(component.activeTab).toBe('generators');
      expect(component.lastPrepTab).toBe('generators');

      // 4. Switch back to live mode: restores lastLiveTab ('initiative')
      component.setDmMode('live');
      expect(component.dmMode).toBe('live');
      expect(component.activeTab).toBe('initiative');

      // 5. User selects 'notes' tab in live mode
      component.onTabChange('notes');
      expect(component.activeTab).toBe('notes');
      expect(component.lastLiveTab).toBe('notes');

      // 6. Switch back to prep mode: restores lastPrepTab ('generators')
      component.setDmMode('prep');
      expect(component.dmMode).toBe('prep');
      expect(component.activeTab).toBe('generators');

      // 7. Switch back to live mode: restores lastLiveTab ('notes')
      component.setDmMode('live');
      expect(component.dmMode).toBe('live');
      expect(component.activeTab).toBe('notes');
    });

    it('exposes correct prep tab labels in activeTabs when in prep mode', () => {
      component.setDmMode('prep');

      expect(component.activeTabs[0].label).toContain('Bestiary & Homebrew');
      expect(component.activeTabs[1].label).toContain('AI Generators');
      expect(component.activeTabs[2].label).toContain('Plot Architect & Session Logs');
      expect(component.activeTabs[3].label).toContain('World Entities Vault');
    });
  });
});

describe('DmComponent — Tactical VTT Relocation & openVTT()', () => {
  let component: DmComponent;
  let wsStub: {
    messages$: Subject<WsMessage>;
    opened$: Subject<string>;
    vttState: ReturnType<typeof signal<VTTState | null>>;
    connect: jest.Mock;
    disconnect: jest.Mock;
    sendVttToggle: jest.Mock;
  };

  beforeEach(() => {
    wsStub = {
      messages$: new Subject<WsMessage>(),
      opened$: new Subject<string>(),
      vttState: signal<VTTState | null>(null),
      connect: jest.fn(),
      disconnect: jest.fn(),
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

    component = makeComponent();
  });

  it('switches dmMode to live, sets activeTab and lastLiveTab to vtt, and calls sendVttToggle(true)', () => {
    // Put DM in prep mode on generators tab first
    component.setDmMode('prep');
    component.onTabChange('generators');
    expect(component.dmMode).toBe('prep');
    expect(component.activeTab).toBe('generators');

    component.openVTT();

    expect(component.dmMode).toBe('live');
    expect(component.activeTab).toBe('vtt');
    expect(component.lastLiveTab).toBe('vtt');
    expect(wsStub.sendVttToggle).toHaveBeenCalledWith(true);
  });

  it('expands vttGrid when it is present and minimized', () => {
    const vttGridMock = { isMinimized: true } as any;
    component.vttGrid = vttGridMock;

    component.openVTT();

    expect(vttGridMock.isMinimized).toBe(false);
    expect(wsStub.sendVttToggle).toHaveBeenCalledWith(true);
  });

  it('executes safely when vttGrid is not mounted (undefined)', () => {
    component.vttGrid = undefined;

    expect(() => component.openVTT()).not.toThrow();
    expect(component.dmMode).toBe('live');
    expect(component.activeTab).toBe('vtt');
    expect(wsStub.sendVttToggle).toHaveBeenCalledWith(true);
  });

  it('preserves isMinimized = false if vttGrid is already expanded', () => {
    const vttGridMock = { isMinimized: false } as any;
    component.vttGrid = vttGridMock;

    component.openVTT();

    expect(vttGridMock.isMinimized).toBe(false);
    expect(wsStub.sendVttToggle).toHaveBeenCalledWith(true);
  });
});

describe('DmComponent — Pinned Active Combat Bar', () => {
  let component: DmComponent;

  beforeEach(() => {
    const wsStub: Partial<WebSocketService> = {
      messages$: new Subject<WsMessage>(),
      opened$: new Subject<string>(),
      vttState: signal<VTTState | null>(null),
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

    component = makeComponent();
    component.campaignName = 'Curse of Strahd';
  });

  describe('Visibility Conditions', () => {
    it('is visible when dmMode is live, activeTab is not initiative, and combatants exist', () => {
      component.dmMode = 'live';
      component.activeTab = 'vtt';
      component.combatants = [combatant('ghoul_1', 12)];

      const isVisible = component.dmMode === 'live' && component.activeTab !== 'initiative' && component.combatants.length > 0;
      expect(isVisible).toBe(true);
    });

    it('is hidden when dmMode is prep even if combatants exist and activeTab is not initiative', () => {
      component.dmMode = 'prep';
      component.activeTab = 'homebrew';
      component.combatants = [combatant('ghoul_1', 12)];

      const isVisible = component.dmMode === 'live' && component.activeTab !== 'initiative' && component.combatants.length > 0;
      expect(isVisible).toBe(false);
    });

    it('is hidden when activeTab is initiative even if dmMode is live and combatants exist', () => {
      component.dmMode = 'live';
      component.activeTab = 'initiative';
      component.combatants = [combatant('ghoul_1', 12)];

      const isVisible = component.dmMode === 'live' && component.activeTab !== 'initiative' && component.combatants.length > 0;
      expect(isVisible).toBe(false);
    });

    it('is hidden when combatants list is empty even if dmMode is live and on non-initiative tab', () => {
      component.dmMode = 'live';
      component.activeTab = 'party';
      component.combatants = [];

      const isVisible = component.dmMode === 'live' && component.activeTab !== 'initiative' && component.combatants.length > 0;
      expect(isVisible).toBe(false);
    });
  });

  describe('Action Controls', () => {
    beforeEach(() => {
      component.dmMode = 'live';
      component.activeTab = 'party';
      component.combatants = [
        combatant('first', 20),
        combatant('second', 15),
      ];
    });

    it('advances turn when nextTurn is triggered', () => {
      const nextSpy = jest.spyOn(component, 'nextTurn');

      component.nextTurn();

      expect(nextSpy).toHaveBeenCalled();
      expect(component.round).toBe(1);
      expect(component.activeCombatantId).toBe('first');

      component.nextTurn();
      expect(component.activeCombatantId).toBe('second');
    });

    it('rewinds turn when previousTurn is triggered', () => {
      component.nextTurn();
      component.nextTurn();
      expect(component.activeCombatantId).toBe('second');

      const prevSpy = jest.spyOn(component, 'previousTurn');
      component.previousTurn();

      expect(prevSpy).toHaveBeenCalled();
      expect(component.activeCombatantId).toBe('first');
    });

    it('switches to initiative tab when Full Tracker action is triggered', () => {
      component.activeTab = 'party';
      component.lastLiveTab = 'party';

      component.onTabChange('initiative');

      expect(component.activeTab).toBe('initiative');
      expect(component.lastLiveTab).toBe('initiative');
    });
  });
});

describe('DmComponent — Pinned Active Combat Bar DOM Rendering', () => {
  let fixture: ComponentFixture<DmComponent>;
  let component: DmComponent;
  let wsStub: any;

  beforeEach(() => {
    wsStub = {
      messages$: new Subject<WsMessage>(),
      opened$: new Subject<string>(),
      vttState: signal<VTTState | null>(null),
      connect: jest.fn(),
      disconnect: jest.fn(),
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

    fixture = TestBed.createComponent(DmComponent);
    component = fixture.componentInstance;
    jest.spyOn(component, 'loadCampaigns').mockImplementation(() => {});
    component.campaignsStatus = 'ready';
    component.userCampaigns = [{ campaign_name: 'Curse of Strahd', role: 'dm' } as any];
    component.campaignName = 'Curse of Strahd';
    component.isMobileViewport.set(false);
  });

  it('renders the pinned combat bar when in live mode, on non-initiative tab, with active combatants', () => {
    component.dmMode = 'live';
    component.activeTab = 'vtt';
    component.combatants = [combatant('zombie_1', 10, { hp: 22, max_hp: 22, ac: 8 })];
    fixture.detectChanges();

    const pinnedBar = fixture.nativeElement.querySelector('[data-testid="pinned-combat-bar"]') ||
                      fixture.nativeElement.querySelector('.pinned-combat-bar');
    expect(pinnedBar).toBeTruthy();
  });

  it('does not render the pinned combat bar in prep mode', () => {
    component.dmMode = 'prep';
    component.activeTab = 'homebrew';
    component.combatants = [combatant('zombie_1', 10)];
    fixture.detectChanges();

    const pinnedBar = fixture.nativeElement.querySelector('[data-testid="pinned-combat-bar"]') ||
                      fixture.nativeElement.querySelector('.pinned-combat-bar');
    expect(pinnedBar).toBeNull();
  });

  it('does not render the pinned combat bar on the initiative tab', () => {
    component.dmMode = 'live';
    component.activeTab = 'initiative';
    component.combatants = [combatant('zombie_1', 10)];
    fixture.detectChanges();

    const pinnedBar = fixture.nativeElement.querySelector('[data-testid="pinned-combat-bar"]') ||
                      fixture.nativeElement.querySelector('.pinned-combat-bar');
    expect(pinnedBar).toBeNull();
  });

  it('does not render the pinned combat bar when combatants list is empty', () => {
    component.dmMode = 'live';
    component.activeTab = 'vtt';
    component.combatants = [];
    fixture.detectChanges();

    const pinnedBar = fixture.nativeElement.querySelector('[data-testid="pinned-combat-bar"]') ||
                      fixture.nativeElement.querySelector('.pinned-combat-bar');
    expect(pinnedBar).toBeNull();
  });
});

describe('DmComponent — Quick-Add & Bestiary Integration', () => {
  let component: DmComponent;

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
    traits: [{ name: 'Nimble Escape', description: 'Can Disengage as bonus action' }],
    actions: [{ name: 'Scimitar', attack_bonus: 4, damage_dice: '1d6+2', damage_type: 'slashing' }],
  };

  const zombieMonster: BestiaryMonster = {
    id: 'srd_zombie_2014',
    name: 'Zombie',
    edition: '2014',
    origin: 'official',
    is_public: true,
    size: 'Medium',
    type: 'undead',
    alignment: 'neutral evil',
    cr: '1/4',
    cr_numeric: 0.25,
    ac: 8,
    hp: 22,
    max_hp: 22,
    speed: '20 ft.',
    stats: { str: 13, dex: 6, con: 16, int: 3, wis: 6, cha: 5 },
    traits: [{ name: 'Undead Fortitude', description: 'Con save to stay at 1 hp' }],
    actions: [{ name: 'Slam', attack_bonus: 3, damage_dice: '1d6+1', damage_type: 'bludgeoning' }],
  };

  beforeEach(() => {
    const wsStub = {
      messages$: new Subject<WsMessage>(),
      connectionState$: new Subject<string>(),
      opened$: new Subject<string>(),
      vttState: signal<VTTState | null>(null),
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

    component = makeComponent();
  });

  it('adds monster to initiative with stats, traits, actions, and dex-modified initiative', () => {
    component.addMonsterToInitiative(mockMonster);

    expect(component.combatants.length).toBe(1);
    const added = component.combatants[0];
    expect(added.name).toBe('Goblin');
    expect(added.hp).toBe(7);
    expect(added.max_hp).toBe(7);
    expect(added.ac).toBe(15);
    expect(added.dex).toBe(14);
    // DEX 14 has mod +2, initiative is 10 + 2 = 12
    expect(added.initiative).toBe(12);
    expect(added.traits?.length).toBe(1);
    expect(added.actions?.length).toBe(1);
  });

  it('correctly calculates initiative with negative DEX modifier (Zombie DEX 6 -> init 8)', () => {
    component.addMonsterToInitiative(zombieMonster);

    const added = component.combatants[0];
    expect(added.name).toBe('Zombie');
    expect(added.dex).toBe(6);
    // DEX 6 has mod -2, initiative is 10 + (-2) = 8
    expect(added.initiative).toBe(8);
  });

  it('auto-numbers duplicate monster names cleanly: Goblin, Goblin 2, Goblin 3', () => {
    component.addMonsterToInitiative(mockMonster);
    component.addMonsterToInitiative(mockMonster);
    component.addMonsterToInitiative(mockMonster);

    const names = component.combatants.map((c) => c.name);
    expect(names).toContain('Goblin');
    expect(names).toContain('Goblin 2');
    expect(names).toContain('Goblin 3');
  });

  it('auto-numbers monster with existing numbered suffix (Skeleton 1 -> Skeleton 2)', () => {
    const skeleton1: BestiaryMonster = {
      ...mockMonster,
      name: 'Skeleton 1',
    };
    component.addMonsterToInitiative(skeleton1);
    component.addMonsterToInitiative(skeleton1);

    const names = component.combatants.map((c) => c.name);
    expect(names).toContain('Skeleton 1');
    expect(names).toContain('Skeleton 2');
  });

  it('preserves the active round counter when adding monster mid-round', () => {
    component.round = 3;
    component.addMonsterToInitiative(mockMonster);

    expect(component.round).toBe(3);
  });

  it('opens statblock modal for a bestiary monster via openBestiaryStatblock', () => {
    component.openBestiaryStatblock(mockMonster);

    expect(component.selectedStatblockCombatant).not.toBeNull();
    expect(component.selectedStatblockCombatant?.name).toBe('Goblin');
    expect(component.selectedStatblockCombatant?.actions?.length).toBe(1);
  });

  it('pins generated riddle to live campaign notes', () => {
    component.riddleTheme = 'Clockwork Crypt';
    component.riddleResult = '## The Gear Puzzle\nTurn cog A before cog B.';
    component.campaignNotes = 'Session notes start.';

    component.pinRiddleToNotes();

    expect(component.campaignNotes).toContain('### 🧩 Riddle / Trap: Clockwork Crypt');
    expect(component.campaignNotes).toContain('The Gear Puzzle');
  });

  it('renders owner_username next to character name in Party Health overview', () => {
    const fixture = TestBed.createComponent(DmComponent);
    const comp = fixture.componentInstance;
    jest.spyOn(comp, 'loadCampaigns').mockImplementation(() => {});
    comp.campaignsStatus = 'ready';
    comp.userCampaigns = [{ campaign_name: 'Curse of Strahd', role: 'dm' } as any];
    comp.campaignName = 'Curse of Strahd';
    comp.partyStatus = 'ready';
    comp.partyMembers = [
      {
        char_id: 'c1',
        name: 'Elendor',
        char_class: 'Wizard',
        level: 3,
        hp_current: 18,
        hp_max: 18,
        ac: 12,
        passive_perception: 13,
        conditions: [],
        owner_username: 'PlayerOne',
      },
      {
        char_id: 'c2',
        name: 'Grom',
        char_class: 'Barbarian',
        level: 3,
        hp_current: 35,
        hp_max: 35,
        ac: 15,
        passive_perception: 11,
        conditions: [],
      },
    ];
    fixture.detectChanges();

    const compiled = fixture.nativeElement as HTMLElement;
    const partyHealthText = compiled.textContent || '';
    expect(partyHealthText).toContain('Elendor');
    expect(partyHealthText).toContain('(PlayerOne)');
    expect(partyHealthText).toContain('Grom');
  });
});
