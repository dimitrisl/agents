import { signal } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { provideRouter } from '@angular/router';
import { Subject, of } from 'rxjs';
import { PlayerComponent } from './player.component';
import { CharacterStateService } from '../../core/services/character-state.service';
import { DiceService } from '../../core/services/dice.service';
import { RollToastService } from '../../core/services/roll-toast.service';
import { ForgeConfirmService } from '../../shared/ui';
import { SpellRulesService } from '../../core/services/spell-rules.service';
import { analyzeSpell } from '../../core/rules';
import { WebSocketService, WsMessage } from '../../core/services/websocket.service';
import { CharacterSchema } from '../../core/models/character.model';
import { RollRequest } from '../../core/models/campaign.model';
import { ROLL_PROMPT_TIMEOUT_SECONDS } from '../../core/models/roll-prompt';

/**
 * #26: the client used to throw the dice the moment a request arrived, so the one
 * roll where advantage matters most was the one roll the player could not shape.
 * These tests are about what the player is *asked* before anything is rolled.
 *
 * The fixture is never change-detected, which keeps the constructor's `effect` —
 * and the socket connect it performs — out of the way.
 */
const HERO: CharacterSchema = {
  char_id: 'lyra1',
  char_name: 'Lyra Meadowlark',
  char_class: 'Ranger',
  char_level: 5,
  race: 'Half-Elf',
  background: 'Outlander',
  armor_class: 15,
  hp_max: 44,
  speed: 30,
  proficiency_bonus: 3,
  stats: { STR: 10, DEX: 18, CON: 14, INT: 12, WIS: 16, CHA: 8 },
  saving_throws: ['DEX'],
  skill_proficiencies: ['Perception'],
  active_campaign: 'Curse of Strahd',
};

function request(overrides: Partial<RollRequest> = {}): RollRequest {
  return {
    id: 'req-1',
    char_filename: 'lyra_lyra1.json',
    char_name: 'Lyra Meadowlark',
    roll_type: 'skill',
    stat: 'Perception',
    reason: 'Did you hear that?',
    status: 'pending',
    created_at: '2026-08-20 19:04:11',
    ...overrides,
  };
}

