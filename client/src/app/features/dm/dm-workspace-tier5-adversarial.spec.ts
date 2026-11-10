import { signal } from '@angular/core';
import { ComponentFixture, TestBed, fakeAsync, tick } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { Subject, of, throwError } from 'rxjs';

import { DmComponent } from './dm.component';
import { InitiativePanelComponent } from './panels/initiative-panel/initiative-panel.component';
import { GeneratorsPanelComponent } from './panels/generators-panel/generators-panel.component';
import { StatblockModalComponent } from './modals/statblock-modal/statblock-modal.component';
import { EncounterStorageService } from '../../core/services/encounter-storage.service';
import { BestiaryService } from '../../core/services/bestiary.service';
import { DiceService } from '../../core/services/dice.service';
import { RollToastService } from '../../core/services/roll-toast.service';
import { WebSocketService, WsMessage } from '../../core/services/websocket.service';
import { VTTState } from '../../core/models/vtt.model';
import { InitiativeCombatant, EncounterState } from '../../core/models/initiative.model';
import { BestiaryMonster, MonsterAction, MonsterTrait } from '../../core/models/bestiary.model';

describe('Tier 5 White-Box Adversarial Stress Test Suite', () => {
  // ---------------------------------------------------------------------------
  // Helpers & Fixtures
  // ---------------------------------------------------------------------------
  function makeCombatant(id: string, overrides: Partial<InitiativeCombatant> = {}): InitiativeCombatant {
    return {
      id,
      name: `Monster ${id}`,
      initiative: 10,
      hp: 20,
      max_hp: 20,
      ac: 12,
      dex: 10,
      is_player: false,
      conditions: [],
      ...overrides,
    };
  }

  function makeMonster(id: string, overrides: Partial<BestiaryMonster> = {}): BestiaryMonster {
    return {
      id,
      name: `SRD ${id}`,
      edition: '2014',
      origin: 'official',
      is_public: true,
      size: 'Medium',
      type: 'monstrosity',
      alignment: 'neutral',
      cr: '1',
      cr_numeric: 1,
      ac: 13,
      hp: 22,
      max_hp: 22,
      speed: '30 ft.',
      stats: { str: 14, dex: 12, con: 12, int: 6, wis: 10, cha: 6 },
      traits: [],
      actions: [],
      ...overrides,
    };
  }

  // ===========================================================================
  // SUITE 1: LocalStorage Corruption in EncounterStorageService
  // ===========================================================================
  describe('1. EncounterStorageService LocalStorage Corruption & Hardening', () => {
    let service: EncounterStorageService;
    const CAMPAIGN = 'Strahd_Adversarial_Lab';
    const KEY = `dnd.encounter.v1.${CAMPAIGN}`;

    beforeEach(() => {
      TestBed.configureTestingModule({});
      service = TestBed.inject(EncounterStorageService);
      localStorage.clear();
    });

    afterEach(() => {
      localStorage.clear();
      jest.restoreAllMocks();
    });

    it('gracefully returns null when stored data is invalid JSON syntax', () => {
      const corruptInputs = [
        '{',
        '{"v": 1, "state": {',
        'undefined',
        '[object Object]',
        'NaN',
        '{"v": 1, "state": {"round": 1, "combatants": [}',
      ];

      for (const corrupt of corruptInputs) {
        localStorage.setItem(KEY, corrupt);
        expect(service.load(CAMPAIGN)).toBeNull();
      }
    });

    it('rejects payloads with missing or non-matching storage version', () => {
      const payloads = [
        { state: { round: 1, activeCombatantId: null, combatants: [] } }, // missing v
        { v: 0, state: { round: 1, activeCombatantId: null, combatants: [] } },
        { v: 2, state: { round: 1, activeCombatantId: null, combatants: [] } },
        { v: '1', state: { round: 1, activeCombatantId: null, combatants: [] } },
        { v: null, state: { round: 1, activeCombatantId: null, combatants: [] } },
      ];

      for (const payload of payloads) {
        localStorage.setItem(KEY, JSON.stringify(payload));
        expect(service.load(CAMPAIGN)).toBeNull();
      }
    });

    it('rejects payloads where state is not a record or round is corrupted', () => {
      const invalidStates = [
        { v: 1, state: null },
        { v: 1, state: 'combat_in_progress' },
        { v: 1, state: [] },
        { v: 1, state: { round: -1, activeCombatantId: null, combatants: [] } },
        { v: 1, state: { round: 2.718, activeCombatantId: null, combatants: [] } },
        { v: 1, state: { round: 'round 3', activeCombatantId: null, combatants: [] } },
        { v: 1, state: { round: NaN, activeCombatantId: null, combatants: [] } },
        { v: 1, state: { round: Infinity, activeCombatantId: null, combatants: [] } },
      ];

      for (const bad of invalidStates) {
        localStorage.setItem(KEY, JSON.stringify(bad));
        expect(service.load(CAMPAIGN)).toBeNull();
      }
    });

    it('rejects combatants containing nulls, primitives, or missing critical fields', () => {
      const corruptedCombatantArrays = [
        [null],
        [undefined],
        [123],
        ['goblin_1'],
        [{ id: '', name: 'Nameless', hp: 10, max_hp: 10, ac: 10, dex: 10, initiative: 10, is_player: false, conditions: [] }],
        [{ id: 'g1', name: '', hp: 10, max_hp: 10, ac: 10, dex: 10, initiative: 10, is_player: false, conditions: [] }],
        [{ id: 'g1', name: 'G', hp: NaN, max_hp: 10, ac: 10, dex: 10, initiative: 10, is_player: false, conditions: [] }],
        [{ id: 'g1', name: 'G', hp: 10, max_hp: 10, ac: 10, dex: 10, initiative: 10, is_player: 'false', conditions: [] }],
        [{ id: 'g1', name: 'G', hp: 10, max_hp: 10, ac: 10, dex: 10, initiative: 10, is_player: false, conditions: 'none' }],
      ];

      for (const list of corruptedCombatantArrays) {
        const payload = {
          v: 1,
          state: { round: 1, activeCombatantId: null, combatants: list },
        };
        localStorage.setItem(KEY, JSON.stringify(payload));
        expect(service.load(CAMPAIGN)).toBeNull();
      }
    });

    it('drops encounter if deathSaves, stats, traits, or actions contain corrupted types', () => {
      const base = makeCombatant('mob_1');

      const corruptedAdditions = [
        { deathSaves: { successes: -1, failures: 0 } },
        { deathSaves: { successes: 1, failures: 2.5 } },
        { deathSaves: { successes: 'three', failures: 0 } },
        { stats: { str: 10, dex: 'fast', con: 10, int: 10, wis: 10, cha: 10 } },
        { stats: { str: 10, dex: 10 } }, // missing 4 stats
        { traits: [{ name: '' }] }, // empty name
        { traits: 'keen smell' }, // non-array
        { actions: [{ name: '' }] }, // empty name
        { actions: [{}] }, // missing name entirely
        { actions: 'not_an_array' }, // non-array
      ];

      for (const corrupt of corruptedAdditions) {
        const payload = {
          v: 1,
          state: {
            round: 1,
            activeCombatantId: null,
            combatants: [{ ...base, ...corrupt }],
          },
        };
        localStorage.setItem(KEY, JSON.stringify(payload));
        expect(service.load(CAMPAIGN)).toBeNull();
      }
    });

    it('gracefully tolerates non-finite attack_bonus by dropping invalid bonus without dropping encounter', () => {
      const base = makeCombatant('mob_1');
      const payload = {
        v: 1,
        state: {
          round: 1,
          activeCombatantId: null,
          combatants: [{ ...base, actions: [{ name: 'Bite', attack_bonus: 'plus_five' }] }],
        },
      };
      localStorage.setItem(KEY, JSON.stringify(payload));

      const loaded = service.load(CAMPAIGN);
      expect(loaded).not.toBeNull();
      expect(loaded?.combatants[0].actions?.[0].name).toBe('Bite');
      expect(loaded?.combatants[0].actions?.[0].attack_bonus).toBeUndefined();
    });

    it('recovers safely when activeCombatantId points to a non-existent combatant id', () => {
      const payload = {
        v: 1,
        state: {
          round: 2,
          activeCombatantId: 'ghost_id_not_in_combatants',
          combatants: [makeCombatant('real_1')],
        },
      };
      localStorage.setItem(KEY, JSON.stringify(payload));

      const loaded = service.load(CAMPAIGN);
      expect(loaded).not.toBeNull();
      expect(loaded?.combatants.length).toBe(1);
      expect(loaded?.combatants[0].id).toBe('real_1');
      // activeCombatantId must reset to null rather than pointing at phantom id
      expect(loaded?.activeCombatantId).toBeNull();
    });

    it('safely handles circular references and quota errors in save() without uncaught throw', () => {
      const circularState: any = { round: 1, activeCombatantId: null, combatants: [] };
      circularState.self = circularState;

      expect(() => {
        service.save(CAMPAIGN, circularState);
      }).not.toThrow();

      // QuotaExceededError simulation
      jest.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
        throw new DOMException('Quota exceeded', 'QuotaExceededError');
      });

      expect(() => {
        service.save(CAMPAIGN, { round: 1, activeCombatantId: null, combatants: [makeCombatant('1')] });
      }).not.toThrow();
    });

    it('safely handles empty campaignName and localStorage getItem throws', () => {
      expect(service.load('')).toBeNull();
      expect(() => service.save('', { round: 1, activeCombatantId: null, combatants: [] })).not.toThrow();
      expect(() => service.clear('')).not.toThrow();

      // SecurityError simulation (e.g. sandboxed iframe or private browsing)
      jest.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
        throw new DOMException('Access denied', 'SecurityError');
      });
      expect(service.load(CAMPAIGN)).toBeNull();
    });
  });

  // ===========================================================================
  // SUITE 2: Rapid Mode Toggling, Tab Switching & openVTT Clicks
  // ===========================================================================
  describe('2. DmComponent Rapid Mode Toggling & VTT Integrations', () => {
    let fixture: ComponentFixture<DmComponent>;
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

      fixture = TestBed.createComponent(DmComponent);
      component = fixture.componentInstance;
      jest.spyOn(component, 'loadCampaigns').mockImplementation(() => {});
      component.campaignsStatus = 'ready';
      component.userCampaigns = [{ campaign_name: 'Strahd', role: 'dm' } as any];
      component.campaignName = 'Strahd';
      component.isMobileViewport.set(false);
    });

    afterEach(() => {
      localStorage.clear();
      jest.restoreAllMocks();
    });

    it('endures 100 rapid mode toggles without state desync or crash', () => {
      expect(component.dmMode).toBe('live');
      expect(component.activeTab).toBe('initiative');

      // Set distinct tabs for each mode
      component.onTabChange('party');
      expect(component.lastLiveTab).toBe('party');

      component.setDmMode('prep');
      component.onTabChange('generators');
      expect(component.lastPrepTab).toBe('generators');

      // Rapidly toggle modes 100 times
      for (let i = 0; i < 100; i++) {
        const targetMode = i % 2 === 0 ? 'live' : 'prep';
        component.setDmMode(targetMode);
        expect(component.dmMode).toBe(targetMode);
        if (targetMode === 'live') {
          expect(component.activeTab).toBe('party');
        } else {
          expect(component.activeTab).toBe('generators');
        }
      }
    });

    it('handles 50 rapid openVTT() invocations idempotently', () => {
      component.setDmMode('prep');
      component.onTabChange('homebrew');

      for (let i = 0; i < 50; i++) {
        component.openVTT();
      }

      expect(component.dmMode).toBe('live');
      expect(component.activeTab).toBe('vtt');
      expect(component.lastLiveTab).toBe('vtt');
      expect(wsStub.sendVttToggle).toHaveBeenCalledTimes(50);
      expect(wsStub.sendVttToggle).toHaveBeenLastCalledWith(true);
    });

    it('dynamically renders and hides pinned combat bar across mode and tab changes', () => {
      component.combatants = [
        makeCombatant('c1', { name: 'Ghoul 1', hp: 22, max_hp: 22, ac: 12 }),
        makeCombatant('c2', { name: 'Ghoul 2', hp: 22, max_hp: 22, ac: 12 }),
      ];

      // Case 1: In Live DM on 'initiative' tab -> Pinned bar should NOT render
      component.dmMode = 'live';
      component.activeTab = 'initiative';
      fixture.detectChanges();
      let pinnedBar = fixture.nativeElement.querySelector('[data-testid="pinned-combat-bar"]');
      expect(pinnedBar).toBeNull();

      // Case 2: In Live DM on 'vtt' tab -> Pinned bar MUST render
      component.activeTab = 'vtt';
      fixture.detectChanges();
      pinnedBar = fixture.nativeElement.querySelector('[data-testid="pinned-combat-bar"]');
      expect(pinnedBar).toBeTruthy();
      expect(pinnedBar.textContent).toContain('Ghoul 1');
      expect(pinnedBar.textContent).toContain('Ghoul 2');

      // Case 3: Switch to 'prep' mode -> Pinned bar MUST disappear completely
      component.setDmMode('prep');
      fixture.detectChanges();
      pinnedBar = fixture.nativeElement.querySelector('[data-testid="pinned-combat-bar"]');
      expect(pinnedBar).toBeNull();

      // Case 4: Switch back to 'live' mode (restoring 'vtt') -> Pinned bar reappears
      component.setDmMode('live');
      fixture.detectChanges();
      pinnedBar = fixture.nativeElement.querySelector('[data-testid="pinned-combat-bar"]');
      expect(pinnedBar).toBeTruthy();

      // Case 5: Clear combatants -> Pinned bar vanishes even on 'vtt'
      component.combatants = [];
      fixture.detectChanges();
      pinnedBar = fixture.nativeElement.querySelector('[data-testid="pinned-combat-bar"]');
      expect(pinnedBar).toBeNull();
    });

    it('populates combatant with safe regex escaping when monster name contains regex metacharacters', () => {
      const exoticMonster = makeMonster('exotic_1', {
        name: 'Elder Ooze [Corrosive] (Type: *Deadly*)',
        cr: '5',
        ac: 15,
        hp: 85,
        stats: { str: 18, dex: 8, con: 18, int: 2, wis: 10, cha: 1 },
      });

      // Adding first time
      component.addMonsterToInitiative(exoticMonster);
      expect(component.combatants.length).toBe(1);
      expect(component.combatants[0].name).toBe('Elder Ooze [Corrosive] (Type: *Deadly*)');
      expect(component.combatants[0].ac).toBe(15);
      expect(component.combatants[0].hp).toBe(85);

      // Adding second time: regex escaping must safely auto-number to " 2" without syntax error
      expect(() => {
        component.addMonsterToInitiative(exoticMonster);
      }).not.toThrow();

      expect(component.combatants.length).toBe(2);
      expect(component.combatants.map(c => c.name)).toContain('Elder Ooze [Corrosive] (Type: *Deadly*) 2');

      // Adding third time
      component.addMonsterToInitiative(exoticMonster);
      expect(component.combatants.length).toBe(3);
      expect(component.combatants.map(c => c.name)).toContain('Elder Ooze [Corrosive] (Type: *Deadly*) 3');
    });
  });

  // ===========================================================================
  // SUITE 3: Pinned Active Combat Strip & Turn Progression Hardening
  // ===========================================================================
  describe('3. Pinned Active Combat Strip & Initiative Turn Engine', () => {
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
      component.userCampaigns = [{ campaign_name: 'Strahd', role: 'dm' } as any];
      component.campaignName = 'Strahd';
      component.isMobileViewport.set(false);
      component.dmMode = 'live';
      component.activeTab = 'party'; // non-initiative tab
    });

    afterEach(() => {
      localStorage.clear();
      jest.restoreAllMocks();
    });

    it('advances turns and wraps rounds correctly across 50 turn progressions', () => {
      component.combatants = [
        makeCombatant('c1', { name: 'Alpha', initiative: 20 }),
        makeCombatant('c2', { name: 'Beta', initiative: 15 }),
        makeCombatant('c3', { name: 'Gamma', initiative: 10 }),
      ];

      expect(component.round).toBe(0);
      expect(component.roundLabel).toBe('Not started');
      expect(component.currentTurnName).toBe('—');

      // First advance -> Round 1, Alpha active
      component.nextTurn();
      expect(component.round).toBe(1);
      expect(component.activeCombatantId).toBe('c1');
      expect(component.currentTurnName).toBe('Alpha');

      // Advance to Beta
      component.nextTurn();
      expect(component.round).toBe(1);
      expect(component.activeCombatantId).toBe('c2');
      expect(component.currentTurnName).toBe('Beta');

      // Advance to Gamma
      component.nextTurn();
      expect(component.round).toBe(1);
      expect(component.activeCombatantId).toBe('c3');
      expect(component.currentTurnName).toBe('Gamma');

      // Advance wraps back to Alpha -> Round 2!
      component.nextTurn();
      expect(component.round).toBe(2);
      expect(component.activeCombatantId).toBe('c1');
      expect(component.currentTurnName).toBe('Alpha');

      // Rewind back to Gamma in Round 1
      component.previousTurn();
      expect(component.round).toBe(1);
      expect(component.activeCombatantId).toBe('c3');
      expect(component.currentTurnName).toBe('Gamma');

      // Rewind to Beta, Alpha, and back to round 0
      component.previousTurn(); // Beta
      component.previousTurn(); // Alpha
      component.previousTurn(); // Off top of round 1 -> reset to 0
      expect(component.round).toBe(0);
      expect(component.activeCombatantId).toBeNull();
      expect(component.currentTurnName).toBe('—');
    });

    it('handles removing the currently active combatant without desyncing the tracker', () => {
      component.combatants = [
        makeCombatant('c1', { name: 'Alpha' }),
        makeCombatant('c2', { name: 'Beta' }),
        makeCombatant('c3', { name: 'Gamma' }),
      ];

      component.nextTurn(); // Round 1, Alpha (index 0)
      component.nextTurn(); // Round 1, Beta (index 1) active
      expect(component.activeCombatantId).toBe('c2');

      // Remove Beta (active combatant at index 1)
      component.removeCombatant(1);

      expect(component.combatants.length).toBe(2);
      // Turn passes to Gamma (who slid into index 1)
      expect(component.activeCombatantId).toBe('c3');
      expect(component.currentTurnName).toBe('Gamma');

      // Remove Gamma (now at index 1, which was last combatant)
      component.removeCombatant(1);
      expect(component.combatants.length).toBe(1);
      // Turn wraps to index 0 (Alpha)
      expect(component.activeCombatantId).toBe('c1');
      expect(component.currentTurnName).toBe('Alpha');

      // Remove last combatant Alpha -> Encounter fully clears
      component.removeCombatant(0);
      expect(component.combatants.length).toBe(0);
      expect(component.round).toBe(0);
      expect(component.activeCombatantId).toBeNull();
    });

    it('safely handles combatant with empty name or special characters in pinned bar DOM', () => {
      component.combatants = [
        makeCombatant('empty_name', { name: '', hp: 10, max_hp: 10, ac: 10 }),
        makeCombatant('special_name', { name: '<script>alert("xss")</script>', hp: 5, max_hp: 5, ac: 10 }),
      ];

      component.nextTurn();
      expect(component.activeCombatantId).toBe('empty_name');
      expect(component.currentTurnName).toBe('—'); // Fallback for empty name

      fixture.detectChanges();
      const pinnedBar = fixture.nativeElement.querySelector('[data-testid="pinned-combat-bar"]');
      expect(pinnedBar).toBeTruthy();
      // Should sanitize script tag as plain text, no <script> DOM elements created
      expect(pinnedBar.querySelector('script')).toBeNull();
      expect(pinnedBar.textContent).toContain('<script>alert("xss")</script>');
    });

    it('safely renders extreme and out-of-bounds HP values without crash or invalid DOM', () => {
      component.combatants = [
        makeCombatant('overheal', { name: 'Overhealed', hp: 999, max_hp: 50, ac: 10 }),
        makeCombatant('negative_hp', { name: 'Dying', hp: -15, max_hp: 50, ac: 10 }),
        makeCombatant('zero_hp', { name: 'Dead', hp: 0, max_hp: 50, ac: 10 }),
      ];

      fixture.detectChanges();
      const pinnedBar = fixture.nativeElement.querySelector('[data-testid="pinned-combat-bar"]');
      expect(pinnedBar).toBeTruthy();

      expect(pinnedBar.textContent).toContain('999/50');
      expect(pinnedBar.textContent).toContain('-15/50');
      expect(pinnedBar.textContent).toContain('0/50');

      // Verify setCombatantHp clamping logic
      const mob = component.combatants[0];
      component.setCombatantHp(mob, -50);
      expect(component.combatants.find(c => c.id === 'overheal')?.hp).toBe(0);

      component.setCombatantHp(mob, 9999);
      expect(component.combatants.find(c => c.id === 'overheal')?.hp).toBe(50); // clamped to max_hp

      component.setCombatantHp(mob, NaN);
      expect(component.combatants.find(c => c.id === 'overheal')?.hp).toBe(0);

      component.setCombatantHp(mob, Infinity);
      expect(component.combatants.find(c => c.id === 'overheal')?.hp).toBe(50);
    });
  });

  // ===========================================================================
  // SUITE 4: Statblock Modal Roll Resilience & Parsing Anomaly Defense
  // ===========================================================================
  describe('4. StatblockModalComponent Roll Resilience & Parser Adversarial Tests', () => {
    let fixture: ComponentFixture<StatblockModalComponent>;
    let component: StatblockModalComponent;
    let diceService: DiceService;
    let rollToast: RollToastService;

    beforeEach(async () => {
      await TestBed.configureTestingModule({
        imports: [StatblockModalComponent],
        providers: [DiceService, RollToastService],
      }).compileComponents();

      fixture = TestBed.createComponent(StatblockModalComponent);
      component = fixture.componentInstance;
      diceService = TestBed.inject(DiceService);
      rollToast = TestBed.inject(RollToastService);
    });

    afterEach(() => {
      component.open = false;
      fixture.detectChanges();
      jest.restoreAllMocks();
    });

    it('correctly handles negative attack bonuses (-3 to hit) and bonus of +0', () => {
      const negativeAction: MonsterAction = {
        name: 'Clumsy Flail',
        attack_bonus: -3,
        damage_dice: '1d6-1',
        damage_type: 'bludgeoning',
      };

      const zeroAction: MonsterAction = {
        name: 'Unskilled Bash',
        attack_bonus: 0,
        damage_dice: '1d4',
        damage_type: 'bludgeoning',
      };

      expect(component.getActionAttackBonus(negativeAction)).toBe(-3);
      expect(component.formatBonus(-3)).toBe('-3');

      // Strict check: bonus 0 must NOT be treated as falsy/null
      expect(component.getActionAttackBonus(zeroAction)).toBe(0);
      expect(component.formatBonus(0)).toBe('+0');

      // Test description regex parsing fallback
      const descNegative: MonsterAction = {
        name: 'Wild Swing',
        description: 'Melee Weapon Attack: -2 to hit, reach 5 ft.',
      };
      const descZero: MonsterAction = {
        name: 'Basic Shove',
        description: 'Melee Weapon Attack: +0 to hit, reach 5 ft.',
      };
      expect(component.getActionAttackBonus(descNegative)).toBe(-2);
      expect(component.getActionAttackBonus(descZero)).toBe(0);

      // Verify rollAttack triggers DiceService with exact values
      const rollD20Spy = jest.spyOn(diceService, 'rollD20');
      const toastSpy = jest.spyOn(rollToast, 'showRoll');
      component.combatant = makeCombatant('ogre', { name: 'Ogre' });

      component.rollAttack(negativeAction);
      expect(rollD20Spy).toHaveBeenCalledWith(-3);
      expect(toastSpy).toHaveBeenCalledWith(
        expect.objectContaining({
          title: expect.stringContaining('CLUMSY FLAIL ATTACK'),
          modifier: -3,
        })
      );

      component.rollAttack(zeroAction);
      expect(rollD20Spy).toHaveBeenCalledWith(0);
      expect(toastSpy).toHaveBeenCalledWith(
        expect.objectContaining({
          title: expect.stringContaining('UNSKILLED BASH ATTACK'),
          modifier: 0,
        })
      );
    });

    it('correctly parses and rolls bizarre damage expressions: compound, flat numbers, and 1d1', () => {
      const rollDamageSpy = jest.spyOn(diceService, 'rollDamage');
      const toastSpy = jest.spyOn(rollToast, 'showRoll');
      component.combatant = makeCombatant('hydra', { name: 'Hydra' });

      // 1. Compound description damage notation
      const compoundAction: MonsterAction = {
        name: 'Poison Bite',
        description: 'Hit: 10 (2d6 + 3) piercing damage plus 7 (2d6) poison damage.',
      };
      expect(component.getActionDamageDice(compoundAction)).toBe('2d6+3');
      expect(component.getActionDamageType(compoundAction)).toBe('piercing');

      component.rollDamage(compoundAction);
      expect(rollDamageSpy).toHaveBeenCalledWith([{ label: 'Poison Bite (piercing)', notation: '2d6+3' }]);

      // 2. Flat damage (e.g. "Hit: 5 slashing damage" or explicit damage_dice: "5")
      const flatAction: MonsterAction = {
        name: 'Constrict',
        damage_dice: '5',
        damage_type: 'bludgeoning',
      };
      expect(component.getActionDamageDice(flatAction)).toBe('5');
      component.rollDamage(flatAction);
      expect(rollDamageSpy).toHaveBeenCalledWith([{ label: 'Constrict (bludgeoning)', notation: '5' }]);
      expect(toastSpy).toHaveBeenCalledWith(
        expect.objectContaining({
          total: 5,
        })
      );

      // 3. Flat damage 0
      const zeroDamageAction: MonsterAction = {
        name: 'Grapple Strangle',
        damage_dice: '0',
      };
      expect(component.getActionDamageDice(zeroDamageAction)).toBe('0');
      component.rollDamage(zeroDamageAction);
      expect(toastSpy).toHaveBeenCalledWith(
        expect.objectContaining({
          total: 0,
        })
      );

      // 4. Exotic 1d1 notation
      const d1Action: MonsterAction = {
        name: 'Dart',
        damage_dice: '1d1',
      };
      expect(component.getActionDamageDice(d1Action)).toBe('1d1');
      component.rollDamage(d1Action);
      expect(toastSpy).toHaveBeenCalledWith(
        expect.objectContaining({
          total: 1,
        })
      );
    });

    it('gracefully handles missing damage dice with damage type and actions without attacks', () => {
      const buffAction: MonsterAction = {
        name: 'Frightful Presence',
        description: 'Each creature within 60 feet must make a DC 16 Wisdom saving throw.',
      };

      expect(component.getActionAttackBonus(buffAction)).toBeNull();
      expect(component.getActionDamageDice(buffAction)).toBeNull();
      expect(component.getActionDamageType(buffAction)).toBeNull();

      const rollD20Spy = jest.spyOn(diceService, 'rollD20');
      const rollDamageSpy = jest.spyOn(diceService, 'rollDamage');

      component.combatant = makeCombatant('dragon', { name: 'Dragon' });
      component.rollAttack(buffAction);
      component.rollDamage(buffAction);

      expect(rollD20Spy).not.toHaveBeenCalled();
      expect(rollDamageSpy).not.toHaveBeenCalled();
    });

    it('renders legacy fallback when combatant has empty arrays or no structured content', () => {
      component.open = true;
      component.combatant = makeCombatant('legacy_specter', {
        name: 'Legacy Specter',
        actions: [],
        traits: [],
        stats: undefined,
        statblock: 'Incorporeal Movement. Life Drain: +4 to hit.',
      });

      expect(component.hasStructuredContent()).toBe(false);

      fixture.detectChanges();
      const overlayText = document.body.textContent || '';
      expect(overlayText).toContain('Legacy Specter');
      expect(overlayText).toContain('Incorporeal Movement. Life Drain: +4 to hit.');
    });

    it('renders default fallback text when combatant statblock string is completely missing', () => {
      component.open = true;
      component.combatant = makeCombatant('blank', {
        name: 'Blank Specter',
        actions: [],
        traits: [],
        stats: undefined,
        statblock: undefined,
      });

      fixture.detectChanges();
      expect(document.body.textContent).toContain('Standard D&D 5e monster statblock.');
    });
  });

  // ===========================================================================
  // SUITE 5: Initiative Quick-Add Monster Search Edge Cases
  // ===========================================================================
  describe('5. InitiativePanelComponent Quick-Add Search & Edge Case Defense', () => {
    let fixture: ComponentFixture<InitiativePanelComponent>;
    let component: InitiativePanelComponent;

    beforeEach(async () => {
      await TestBed.configureTestingModule({
        imports: [InitiativePanelComponent],
      }).compileComponents();

      fixture = TestBed.createComponent(InitiativePanelComponent);
      component = fixture.componentInstance;
    });

    afterEach(() => {
      fixture.destroy();
      jest.restoreAllMocks();
    });

    it('correctly emits search query when all source filter chips are toggled off', fakeAsync(() => {
      const searchSpy = jest.spyOn(component.searchBestiary, 'emit');

      // Defaults: official = true, mine = true, community = false
      expect(component.includeOfficial).toBe(true);
      expect(component.includeMine).toBe(true);
      expect(component.includeCommunity).toBe(false);

      // Toggle official and mine OFF
      component.toggleSource('official');
      component.toggleSource('mine');
      expect(component.includeOfficial).toBe(false);
      expect(component.includeMine).toBe(false);
      expect(component.includeCommunity).toBe(false);

      component.onSearchInput('beholder');
      tick(300);

      expect(searchSpy).toHaveBeenCalledWith({
        query: 'beholder',
        includeOfficial: false,
        includeMine: false,
        includeCommunity: false,
      });
    }));

    it('debounces rapid typing and suppresses distinct consecutive duplicates', fakeAsync(() => {
      const searchSpy = jest.spyOn(component.searchBestiary, 'emit');

      // Simulate fast user typing: "g", "go", "gob", "goblin"
      component.onSearchInput('g');
      tick(100);
      component.onSearchInput('go');
      tick(100);
      component.onSearchInput('gob');
      tick(100);
      component.onSearchInput('goblin');
      tick(300); // Debounce expires

      expect(searchSpy).toHaveBeenCalledTimes(1);
      expect(searchSpy).toHaveBeenCalledWith(
        expect.objectContaining({ query: 'goblin' })
      );

      // Retyping identical query should be blocked by distinctUntilChanged
      component.onSearchInput('goblin');
      tick(300);
      expect(searchSpy).toHaveBeenCalledTimes(1);

      // Whitespace only typing should clear results and NOT emit
      component.onSearchInput('   ');
      tick(300);
      expect(searchSpy).toHaveBeenCalledTimes(1);
      expect(component.quickAddResults).toEqual([]);
    }));

    it('safely tolerates regex control characters in search input without crash', fakeAsync(() => {
      const searchSpy = jest.spyOn(component.searchBestiary, 'emit');
      const adversarialInputs = [
        '.*',
        '(?<=abc)[a-z]+',
        '[.*+?^${}()|[]\\]',
        '\\',
        '(((',
        '${7*7}',
        '<script>alert("test")</script>',
      ];

      for (const input of adversarialInputs) {
        expect(() => {
          component.onSearchInput(input);
          tick(300);
        }).not.toThrow();
      }

      expect(searchSpy).toHaveBeenCalled();
    }));
  });

  // ===========================================================================
  // SUITE 6: BestiaryService & GeneratorsPanel Edge Cases
  // ===========================================================================
  describe('6. BestiaryService & GeneratorsPanel Edge Cases', () => {
    let service: BestiaryService;
    let httpTesting: HttpTestingController;

    beforeEach(() => {
      TestBed.configureTestingModule({
        providers: [provideHttpClient(), provideHttpClientTesting(), BestiaryService],
      });
      service = TestBed.inject(BestiaryService);
      httpTesting = TestBed.inject(HttpTestingController);
    });

    afterEach(() => {
      httpTesting.verify();
    });

    it('BestiaryService correctly refines client-side CR numeric range filtering', () => {
      const monsters: BestiaryMonster[] = [
        makeMonster('m1', { cr_numeric: 0.25, name: 'CR 1/4' }),
        makeMonster('m2', { cr_numeric: 2, name: 'CR 2' }),
        makeMonster('m3', { cr_numeric: 5, name: 'CR 5' }),
        makeMonster('m4', { cr_numeric: 10, name: 'CR 10' }),
      ];

      let results: BestiaryMonster[] = [];
      service.getMonsters({ cr_min: 1, cr_max: 5 }).subscribe((res) => {
        results = res;
      });

      const req = httpTesting.expectOne((r) => r.url.endsWith('/bestiary'));
      req.flush(monsters);

      expect(results.length).toBe(2);
      expect(results.map(m => m.name)).toEqual(['CR 2', 'CR 5']);
    });

    it('BestiaryService handles HTTP errors cleanly by setting error signal', () => {
      let threw = false;
      service.getMonsters({ search: 'fail' }).subscribe({
        next: () => {},
        error: () => { threw = true; },
      });

      const req = httpTesting.expectOne((r) => r.url.endsWith('/bestiary'));
      req.flush({ detail: 'Database disconnected' }, { status: 500, statusText: 'Internal Error' });

      expect(threw).toBe(true);
      expect(service.isLoading()).toBe(false);
      expect(service.error()).toBe('Database disconnected');
    });

    it('GeneratorsPanelComponent disables encounter generation when partySize is 0 and enables when positive', () => {
      const genFixture = TestBed.createComponent(GeneratorsPanelComponent);
      const genComp = genFixture.componentInstance;

      genFixture.componentRef.setInput('partySize', 0);
      genFixture.detectChanges();

      const button: HTMLButtonElement = genFixture.nativeElement.querySelector('button');
      expect(button.disabled).toBe(true);
      expect(genFixture.nativeElement.textContent).toContain('No heroes on the roster yet');

      // Set partySize > 0 using setInput for OnPush component
      genFixture.componentRef.setInput('partySize', 4);
      genFixture.componentRef.setInput('avgLevel', 5);
      genFixture.detectChanges();
      expect(button.disabled).toBe(false);
      expect(genFixture.nativeElement.textContent).toContain('Balanced for 4 heroes at average level 5');
    });
  });
});
