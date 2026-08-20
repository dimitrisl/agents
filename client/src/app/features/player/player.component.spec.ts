import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { provideRouter } from '@angular/router';
import { Subject } from 'rxjs';
import { PlayerComponent } from './player.component';
import { CharacterStateService } from '../../core/services/character-state.service';
import { DiceService } from '../../core/services/dice.service';
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
    http.expectOne((r) => r.url.endsWith('/characters')).flush([HERO]);
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
      http.expectOne((r) => r.url.endsWith('/characters')).flush([HERO]);

      opened$.next('Curse of Strahd');
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
      http.expectOne((r) => r.url.endsWith('/characters')).flush([HERO]);

      opened$.next('Curse of Strahd');
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
});