describe('PlayerComponent — DM roll requests', () => {
  let component: PlayerComponent;
  let http: HttpTestingController;
  let messages$: Subject<WsMessage>;
  let opened$: Subject<string>;

  beforeEach(() => {
    jest.useFakeTimers();
    messages$ = new Subject<WsMessage>();
    opened$ = new Subject<string>();

    const wsStub: Partial<WebSocketService> = {
      messages$,
      opened$,
      connect: () => undefined,
      disconnect: () => undefined,
      sendMessage: () => true,
    };

    TestBed.configureTestingModule({
      imports: [PlayerComponent],
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        provideRouter([]),
        { provide: WebSocketService, useValue: wsStub },
      ],
    });

    http = TestBed.inject(HttpTestingController);
    TestBed.inject(CharacterStateService).activeCharacter.set({ ...HERO });
    component = TestBed.createComponent(PlayerComponent).componentInstance;
  });

  afterEach(() => {
    jest.useRealTimers();
    http.verify();
  });

  /** Delivers a roll request down the socket, the way the DM's screen sends one. */
  function sendRequest(req: RollRequest): void {
    component.ngOnInit();
    // `ngOnInit` loads the vault; that fetch is not what these tests are about.
    http.expectOne((r) => r.url.endsWith('/characters')).flush({ characters: [HERO], unreadable: [] });
    messages$.next({ type: 'roll_request', payload: req } as WsMessage);
  }

  describe('the prompt', () => {
    it('asks instead of rolling', () => {
      sendRequest(request());

      expect(component.activeRollPrompt?.id).toBe('req-1');
      // The regression this guards: no result may reach the DM until the player
      // has said how they want to roll.
      http.expectNone((r) => r.url.includes('/roll-request/'));
    });

    it('reads the modifier off the sheet', () => {
      sendRequest(request());

      // WIS 16 (+3) with Perception proficiency (+3).
      expect(component.activeRollPromptModifier).toBe(6);
      expect(component.activeRollPromptLabel).toBe('Perception check');
    });

    it('opens every prompt on a clean slate', () => {
      // Advantage chosen for the sheet's own buttons says nothing about what the
      // DM is asking for now.
      component.rollMode = 'advantage';

      sendRequest(request());

      expect(component.promptRollMode).toBe('normal');
      expect(component.promptSituationalBonus).toBe(0);
    });
  });

  describe('answering', () => {
    it('sends the mode and the situational bonus the player picked', () => {
      sendRequest(request());
      jest.spyOn(TestBed.inject(DiceService), 'rollDie').mockReturnValue(11);

      component.promptRollMode = 'advantage';
      component.promptSituationalBonus = 2;
      component.confirmRollPrompt();

      const posted = http.expectOne((r) => r.url.includes('/roll-request/req-1/result'));
      expect(posted.request.body).toMatchObject({
        mode: 'advantage',
        situational_bonus: 2,
        // 11 on both d20s, +6 from the sheet, +2 by hand.
        total: 19,
        modifier: 8,
      });
      posted.flush({ success: true });

      expect(component.activeRollPrompt).toBeNull();
    });

    it('throws two d20s when the player takes advantage', () => {
      sendRequest(request());
      const rollDie = jest.spyOn(TestBed.inject(DiceService), 'rollDie');
      rollDie.mockReturnValueOnce(4).mockReturnValueOnce(17);

      component.promptRollMode = 'advantage';
      component.confirmRollPrompt();

      const posted = http.expectOne((r) => r.url.includes('/roll-request/req-1/result'));
      expect(posted.request.body).toMatchObject({ rolls: [4, 17], raw: 17, total: 23 });
      posted.flush({ success: true });
    });

    it('never answers the same request twice', () => {
      sendRequest(request());
      component.confirmRollPrompt();
      http.expectOne((r) => r.url.includes('/roll-request/req-1/result')).flush({ success: true });

      // The socket echoes the request back on a reconnect.
      messages$.next({ type: 'roll_request', payload: request() } as WsMessage);

      expect(component.activeRollPrompt).toBeNull();
      http.expectNone((r) => r.url.includes('/roll-request/'));
    });
  });

  describe('the queue', () => {
    it('asks one at a time rather than stacking prompts', () => {
      sendRequest(request());
      messages$.next({ type: 'roll_request', payload: request({ id: 'req-2', stat: 'Stealth' }) } as WsMessage);

      expect(component.activeRollPrompt?.id).toBe('req-1');
      expect(component.queuedRollPromptCount).toBe(1);
    });

    it('opens the next one as soon as the first is answered', () => {
      sendRequest(request());
      messages$.next({ type: 'roll_request', payload: request({ id: 'req-2', stat: 'Stealth' }) } as WsMessage);

      component.confirmRollPrompt();
      http.expectOne((r) => r.url.includes('/roll-request/req-1/result')).flush({ success: true });

      expect(component.activeRollPrompt?.id).toBe('req-2');
      expect(component.queuedRollPromptCount).toBe(0);
    });
  });

  describe('catching up after being offline', () => {
    /**
     * The bug the ticket calls out by name: `mergeRollRequestFromHistory` used to
     * roll every request the player missed, silently, the instant the socket came
     * back — several rolls at once, none of them the player's choice.
     */
    it('queues what was missed instead of rolling it', () => {
      component.ngOnInit();
      http.expectOne((r) => r.url.endsWith('/characters')).flush({ characters: [HERO], unreadable: [] });

      opened$.next('Curse of Strahd');
      http.expectOne((r) => r.url.includes('/encounter')).flush({ is_active: false });
      http.expectOne((r) => r.url.includes('/messages')).flush({
        campaign_name: 'Curse of Strahd',
        whispers: [],
        roll_requests: [
          request({ id: 'old-1' }),
          request({ id: 'old-2', stat: 'Stealth' }),
        ],
      });

      expect(component.activeRollPrompt?.id).toBe('old-1');
      expect(component.queuedRollPromptCount).toBe(1);
      http.expectNone((r) => r.url.includes('/roll-request/'));
    });

    it('does not re-ask a request that was already answered', () => {
      component.ngOnInit();
      http.expectOne((r) => r.url.endsWith('/characters')).flush({ characters: [HERO], unreadable: [] });

      opened$.next('Curse of Strahd');
      http.expectOne((r) => r.url.includes('/encounter')).flush({ is_active: false });
      http.expectOne((r) => r.url.includes('/messages')).flush({
        campaign_name: 'Curse of Strahd',
        whispers: [],
        roll_requests: [
          request({
            id: 'old-1',
            status: 'resolved',
            result: { total: 18, expression: '1d20 (12) +6', raw: 12, rolls: [12], modifier: 6 },
          }),
        ],
      });

      expect(component.activeRollPrompt).toBeNull();
    });
  });

  describe('no answer', () => {
    it('reports the roll as missed once the clock runs out', () => {
      sendRequest(request());

      jest.advanceTimersByTime(ROLL_PROMPT_TIMEOUT_SECONDS * 1000);

      expect(component.activeRollPrompt).toBeNull();
      const missed = http.expectOne((r) => r.url.includes('/roll-request/req-1/miss'));
      missed.flush({ success: true });
      http.expectNone((r) => r.url.includes('/result'));
    });

    it('lets the player roll it from the inbox afterwards', () => {
      sendRequest(request());
      jest.advanceTimersByTime(ROLL_PROMPT_TIMEOUT_SECONDS * 1000);
      http.expectOne((r) => r.url.includes('/miss')).flush({ success: true });

      // A slip is not a locked door: the inbox entry still opens the prompt.
      const missedRequest = component.rollRequestHistory[0];
      expect(missedRequest.status).toBe('missed');

      component.openRollPrompt(missedRequest);
      expect(component.activeRollPrompt?.id).toBe('req-1');

      component.confirmRollPrompt();
      http.expectOne((r) => r.url.includes('/roll-request/req-1/result')).flush({ success: true });
    });

    it('skipping deliberately reports the same thing', () => {
      sendRequest(request());

      component.dismissRollPrompt();

      expect(component.activeRollPrompt).toBeNull();
      http.expectOne((r) => r.url.includes('/roll-request/req-1/miss')).flush({ success: true });
    });

    /**
     * `forge-modal` emits `openChange(false)` when a prompt is closed programmatically
     * too. Without a guard, confirming a roll would mark the request it just
     * answered as missed a tick later.
     */
    it('does not mark an answered request as missed when the dialog closes', () => {
      sendRequest(request());

      component.confirmRollPrompt();
      http.expectOne((r) => r.url.includes('/roll-request/req-1/result')).flush({ success: true });

      component.onRollPromptOpenChange(false);

      http.expectNone((r) => r.url.includes('/miss'));
    });
  });

  describe('party_update and Warlock short rest', () => {
    it('replaces activeCharacter with a new object reference on party_update for OnPush children', () => {
      component.ngOnInit();
      http.expectOne((r) => r.url.endsWith('/characters')).flush({ characters: [HERO], unreadable: [] });

      const charState = TestBed.inject(CharacterStateService);
      const beforeRef = charState.activeCharacter();

      messages$.next({
        type: 'party_update',
        payload: { char_id: 'lyra1', hp_current: 19, conditions: ['Blessed'], version: 4 },
      } as WsMessage);

      const afterRef = charState.activeCharacter();
      expect(afterRef).not.toBe(beforeRef);
      expect(afterRef?.hp_current).toBe(19);
      expect(afterRef?.conditions).toEqual(['Blessed']);
      expect(afterRef?.version).toBe(4);
    });

    it('restores Warlock Pact Magic slots on a 0-dice short rest without rolling hit dice', () => {
      const charState = TestBed.inject(CharacterStateService);
      charState.activeCharacter.set({
        ...HERO,
        active_campaign: undefined,
        char_class: 'Warlock',
        char_level: 3,
        hit_dice_used: 3,
        spell_slots: { level_2: { max: 2, used: 2 } },
      });

      const rollDieSpy = jest.spyOn(TestBed.inject(DiceService), 'rollDie');
      component.shortRestDiceToSpend = 0;
      component.executeShortRest();

      const putReq = http.expectOne((r) => r.method === 'PUT' && r.url.includes('/characters/'));
      putReq.flush(putReq.request.body);

      expect(rollDieSpy).not.toHaveBeenCalled();
      expect(charState.activeCharacter()?.spell_slots?.['level_2'].used).toBe(0);
    });
  });

  describe('Character Import & Whisper Reporting (#151, #153, #155)', () => {
    it('opens import modal and handles D&D Beyond import flow', () => {
      component.openImportModal();
      expect(component.showImportModal()).toBe(true);

      component.onImportDndBeyond('https://www.dndbeyond.com/characters/99999999');

      expect(component.isImporting()).toBe(true);
      const req = http.expectOne((r) => r.method === 'POST' && r.url.endsWith('/characters/import-dndbeyond'));
      expect(req.request.body).toEqual({ url_or_id: 'https://www.dndbeyond.com/characters/99999999' });

      req.flush({
        ...HERO,
        char_id: 'imported_ddb_hero',
        char_name: 'DDB Hero',
        warnings: [],
      });

      // CharacterStateService loadCharacters
      const loadReq = http.expectOne((r) => r.url.endsWith('/characters'));
      loadReq.flush({ characters: [{ ...HERO, char_id: 'imported_ddb_hero', char_name: 'DDB Hero' }], unreadable: [] });

      expect(component.isImporting()).toBe(false);
      expect(component.showImportModal()).toBe(false);
      const charState = TestBed.inject(CharacterStateService);
      expect(charState.activeCharacter()?.char_name).toBe('DDB Hero');
    });

    it('submits whisper moderation report to campaign endpoint', async () => {
      const charState = TestBed.inject(CharacterStateService);
      charState.activeCharacter.set({
        ...HERO,
        active_campaign: 'CurseOfStrahd',
      });

      const confirmDialog = TestBed.inject(ForgeConfirmService);
      jest.spyOn(confirmDialog, 'askPrompt').mockResolvedValue('Harassment in secret whisper');

      const whisper: Whisper = {
        id: 'whisp-123',
        sender: 'DM',
        recipient: 'Lyra',
        message: 'Toxic content',
        timestamp: '12:00',
        has_open_report: false,
      };
      component.whisperHistory = [whisper];

      await component.reportWhisper(whisper);

      const req = http.expectOne((r) =>
        r.method === 'POST' && r.url.endsWith('/campaigns/CurseOfStrahd/whispers/whisp-123/report')
      );
      expect(req.request.body).toEqual({ reason: 'Harassment in secret whisper' });
      req.flush({ success: true, message: 'Report submitted.' });

      expect(component.whisperHistory[0].has_open_report).toBe(true);
    });
  });

  describe('Mobile Player Companion Fixes (#170-#175)', () => {
    it('triggers concentration check even when damage is fully absorbed by Temp HP', () => {
      const charState = TestBed.inject(CharacterStateService);
      charState.activeCharacter.set({
        ...HERO,
        hp_current: 20,
        hp_max: 20,
        hp_temp: 15,
        concentrating_on: 'Bless',
      });

      component.applyDamage(10);

      expect(charState.activeCharacter()?.hp_temp).toBe(5);
      expect(charState.activeCharacter()?.hp_current).toBe(20);
      expect(component.showConcentrationPrompt()).toBe(true);
      expect(component.concentrationDc()).toBe(10);
    });

    it('uses CON saving throw bonus (including proficiency) and rollMode in rollConcentrationSave', () => {
      const charState = TestBed.inject(CharacterStateService);
      const dice = TestBed.inject(DiceService);
      const rollSpy = jest.spyOn(dice, 'rollD20').mockReturnValue({
        total: 18,
        raw: 13,
        rolls: [13, 8],
        sides: 20,
        modifier: 5,
        expression: '1d20+5 (ADVANTAGE)',
        mode: 'advantage',
      });

      charState.activeCharacter.set({
        ...HERO,
        stats: { ...HERO.stats, CON: 16 }, // +3 mod
        saving_throws: ['CON'], // +2 prof = +5 total
        proficiency_bonus: 2,
        concentrating_on: 'Haste',
      });
      component.rollMode = 'advantage';
      component.concentrationDc.set(15);
      component.showConcentrationPrompt.set(true);

      component.rollConcentrationSave();

      expect(rollSpy).toHaveBeenCalledWith(5, 'advantage');
      expect(component.showConcentrationPrompt()).toBe(false);

      const rollReq = http.expectOne(
        (r) => r.method === 'POST' && r.url.endsWith('/campaigns/Curse%20of%20Strahd/rolls')
      );
      expect(rollReq.request.body.roll_type).toBe('concentration');
      expect(rollReq.request.body.visibility).toBe('public');
      rollReq.flush({ roll: { id: 'r-conc', ...rollReq.request.body, campaign_name: 'Curse of Strahd', sender_user_id: 'u1', created_at: '2026-11-12T10:00:00Z' } });
    });

    it('removes one condition or ends concentration from the chip ✕, leaving the rest', () => {
      const charState = TestBed.inject(CharacterStateService);
      charState.activeCharacter.set({
        ...HERO,
        conditions: ['Paralyzed', 'Stunned'],
        concentrating_on: 'Haste',
      });

      component.removeCondition('Paralyzed');
      expect(charState.activeCharacter()!.conditions).toEqual(['Stunned']);
      expect(charState.activeCharacter()!.concentrating_on).toBe('Haste');

      component.endConcentration();
      expect(charState.activeCharacter()!.concentrating_on).toBe('');
      expect(charState.activeCharacter()!.conditions).toEqual(['Stunned']);
    });

    it('casting Fireball at 4th level rolls 9d6 with a "passed the save" button', () => {
      const charState = TestBed.inject(CharacterStateService);
      charState.activeCharacter.set({ ...HERO, char_level: 8, spell_save_dc: 15 });
      jest.spyOn(TestBed.inject(SpellRulesService), 'profile').mockReturnValue(
        of(
          analyzeSpell({
            name: 'Fireball',
            level: 3,
            duration: 'Instantaneous',
            description:
              'Each creature must make a Dexterity saving throw. A target takes 8d6 fire damage on a failed save, or half as much damage on a successful one.',
            higherLevelSlot: 'the damage increases by 1d6 for each slot level above 3rd.',
          })
        )
      );

      component.onCastSpell({ spellName: 'Fireball', level: 4, isRitual: false });

      const shown = TestBed.inject(RollToastService).activeRoll()!;
      expect(shown.title).toContain('FIREBALL · LEVEL 4');
      expect(shown.rolls?.length).toBe(9);
      expect(shown.damageParts?.[0]).toEqual(
        expect.objectContaining({ label: 'Fireball · fire', saveHalf: { dc: 'DC 15 DEX' } })
      );

      const rollReq = http.expectOne(
        (r) => r.method === 'POST' && r.url.endsWith('/campaigns/Curse%20of%20Strahd/rolls')
      );
      expect(rollReq.request.body.roll_type).toBe('spell');
      rollReq.flush({ roll: { id: 'r-fb', ...rollReq.request.body, campaign_name: 'Curse of Strahd', sender_user_id: 'u1', created_at: '2026-11-12T10:01:00Z' } });
    });

    it('a spell attack that rolls a natural 20 crits and doubles its damage dice', () => {
      const charState = TestBed.inject(CharacterStateService);
      charState.activeCharacter.set({ ...HERO, char_level: 8, spell_attack_bonus: '+7' });
      jest.spyOn(TestBed.inject(SpellRulesService), 'profile').mockReturnValue(
        of(
          analyzeSpell({
            name: 'Fire Bolt',
            level: 0,
            duration: 'Instantaneous',
            description: 'Make a ranged spell attack against the target. On a hit, the target takes 1d10 fire damage.',
          })
        )
      );
      const dice = TestBed.inject(DiceService);
      jest.spyOn(dice, 'rollD20').mockReturnValue({
        expression: '1d20+7', numDice: 1, sides: 20, modifier: 7, rolls: [20], raw: 20, total: 27, mode: 'normal',
      } as any);

      component.onCastSpell({ spellName: 'Fire Bolt', level: 0, isRitual: false });

      const shown = TestBed.inject(RollToastService).activeRoll()!;
      expect(shown.title).toContain('NAT 20');
      expect(shown.isCritHit).toBe(true);
      expect(shown.rolls?.length).toBe(4); // 2d10 at level 8, doubled

      const rollReq = http.expectOne(
        (r) => r.method === 'POST' && r.url.endsWith('/campaigns/Curse%20of%20Strahd/rolls')
      );
      expect(rollReq.request.body.is_crit).toBe(true);
      rollReq.flush({ roll: { id: 'r-bolt', ...rollReq.request.body, campaign_name: 'Curse of Strahd', sender_user_id: 'u1', created_at: '2026-11-12T10:02:00Z' } });
    });

    it('a save spell never crits', () => {
      const charState = TestBed.inject(CharacterStateService);
      charState.activeCharacter.set({ ...HERO, char_level: 8, spell_save_dc: 15 });
      jest.spyOn(TestBed.inject(SpellRulesService), 'profile').mockReturnValue(
        of(
          analyzeSpell({
            name: 'Shatter',
            level: 2,
            duration: 'Instantaneous',
            description: 'Each creature must make a Constitution saving throw. A creature takes 3d8 thunder damage on a failed save, or half as much damage on a successful one.',
          })
        )
      );
      component.onCastSpell({ spellName: 'Shatter', level: 2, isRitual: false });
      const shown = TestBed.inject(RollToastService).activeRoll()!;
      expect(shown.isCritHit).toBe(false);
      expect(shown.rolls?.length).toBe(3);

      const rollReq = http.expectOne(
        (r) => r.method === 'POST' && r.url.endsWith('/campaigns/Curse%20of%20Strahd/rolls')
      );
      expect(rollReq.request.body.is_crit).toBe(false);
      rollReq.flush({ roll: { id: 'r-shatter', ...rollReq.request.body, campaign_name: 'Curse of Strahd', sender_user_id: 'u1', created_at: '2026-11-12T10:03:00Z' } });
    });

    it('casting Haste puts it on Status and ends the previous concentration', () => {
      const charState = TestBed.inject(CharacterStateService);
      charState.activeCharacter.set({ ...HERO, concentrating_on: 'Bless', conditions: ['Prone'] });
      jest.spyOn(TestBed.inject(SpellRulesService), 'profile').mockReturnValue(
        of(
          analyzeSpell({
            name: 'Haste',
            level: 3,
            concentration: 'True',
            duration: 'Concentration, up to 1 minute',
            description: 'Choose a willing creature that you can see within range. Until the spell ends, the speed of the target is doubled.',
          })
        )
      );

      component.onCastSpell({ spellName: 'Haste', level: 3, isRitual: false });

      expect(charState.activeCharacter()!.concentrating_on).toBe('Haste');
      expect(charState.activeCharacter()!.conditions).toEqual(['Prone']);
      expect(TestBed.inject(RollToastService).activeRoll()?.message).toContain('Bless ended');
    });

    it('a spell without concentration leaves the current one alone', () => {
      const charState = TestBed.inject(CharacterStateService);
      charState.activeCharacter.set({ ...HERO, char_level: 8, concentrating_on: 'Haste' });
      jest.spyOn(TestBed.inject(SpellRulesService), 'profile').mockReturnValue(
        of(
          analyzeSpell({
            name: 'Fireball',
            level: 3,
            concentration: 'False',
            duration: 'Instantaneous',
            description: 'Each creature must make a Dexterity saving throw. A target takes 8d6 fire damage on a failed save, or half as much damage on a successful one.',
          })
        )
      );
      component.onCastSpell({ spellName: 'Fireball', level: 3, isRitual: false });
      expect(charState.activeCharacter()!.concentrating_on).toBe('Haste');

      const rollReq = http.expectOne(
        (r) => r.method === 'POST' && r.url.endsWith('/campaigns/Curse%20of%20Strahd/rolls')
      );
      rollReq.flush({ roll: { id: 'r-fb2', ...rollReq.request.body, campaign_name: 'Curse of Strahd', sender_user_id: 'u1', created_at: '2026-11-12T10:04:00Z' } });
    });

    it('casting a concentration spell saves slot and concentration together, without the chip flickering', () => {
      const charState = TestBed.inject(CharacterStateService);
      charState.activeCharacter.set({
        ...HERO,
        char_level: 8,
        spell_save_dc: 15,
        concentrating_on: undefined,
        spell_slots: { level_4: { max: 2, used: 0 } },
      });
      jest.spyOn(TestBed.inject(SpellRulesService), 'profile').mockReturnValue(
        of(
          analyzeSpell({
            name: 'Wall of Fire',
            level: 4,
            concentration: 'True',
            duration: 'Concentration, up to 1 minute',
            description:
              'Each creature within its area must make a Dexterity saving throw. On a failed save, a creature takes 5d8 fire damage, or half as much damage on a successful save.',
          })
        )
      );

      // What the Cast button sends: spend the slot, then cast
      component.useSpellSlot(4);
      component.onCastSpell({ spellName: 'Wall of Fire', level: 4, isRitual: false });

      const rollReq = http.expectOne(
        (r) => r.method === 'POST' && r.url.endsWith('/campaigns/Curse%20of%20Strahd/rolls')
      );
      rollReq.flush({ roll: { id: 'r-wof', ...rollReq.request.body, campaign_name: 'Curse of Strahd', sender_user_id: 'u1', created_at: '2026-11-12T10:05:00Z' } });

      // Nothing is sent straight away: no early save that could answer with the pre-cast sheet
      http.expectNone((r) => r.method === 'PUT');
      expect(charState.activeCharacter()!.concentrating_on).toBe('Wall of Fire');

      jest.advanceTimersByTime(1000); // the sheet's save debounce
      const put = http.expectOne((r) => r.method === 'PUT' && r.url.includes('/characters/'));
      expect(put.request.body.concentrating_on).toBe('Wall of Fire');
      expect(put.request.body.spell_slots.level_4.used).toBe(1);
      put.flush({ ...put.request.body, version: (put.request.body.version ?? 0) + 1 });

      expect(charState.activeCharacter()!.concentrating_on).toBe('Wall of Fire');
    });

    it('a spell with nothing to roll on casting just reports the cast', () => {
      const charState = TestBed.inject(CharacterStateService);
      charState.activeCharacter.set({ ...HERO });
      jest.spyOn(TestBed.inject(SpellRulesService), 'profile').mockReturnValue(of(null));

      component.onCastSpell({ spellName: 'Misty Step', level: 2, isRitual: false });
      expect(TestBed.inject(RollToastService).activeRoll()?.message).toContain('Misty Step (Level 2)');
    });

    it('updates HP and equipment immutably in a single save on onConsumePotion', () => {
      const charState = TestBed.inject(CharacterStateService);
      const potion = { name: 'Potion of Healing', quantity: 2, equipped: false };
      charState.activeCharacter.set({
        ...HERO,
        hp_current: 10,
        hp_max: 30,
        equipment: [potion],
      });

      component.onConsumePotion({
        item: potion,
        dice: '2d4',
        bonus: 2,
        name: 'Potion of Healing',
      });

      const putReq = http.expectOne((r) => r.method === 'PUT' && r.url.includes('/characters/'));
      putReq.flush(putReq.request.body);

      const rollReq = http.expectOne(
        (r) => r.method === 'POST' && r.url.endsWith('/campaigns/Curse%20of%20Strahd/rolls')
      );
      expect(rollReq.request.body.roll_type).toBe('healing');
      rollReq.flush({ roll: { id: 'r-pot', ...rollReq.request.body, campaign_name: 'Curse of Strahd', sender_user_id: 'u1', created_at: '2026-11-12T10:06:00Z' } });

      const updated = charState.activeCharacter();
      expect(updated?.hp_current).toBeGreaterThan(10);
      expect(updated?.equipment?.[0]?.quantity).toBe(1);

      // Drinking opens the 3D dice tray like any other roll, with the potion's dice.
      const shown = TestBed.inject(RollToastService).activeRoll();
      expect(shown?.sides).toBe(4);
      expect(shown?.rolls?.length).toBe(2);
      expect(shown?.modifier).toBe(2);
      expect(shown?.total).toBe((updated?.hp_current ?? 0) - 10);
    });

    it('broadcasts custom roll to campaign roll log endpoint when broadcast is true (#197)', () => {
      const charState = TestBed.inject(CharacterStateService);
      charState.activeCharacter.set({
        ...HERO,
        active_campaign: 'DragonHeist',
      });

      component.onCustomRoll({
        title: '🎲 1d20',
        expression: '1d20+3',
        total: 17,
        rolls: [14],
        modifier: 3,
        broadcast: true,
      });

      const req = http.expectOne(
        (r) => r.method === 'POST' && r.url.endsWith('/campaigns/DragonHeist/rolls')
      );
      expect(req.request.body.char_name).toBe(HERO.char_name);
      expect(req.request.body.roll_type).toBe('custom');
      expect(req.request.body.formula).toBe('1d20+3');
      expect(req.request.body.total).toBe(17);
      expect(req.request.body.visibility).toBe('public');
      req.flush({
        roll: {
          id: 'roll-99',
          campaign_name: 'DragonHeist',
          sender_user_id: 'user-1',
          char_name: HERO.char_name,
          roll_label: '🎲 1d20',
          roll_type: 'custom',
          formula: '1d20+3',
          natural_roll: 14,
          rolls: [14],
          modifier: 3,
          total: 17,
          mode: 'normal',
          is_crit: false,
          is_fumble: false,
          visibility: 'public',
          created_at: '2026-11-12T12:00:00Z',
        },
      });
      expect(component.inboxFeed.some((e) => e.kind === 'campaign_roll' && e.roll.id === 'roll-99')).toBe(true);
    });

    it('respects Whisper DM visibility toggle and sends sheet rolls privately to DM (#197)', () => {
      component.setRollVisibility('dm');
      component.rollAbilityCheck('DEX');

      const req = http.expectOne(
        (r) => r.method === 'POST' && r.url.endsWith('/campaigns/Curse%20of%20Strahd/rolls')
      );
      expect(req.request.body.roll_type).toBe('ability');
      expect(req.request.body.visibility).toBe('dm');
      req.flush({
        roll: {
          id: 'roll-dm-1',
          campaign_name: 'Curse of Strahd',
          sender_user_id: 'user-1',
          char_name: HERO.char_name,
          roll_label: req.request.body.roll_label,
          roll_type: 'ability',
          formula: req.request.body.formula,
          rolls: req.request.body.rolls,
          modifier: req.request.body.modifier,
          total: req.request.body.total,
          mode: 'normal',
          is_crit: false,
          is_fumble: false,
          visibility: 'dm',
          created_at: '2026-11-12T12:05:00Z',
        },
      });
      expect(
        component.inboxFeed.some(
          (entry) => entry.kind === 'campaign_roll' && entry.roll.id === 'roll-dm-1' && entry.roll.visibility === 'dm'
        )
      ).toBe(true);
    });

    it('appends and deduplicates incoming campaign_roll WebSocket events (#197)', () => {
      component.ngOnInit();
      http.expectOne((r) => r.url.endsWith('/characters')).flush({ characters: [HERO], unreadable: [] });

      const wsRoll = {
        id: 'ws-roll-1',
        campaign_name: 'Curse of Strahd',
        sender_user_id: 'user-2',
        char_name: 'Borin',
        roll_label: '🎲 STEALTH CHECK',
        roll_type: 'skill',
        formula: '1d20+5',
        natural_roll: 16,
        rolls: [16],
        modifier: 5,
        total: 21,
        mode: 'normal',
        is_crit: false,
        is_fumble: false,
        visibility: 'public',
        created_at: '2026-11-12T12:10:00Z',
      };

      messages$.next({ type: 'campaign_roll', payload: wsRoll } as WsMessage);
      messages$.next({ type: 'campaign_roll', payload: wsRoll } as WsMessage);

      const matches = component.inboxFeed.filter(
        (entry) => entry.kind === 'campaign_roll' && entry.roll.id === 'ws-roll-1'
      );
      expect(matches.length).toBe(1);
    });

    it('loads campaign roll_logs alongside whispers and roll_requests on reconnect (#197)', () => {
      component.ngOnInit();
      http.expectOne((r) => r.url.endsWith('/characters')).flush({ characters: [HERO], unreadable: [] });

      opened$.next('Curse of Strahd');
      http.expectOne((r) => r.url.includes('/encounter')).flush(null);
      const msgReq = http.expectOne((r) => r.url.endsWith('/campaigns/Curse%20of%20Strahd/messages'));
      msgReq.flush({
        campaign_name: 'Curse of Strahd',
        whispers: [],
        roll_requests: [],
        roll_logs: [
          {
            id: 'hist-roll-1',
            campaign_name: 'Curse of Strahd',
            sender_user_id: 'user-1',
            char_name: HERO.char_name,
            roll_label: '⚔️ LONGSWORD ATTACK',
            roll_type: 'attack',
            formula: '1d20+6',
            natural_roll: 18,
            rolls: [18],
            modifier: 6,
            total: 24,
            mode: 'normal',
            is_crit: false,
            is_fumble: false,
            visibility: 'public',
            created_at: '2026-11-12T09:00:00Z',
          },
        ],
      });

      expect(
        component.inboxFeed.some((e) => e.kind === 'campaign_roll' && e.roll.id === 'hist-roll-1')
      ).toBe(true);
    });

    it('forwards Quick Dice advantage metadata and surfaces non-blocking warning on HTTP sync failure (#197)', () => {
      component.onCustomRoll({
        title: '🎲 Quick d20 (ADVANTAGE)',
        expression: '1d20+4 (ADVANTAGE)',
        total: 24,
        rolls: [7, 20],
        modifier: 4,
        broadcast: true,
        mode: 'advantage',
        naturalRoll: 20,
        isCrit: true,
        isFumble: false,
      });

      const advReq = http.expectOne(
        (r) => r.method === 'POST' && r.url.endsWith('/campaigns/Curse%20of%20Strahd/rolls')
      );
      expect(advReq.request.body.mode).toBe('advantage');
      expect(advReq.request.body.natural_roll).toBe(20);
      expect(advReq.request.body.is_crit).toBe(true);
      advReq.flush('error', { status: 429, statusText: 'Too Many Requests' });

      expect(component.rollSyncWarning()).toContain('failed to sync');
      component.dismissRollSyncWarning();
      expect(component.rollSyncWarning()).toBeNull();
    });

    it('collapses hero management header in companion mode and toggles mobile actions drawer (#209)', () => {
      component.companionModeOverride.set(true);
      expect(component.isCompanionMode()).toBe(true);
      expect(component.showMobileHeaderActions()).toBe(false);

      component.showMobileHeaderActions.set(true);
      expect(component.showMobileHeaderActions()).toBe(true);

      component.showMobileHeaderActions.set(false);
      expect(component.showMobileHeaderActions()).toBe(false);
    });

    it('switches to table tab in companion mode and manages whisper reply state (#211)', () => {
      component.companionModeOverride.set(true);
      component.selectMobileTab('table');
      expect(component.mobileActiveTab()).toBe('table');

      component.whisperReply = 'Secret message';
      expect(component.whisperReply).toBe('Secret message');
    });

    it('rolls initiative and broadcasts result via WebSocket', () => {
      let sentWsMessage: any = null;
      jest.spyOn((component as any).wsService, 'sendMessage').mockImplementation((msg: any) => {
        sentWsMessage = msg;
      });

      const roll = component.rollInitiative();
      expect(roll).toBeDefined();
      expect(roll?.modifier).toBe(4); // DEX 18 (+4)
      expect(sentWsMessage).not.toBeNull();
      expect(sentWsMessage.type).toBe('roll_result');
      expect(sentWsMessage.payload.roll_type).toBe('initiative');
      expect(sentWsMessage.payload.result.total).toBe(roll!.total);
    });

    it('allows combat action for healthy hero even if hp_current is undefined (DEF-CR-01)', () => {
      const charState = TestBed.inject(CharacterStateService);
      const toastService = TestBed.inject(RollToastService);
      charState.activeCharacter.set({
        ...HERO,
        hp_max: 30,
        hp_current: undefined,
        conditions: [],
      });

      component.onCombatAction('Dodge');
      expect(toastService.activeRoll()?.title).toBe('⚔️ ACTION: DODGE');
    });

    it('blocks combat action when hero is incapacitated or at 0 HP', () => {
      const charState = TestBed.inject(CharacterStateService);
      const toastService = TestBed.inject(RollToastService);
      charState.activeCharacter.set({
        ...HERO,
        hp_max: 30,
        hp_current: 0,
        conditions: [],
      });

      component.onCombatAction('Dash');
      expect(toastService.activeRoll()?.title).toBe('⚠️ INCAPACITATED');

      charState.activeCharacter.set({
        ...HERO,
        hp_max: 30,
        hp_current: 25,
        conditions: ['Unconscious'],
      });

      component.onCombatAction('Disengage');
      expect(toastService.activeRoll()?.title).toBe('⚠️ INCAPACITATED');
    });

    it('includes char_id in POST /rolls and isolates homonym whispers/requests by char_id', () => {
      const charState = TestBed.inject(CharacterStateService);
      const toastService = TestBed.inject(RollToastService);

      const altHero: CharacterSchema = {
        ...HERO,
        char_id: 'lyra2',
        char_name: 'Lyra Meadowlark',
      };
      component.ngOnInit();
      http.expectOne((r) => r.url.endsWith('/characters')).flush({ characters: [HERO, altHero], unreadable: [] });
      charState.activeCharacter.set(HERO);

      component.onCustomRoll({
        title: '🎲 Quick d20',
        expression: '1d20+2',
        total: 14,
        rolls: [12],
        modifier: 2,
        broadcast: true,
      });

      const rollReq = http.expectOne(
        (r) => r.method === 'POST' && r.url.endsWith('/campaigns/Curse%20of%20Strahd/rolls')
      );
      expect(rollReq.request.body.char_id).toBe('lyra1');
      expect(rollReq.request.body.char_name).toBe('Lyra Meadowlark');
      rollReq.flush({ success: true, roll: { id: 'r-id', ...rollReq.request.body, campaign_name: 'Curse of Strahd', sender_user_id: 'u1', created_at: '2026-11-13T00:00:00Z' } });

      // Incoming WS whisper for player's 2nd character (with identical char_name)
      messages$.next({
        type: 'whisper',
        payload: {
          id: 'w-alt',
          sender: 'DM',
          recipient: 'Lyra Meadowlark',
          recipient_character_id: 'lyra2',
          recipient_character_name: 'Lyra Meadowlark',
          message: 'Hidden clue for alt hero',
          timestamp: '2026-11-13 00:01:00',
        },
      } as any);

      // Must NOT pollute lyra1's feed, and must surface toast pointing to lyra2
      expect(component.whisperHistory.length).toBe(0);
      expect(toastService.activeRoll()?.title).toBe('💬 WHISPER → Lyra Meadowlark');

      // Incoming WS roll_request targeting altHero (lyra2) via target_char_id must toast, not prompt lyra1
      messages$.next({
        type: 'roll_request',
        payload: {
          id: 'req-alt',
          char_filename: 'lyra_meadowlark_lyra2.json',
          char_name: 'Lyra Meadowlark',
          target_char_id: 'lyra2',
          roll_type: 'saving_throw',
          stat: 'WIS',
          reason: 'Illusion',
          status: 'pending',
        },
      } as any);

      expect(component.activeRollPrompt).toBeNull();
      expect(toastService.activeRoll()?.title).toBe('🎲 ROLL REQUEST → Lyra Meadowlark');
    });
  });
});

describe('PlayerComponent — WebSocket stability (#235)', () => {
  it('does not reconnect WebSocket when HP or version updates for the same active hero and campaign', () => {
    jest.useFakeTimers();
    const messages$ = new Subject<WsMessage>();
    const opened$ = new Subject<string>();
    const connect = jest.fn();
    const disconnect = jest.fn();

    TestBed.configureTestingModule({
      imports: [PlayerComponent],
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        provideRouter([]),
        {
          provide: WebSocketService,
          useValue: {
            messages$,
            opened$,
            vttState: signal(null),
            connect,
            disconnect,
            sendMessage: () => true,
          },
        },
      ],
    });

    const http = TestBed.inject(HttpTestingController);
    const charState = TestBed.inject(CharacterStateService);
    charState.activeCharacter.set({ ...HERO });

    const fixture = TestBed.createComponent(PlayerComponent);
    fixture.detectChanges();
    TestBed.flushEffects();

    expect(connect).toHaveBeenCalledTimes(1);
    expect(connect).toHaveBeenCalledWith('Curse of Strahd', { character: 'Lyra Meadowlark' });
    expect(disconnect).not.toHaveBeenCalled();

    // Editing HP or bumping version on the same hero/campaign must not tear down the socket.
    charState.activeCharacter.set({ ...HERO, hp_current: 21, version: 3 } as CharacterSchema);
    fixture.detectChanges();
    TestBed.flushEffects();

    expect(connect).toHaveBeenCalledTimes(1);
    expect(disconnect).not.toHaveBeenCalled();

    // Switching to another owned character sharing the same char_name MUST update wsConnectionKey.
    charState.activeCharacter.set({ ...HERO, char_id: 'lyra_homonym_2' } as CharacterSchema);
    fixture.detectChanges();
    TestBed.flushEffects();

    expect(connect).toHaveBeenCalledTimes(2);
    expect(disconnect).toHaveBeenCalled();

    http.match(() => true).forEach((req) => req.flush({}));
    fixture.destroy();
    jest.useRealTimers();
  });
});

describe('PlayerComponent — DM party_update long_rest & Exhaustion sync QA Fixes', () => {
  it('rehydrates full party_update long_rest payload and applies 2024 exhaustion immutably', () => {
    jest.useFakeTimers();
    const messages$ = new Subject<WsMessage>();
    const opened$ = new Subject<string>();

    TestBed.configureTestingModule({
      imports: [PlayerComponent],
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        provideRouter([]),
        {
          provide: WebSocketService,
          useValue: {
            messages$,
            opened$,
            vttState: signal(null),
            connect: jest.fn(),
            disconnect: jest.fn(),
            sendMessage: () => true,
          },
        },
      ],
    });

    const http = TestBed.inject(HttpTestingController);
    const charState = TestBed.inject(CharacterStateService);
    charState.activeCharacter.set({
      ...HERO,
      dnd_edition: '2024 Revision (5.5e)',
      speed: 30,
      hp_current: 12,
      hp_temp: 5,
      hit_dice_used: 4,
      exhaustion_level: 3,
      spell_slots: {
        level_1: { max: 4, used: 3 },
        pact: { max: 2, used: 2, level: 3 },
      },
      class_resources: [{ name: 'Favored Enemy', current: 0, max: 3, recharge: 'long' }],
      version: 2,
    } as CharacterSchema);

    const fixture = TestBed.createComponent(PlayerComponent);
    fixture.detectChanges();
    TestBed.flushEffects();

    // 1) Simulate DM broadcasting full long_rest payload
    messages$.next({
      type: 'party_update',
      payload: {
        char_id: HERO.char_id,
        action: 'long_rest',
        hp_current: 44,
        hp_max: 44,
        hp_temp: 0,
        hit_dice_used: 0,
        exhaustion_level: 2,
        speed: 20,
        death_saves: { successes: 0, failures: 0 },
        spell_slots: {
          level_1: { max: 4, used: 0 },
          pact: { max: 2, used: 0, level: 3 },
        },
        class_resources: [{ name: 'Favored Enemy', current: 3, max: 3, recharge: 'long' }],
        version: 3,
      },
    } as any);

    const afterRest = charState.activeCharacter()!;
    expect(afterRest.hp_current).toBe(44);
    expect(afterRest.hp_temp).toBe(0);
    expect(afterRest.hit_dice_used).toBe(0);
    expect(afterRest.exhaustion_level).toBe(2);
    expect(afterRest.speed).toBe(20);
    expect(afterRest.spell_slots?.['pact']?.used).toBe(0);
    expect(afterRest.class_resources?.[0]?.current).toBe(3);
    expect(afterRest.version).toBe(3);

    // 2) Inside a campaign, player cannot modify exhaustion directly; DM party_update restores 20 -> 30 immutably
    fixture.componentInstance.onUpdateHeroStatus({ exhaustion_level: 0 });
    expect(charState.activeCharacter()!.exhaustion_level).toBe(2);
    expect(charState.activeCharacter()!.speed).toBe(20);

    messages$.next({
      type: 'party_update',
      payload: {
        char_id: HERO.char_id,
        exhaustion_level: 0,
        speed: 30,
        version: 4,
      },
    } as any);
    expect(afterRest.speed).toBe(20);
    expect(charState.activeCharacter()!.exhaustion_level).toBe(0);
    expect(charState.activeCharacter()!.speed).toBe(30);

    // 3) Solo (outside campaign) player updates exhaustion locally 0 -> 1: speed drops 30 -> 25 immutably
    const beforeSolo = charState.activeCharacter()!;
    charState.activeCharacter.set({ ...beforeSolo, active_campaign: undefined });
    fixture.componentInstance.onUpdateHeroStatus({ exhaustion_level: 1 });
    expect(charState.activeCharacter()!.exhaustion_level).toBe(1);
    expect(charState.activeCharacter()!.speed).toBe(25);

    http.match(() => true).forEach((req) => req.flush({}));
    fixture.destroy();
    jest.useRealTimers();
  });

  it('recomputes char.skills on Quick Edit toggle and clears stale caches on saveEditModal', () => {
    const messages$ = new Subject<WsMessage>();
    const opened$ = new Subject<string>();

    TestBed.configureTestingModule({
      imports: [PlayerComponent],
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        provideRouter([]),
        {
          provide: WebSocketService,
          useValue: {
            messages$,
            opened$,
            vttState: signal(null),
            connect: jest.fn(),
            disconnect: jest.fn(),
            sendMessage: () => true,
          },
        },
      ],
    });

    const http = TestBed.inject(HttpTestingController);
    const charState = TestBed.inject(CharacterStateService);
    charState.activeCharacter.set({
      ...HERO,
      // Server-synced cached skills (WIS 16 (+3) + PB 3 = 6 for Perception)
      skill_proficiencies: ['Perception'],
      skill_expertise: [],
      skills: { Perception: 6, Stealth: 4 },
      saving_throw_values: { WIS: 3 },
      version: 1,
    } as CharacterSchema);

    const fixture = TestBed.createComponent(PlayerComponent);
    const comp = fixture.componentInstance;

    // Adding Expertise raises Perception 6 -> 9 (must not short-circuit on stale 6!)
    comp.toggleSkillExpertise('Perception');
    expect(charState.activeCharacter()!.skills!['Perception']).toBe(9);
    http.match(() => true).forEach((req) => req.flush({ ...charState.activeCharacter(), version: 2 }));

    // Removing Proficiency drops Perception 9 -> 3
    comp.toggleSkillProficiency('Perception');
    expect(charState.activeCharacter()!.skills!['Perception']).toBe(3);
    http.match(() => true).forEach((req) => req.flush({ ...charState.activeCharacter(), version: 3 }));

    // Opening Edit modal, changing WIS 16 -> 20 (+5), saving -> clears stale cached skills/saves
    comp.openEditModal();
    comp.editDraftChar!.stats!.WIS = 20;
    comp.saveEditModal();
    expect(charState.activeCharacter()!.skills).toBeUndefined();
    expect(charState.activeCharacter()!.saving_throw_values).toBeUndefined();
    expect(comp.getSkillModifier({ name: 'Perception', ability: 'WIS', label: 'Perception' } as any)).toBe(5);

    http.match(() => true).forEach((req) => req.flush({ ...charState.activeCharacter(), version: 4 }));
    fixture.destroy();
  });

  it('cancels superseded /forge/level-up-analysis calls via switchMap and updates rolled HP when subclass adds hp_bonus_per_level', () => {
    const messages$ = new Subject<WsMessage>();
    const opened$ = new Subject<string>();

    TestBed.configureTestingModule({
      imports: [PlayerComponent],
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        provideRouter([]),
        {
          provide: WebSocketService,
          useValue: {
            messages$,
            opened$,
            vttState: signal(null),
            connect: jest.fn(),
            disconnect: jest.fn(),
            sendMessage: () => true,
          },
        },
      ],
    });

    const http = TestBed.inject(HttpTestingController);
    const charState = TestBed.inject(CharacterStateService);
    charState.activeCharacter.set({
      ...HERO,
      char_id: 'sorc_l2',
      char_name: 'Lyra Emberveil',
      char_class: 'Sorcerer',
      char_level: 2,
      dnd_edition: '2024 Revision (5.5e)',
      dm_level_up_unlocked: true,
    } as CharacterSchema);

    const fixture = TestBed.createComponent(PlayerComponent);
    const comp = fixture.componentInstance;

    comp.onLevelUp();
    const initialReq = http.expectOne((r) => r.url.endsWith('/forge/level-up-analysis'));
    initialReq.flush({
      automatic_changes: [],
      hp_increase: 6,
      hp_bonus_per_level: 0,
      new_total_hp: 20,
      choices_required: [],
      updated_proficiency_bonus: 2,
      updated_spell_slots: { level_1: 4, level_2: 2 },
    });

    // Player rolls 6 (1d6+2) BEFORE picking Draconic Sorcery
    comp.levelUpUserChoices = {
      level_up_class: 'Sorcerer',
      hp_method: 'roll',
      hp_bonus_included: '0',
      custom_hp_increase: '6',
    };

    // Rapid subclass switches cancel the first in-flight request via switchMap
    comp.onLevelUpChoicesChange({ ...comp.levelUpUserChoices, subclass_0: 'Wild Magic Sorcery' });
    const req1 = http.expectOne((r) => r.url.endsWith('/forge/level-up-analysis'));
    comp.onLevelUpChoicesChange({ ...comp.levelUpUserChoices, subclass_0: 'Draconic Sorcery' });
    expect(req1.cancelled).toBe(true);

    const req2 = http.expectOne((r) => r.url.endsWith('/forge/level-up-analysis'));
    req2.flush({
      automatic_changes: [],
      hp_increase: 7,
      hp_bonus_per_level: 1,
      new_total_hp: 23,
      choices_required: [],
      updated_proficiency_bonus: 2,
      updated_spell_slots: { level_1: 4, level_2: 2 },
    });

    expect(comp.levelUpUserChoices['custom_hp_increase']).toBe('7');
    expect(comp.levelUpUserChoices['hp_bonus_included']).toBe('1');

    http.verify();
    fixture.destroy();
  });

  it('excludes feat_* and _stat* keys when refreshing level-up-analysis on subclass change', () => {
    const messages$ = new Subject<WsMessage>();
    const opened$ = new Subject<string>();

    TestBed.configureTestingModule({
      imports: [PlayerComponent],
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        provideRouter([]),
        {
          provide: WebSocketService,
          useValue: {
            messages$,
            opened$,
            vttState: signal(null),
            connect: jest.fn(),
            disconnect: jest.fn(),
            sendMessage: () => true,
          },
        },
      ],
    });

    const http = TestBed.inject(HttpTestingController);
    const charState = TestBed.inject(CharacterStateService);
    charState.activeCharacter.set({
      ...HERO,
      char_id: 'fighter_l3_sub',
      char_name: 'Valerius',
      char_class: 'Fighter',
      char_level: 2,
      dnd_edition: '2024 Revision (5.5e)',
      dm_level_up_unlocked: true,
    } as CharacterSchema);

    const fixture = TestBed.createComponent(PlayerComponent);
    const comp = fixture.componentInstance;

    comp.onLevelUp();
    const initialReq = http.expectOne((r) => r.url.endsWith('/forge/level-up-analysis'));
    initialReq.flush({
      automatic_changes: [],
      hp_increase: 6,
      hp_bonus_per_level: 0,
      new_total_hp: 20,
      choices_required: [],
      updated_proficiency_bonus: 2,
      updated_spell_slots: {},
    });

    comp.onLevelUpChoicesChange({
      level_up_class: 'Fighter',
      subclass_0: 'Champion',
      hp_method: 'roll',
      custom_hp_increase: '8',
      hp_bonus_included: '0',
      feat_0: 'Tough',
      feat_stat1_0: 'CON',
      feat_stat2_0: 'STR',
    });

    const req = http.expectOne((r) => r.url.endsWith('/forge/level-up-analysis'));
    expect(req.request.body.user_choices).toEqual({
      level_up_class: 'Fighter',
      subclass: 'Champion',
      hp_method: 'roll',
      custom_hp_increase: '8',
      hp_bonus_included: '0',
    });
    expect(req.request.body.user_choices['feat_0']).toBeUndefined();
    expect(req.request.body.user_choices['feat_stat1_0']).toBeUndefined();
    expect(req.request.body.user_choices['feat_stat2_0']).toBeUndefined();

    req.flush({
      automatic_changes: [],
      hp_increase: 6,
      hp_bonus_per_level: 0,
      new_total_hp: 20,
      choices_required: [],
      updated_proficiency_bonus: 2,
      updated_spell_slots: {},
    });

    http.verify();
    fixture.destroy();
  });
});

describe('PlayerComponent — Campaign Locks, Rests, Exhaustion 6 Death & Athas Sync', () => {
  const setupPlayer = (charOverrides: Partial<CharacterSchema> = {}) => {
    const messages$ = new Subject<WsMessage>();
    const opened$ = new Subject<string>();
    TestBed.configureTestingModule({
      imports: [PlayerComponent],
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        provideRouter([]),
        {
          provide: WebSocketService,
          useValue: {
            messages$,
            opened$,
            vttState: signal(null),
            connect: jest.fn(),
            disconnect: jest.fn(),
            sendMessage: () => true,
          },
        },
      ],
    });
    const http = TestBed.inject(HttpTestingController);
    const charState = TestBed.inject(CharacterStateService);
    charState.dndEdition.set(charOverrides.dnd_edition || '2014 Edition');
    charState.activeCharacter.set({
      ...HERO,
      dnd_edition: '2014 Edition',
      hp_max: 44,
      hp_current: 20,
      speed: 30,
      base_speed: 30,
      version: 2,
      ...charOverrides,
    });
    const fixture = TestBed.createComponent(PlayerComponent);
    fixture.detectChanges();
    TestBed.flushEffects();
    http.match((r) => r.method === 'GET').forEach((r) => {
      if (r.request.url.endsWith('/characters')) {
        r.flush({ characters: [charState.activeCharacter()] });
      } else {
        r.flush({ whispers: [], roll_requests: [], roll_logs: [] });
      }
    });
    return { fixture, comp: fixture.componentInstance, http, charState, messages$ };
  };

  it('blocks locked campaign rests & level-up, allows 1-shot DM unlocks via server rest endpoints, and auto-relocks', () => {
    const { comp, http, charState, fixture } = setupPlayer({
      dm_short_rest_unlocked: false,
      dm_long_rest_unlocked: false,
      dm_level_up_unlocked: false,
    });

    // All three locked in campaign
    comp.openShortRestModal();
    expect(comp.showShortRestModal()).toBe(false);
    comp.triggerLongRest();
    comp.onLevelUp();
    http.expectNone(() => true);

    // DM unlocks short rest & long rest -> calls dedicated backend routes and updates signal
    charState.activeCharacter.set({
      ...charState.activeCharacter()!,
      dm_short_rest_unlocked: true,
      dm_long_rest_unlocked: true,
    });

    comp.openShortRestModal();
    expect(comp.showShortRestModal()).toBe(true);
    comp.shortRestDiceToSpend = 1;
    comp.executeShortRest();
    const srReq = http.expectOne((r) => r.method === 'POST' && r.url.endsWith(`/characters/${HERO.char_id}/short-rest`));
    srReq.flush({ ...charState.activeCharacter()!, hp_current: 28, dm_short_rest_unlocked: false, version: 3 });
    expect(charState.activeCharacter()!.dm_short_rest_unlocked).toBe(false);
    expect(charState.activeCharacter()!.hp_current).toBe(28);

    comp.triggerLongRest();
    const lrReq = http.expectOne((r) => r.method === 'POST' && r.url.endsWith(`/characters/${HERO.char_id}/long-rest`));
    lrReq.flush({ ...charState.activeCharacter()!, hp_current: 44, dm_long_rest_unlocked: false, version: 4 });
    expect(charState.activeCharacter()!.dm_long_rest_unlocked).toBe(false);
    expect(charState.activeCharacter()!.hp_current).toBe(44);

    fixture.destroy();
  });

  it('blocks Exhaustion 6 deceased characters from healing, resting, and leveling, and rehydrates full Athas/modifier party_update payloads', () => {
    const { comp, http, charState, messages$, fixture } = setupPlayer({
      exhaustion_level: 6,
      exhaustion_bypass: false,
      hp_current: 0,
      dm_long_rest_unlocked: true,
      dm_level_up_unlocked: true,
    });

    comp.applyHeal(10);
    comp.adjustHp(5);
    comp.triggerLongRest();
    comp.onLevelUp();
    http.expectNone(() => true);
    expect(charState.activeCharacter()!.hp_current).toBe(0);

    // DM sends party_update waiving exhaustion, suppressing magic items (Athas), and adding signed modifiers
    messages$.next({
      type: 'party_update',
      payload: {
        char_id: HERO.char_id,
        exhaustion_level: 6,
        exhaustion_bypass: true,
        magic_items_suppressed: true,
        dm_modifiers: { ac_bonus: -2, attack_bonus: -1, note: 'Athas Heat' },
        ac: 13,
        hp_current: 1,
        hp_max: 44,
        speed: 30,
        inspiration: true,
        version: 5,
      },
    } as any);

    const updated = charState.activeCharacter()!;
    expect(updated.exhaustion_bypass).toBe(true);
    expect(updated.magic_items_suppressed).toBe(true);
    expect(updated.dm_modifiers?.ac_bonus).toBe(-2);
    expect(updated.armor_class).toBe(13);
    expect(updated.inspiration).toBe(true);

    // Waived hero CAN now heal!
    comp.applyHeal(9);
    expect(charState.activeCharacter()!.hp_current).toBe(10);
    http.match(() => true).forEach((r) => r.flush({ ...updated, hp_current: 10, version: 6 }));

    fixture.destroy();
  });

  it('lets Solo heroes freely adjust 2014 exhaustion with L2 speed halve, L4 HP halve, and L6 death', () => {
    const { comp, http, charState, fixture } = setupPlayer({
      active_campaign: undefined,
      dnd_edition: '2014 Edition',
      hp_max: 44,
      hp_current: 44,
      speed: 30,
      base_speed: 30,
      exhaustion_level: 0,
    });

    comp.onUpdateHeroStatus({ exhaustion_level: 2 });
    expect(charState.activeCharacter()!.speed).toBe(15);

    comp.onUpdateHeroStatus({ exhaustion_level: 4 });
    expect(charState.activeCharacter()!.hp_max).toBe(22);
    expect(charState.activeCharacter()!.base_hp_max).toBe(44);
    expect(charState.activeCharacter()!.hp_current).toBe(22);

    comp.onUpdateHeroStatus({ exhaustion_level: 3 });
    expect(charState.activeCharacter()!.hp_max).toBe(44);

    comp.onUpdateHeroStatus({ exhaustion_level: 6 });
    expect(charState.activeCharacter()!.speed).toBe(0);
    expect(charState.activeCharacter()!.hp_current).toBe(0);

    http.match(() => true).forEach((r) => r.flush(r.request.body));
    fixture.destroy();
  });

  it('syncs multi-tab player party_update locks/rest/level_up state, supports death_save/concentration roll targets, and blocks L6 potion consumption', () => {
    const { comp, http, charState, messages$, fixture } = setupPlayer({
      dnd_edition: '2024 Revision (5.5e)',
      exhaustion_level: 2, // -4 penalty in 2024
      dm_short_rest_unlocked: true,
      dm_level_up_unlocked: true,
      dm_modifiers: { saving_throws_bonus: 1 },
      stats: { STR: 10, DEX: 14, CON: 16, INT: 10, WIS: 12, CHA: 8 },
      saving_throws: ['CON'],
      proficiency_bonus: 3,
      hp_current: 20,
      hp_max: 44,
      version: 2,
    });

    // Adequate #3: Multi-tab `source: 'player'` level_up consumes lock & triggers reload
    messages$.next({
      type: 'party_update',
      payload: {
        char_id: HERO.char_id,
        source: 'player',
        action: 'level_up',
        level: 6,
        hp_max: 52,
        hp_current: 52,
        dm_level_up_unlocked: false,
        dm_short_rest_unlocked: false,
        spell_slots: { level_1: { max: 4, used: 0 } },
        passive_perception: 13,
        skills: { Perception: 3 },
        magic_items_suppressed: true,
        dm_modifiers: { saving_throws_bonus: 1, initiative_bonus: 2 },
        version: 3,
      },
    } as any);
    const updated = charState.activeCharacter()!;
    expect(updated.char_level).toBe(6);
    expect(updated.hp_max).toBe(52);
    expect(updated.dm_level_up_unlocked).toBe(false);
    expect(updated.dm_short_rest_unlocked).toBe(false);
    expect(updated.passive_perception).toBe(13);
    expect(updated.magic_items_suppressed).toBe(true);
    expect(updated.dm_modifiers?.initiative_bonus).toBe(2);
    const reloadReqs = http.match((r) => r.method === 'GET' && r.url.endsWith('/characters'));
    expect(reloadReqs.length).toBe(1);
    reloadReqs[0].flush({ characters: [updated] });

    // Minor #1: DM roll requests for death_save & concentration match backend modifiers
    messages$.next({
      type: 'roll_request',
      payload: request({ id: 'req-death', roll_type: 'death_save', stat: 'Death' }),
    } as WsMessage);
    // 2024 L2 (-4) + DM save (+1) = -3
    expect(comp.activeRollPromptModifier).toBe(-3);
    comp.dismissRollPrompt();
    http.expectOne((r) => r.url.includes('/roll-request/req-death/miss')).flush({ success: true });

    messages$.next({
      type: 'roll_request',
      payload: request({ id: 'req-conc', roll_type: 'concentration', stat: 'Concentration' }),
    } as WsMessage);
    // CON +3 + Prof +3 - 4 (Exh 2) + 1 (DM Save) = +3
    expect(comp.activeRollPromptModifier).toBe(3);
    comp.dismissRollPrompt();
    http.expectOne((r) => r.url.includes('/roll-request/req-conc/miss')).flush({ success: true });

    // attack_roll prompt uses STR + dm_modifiers.attack_bonus - 2024 Exhaustion penalty (never ability_checks_bonus)
    charState.activeCharacter.set({
      ...charState.activeCharacter()!,
      dnd_edition: '2024 Revision (5.5e)',
      exhaustion_level: 2,
      dm_modifiers: { attack_bonus: 3, ability_checks_bonus: -5 },
      stats: { STR: 16, DEX: 14, CON: 16, INT: 10, WIS: 12, CHA: 8 },
    });
    messages$.next({
      type: 'roll_request',
      payload: request({ id: 'req-atk', roll_type: 'attack_roll', stat: 'STR' }),
    } as WsMessage);
    // STR (+3) + DM Atk (+3) - 2024 Exh L2 (-4) = +2
    expect(comp.activeRollPromptModifier).toBe(2);
    comp.dismissRollPrompt();
    http.expectOne((r) => r.url.includes('/roll-request/req-atk/miss')).flush({ success: true });

    // addWeapon() initializes separated base damage_dice + damage_bonus with is_custom=true
    comp.addWeapon();
    const added = charState.activeCharacter()!.weapons!.slice(-1)[0];
    expect(added.damage_dice).toBe('1d8');
    expect(added.damage_bonus).toBe('+3');
    expect(added.is_custom).toBe(true);
    http.match((r) => r.method === 'PUT').forEach((r) => r.flush(charState.activeCharacter()));

    // Minor #2 & Minor #6: Exhaustion L6 deceased blocks onConsumePotion, setTempHp & adjustTempHp
    charState.activeCharacter.set({
      ...charState.activeCharacter()!,
      exhaustion_level: 6,
      exhaustion_bypass: false,
      hp_current: 0,
      hp_temp: 0,
      equipment: [{ name: 'Potion of Healing', quantity: 2 }],
    });
    comp.onConsumePotion({
      item: charState.activeCharacter()!.equipment![0],
      dice: '2d4',
      bonus: 2,
      name: 'Potion of Healing',
    });
    comp.setTempHp(10);
    comp.adjustTempHp(5);
    expect(charState.activeCharacter()!.hp_current).toBe(0);
    expect(charState.activeCharacter()!.hp_temp).toBe(0);
    expect(charState.activeCharacter()!.equipment![0].quantity).toBe(2);
    http.expectNone(() => true);

    fixture.destroy();
  });

  it('applies 2014 Rogue Reliable Talent floor on proficient skill checks and Bard Song of Rest / Sorcerous Restoration on short rest', () => {
    const { comp, http, charState, fixture } = setupPlayer({
      dnd_edition: '2014 Edition',
      active_campaign: undefined,
      char_class: 'Rogue',
      char_level: 11,
      proficiency_bonus: 4,
      stats: { STR: 10, DEX: 18, CON: 14, INT: 12, WIS: 12, CHA: 10 },
      skill_proficiencies: ['Stealth'],
      hp_current: 20,
      hp_max: 80,
      hit_dice: '11d8',
      hit_dice_used: 0,
    });
    const dice = TestBed.inject(DiceService);
    jest.spyOn(dice, 'rollDie').mockReturnValue(2);

    // Proficient skill gets floored d20 = 10 (+4 DEX +4 PB = 18)
    const stealthRoll = comp.rollSkillCheck({ name: 'Stealth', ability: 'DEX' });
    expect(stealthRoll.raw).toBe(10);
    expect(stealthRoll.total).toBe(18);

    // Untrained skill is NOT floored by Reliable Talent (2 + 0 = 2)
    const athleticsRoll = comp.rollSkillCheck({ name: 'Athletics', ability: 'STR' });
    expect(athleticsRoll.raw).toBe(2);
    expect(athleticsRoll.total).toBe(2);

    // 2014 Bard L5 Song of Rest (+1d6) + Hit Die roll during offline short rest
    charState.activeCharacter.set({
      ...charState.activeCharacter()!,
      char_class: 'Bard',
      char_level: 5,
      dnd_edition: '2014 Edition',
      stats: { STR: 8, DEX: 14, CON: 14, INT: 10, WIS: 12, CHA: 18 },
      hp_current: 15,
      hp_max: 38,
      hit_dice_used: 0,
      class_resources: [{ name: 'Sorcery Points', current: 2, max: 20, recharge: 'long' }],
    });
    jest.spyOn(dice, 'rollDie').mockReturnValue(4);
    comp.shortRestDiceToSpend = 1;
    comp.shortRestDieSize = 8;
    comp.shortRestManualHp = null;
    comp.executeShortRest();
    // 1d8 (4) + CON (+2) + Song of Rest 1d6 (4) = +10 HP (15 -> 25)
    expect(charState.activeCharacter()!.hp_current).toBe(25);
    http.match((r) => r.method === 'PUT').forEach((r) => r.flush(charState.activeCharacter()));

    fixture.destroy();
  });
});
