import { LevelUpAnalysis, LevelUpApplyRequest, LevelUpChoice } from '../../core/models/character.model';
import {
  AfterViewChecked,
  Component,
  ElementRef,
  OnDestroy,
  OnInit,
  ViewChild,
  computed,
  effect,
  signal,
} from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { HttpClient } from '@angular/common/http';
import { ActivatedRoute, Router } from '@angular/router';
import { EMPTY, Subject, Subscription, catchError, debounceTime, switchMap, tap } from 'rxjs';
import { CharacterStateService } from '../../core/services/character-state.service';
import { HomebrewService } from '../../core/services/homebrew.service';
import { DiceRoll, DiceService, RollMode } from '../../core/services/dice.service';
import { RollToastService } from '../../core/services/roll-toast.service';
import { WebSocketService, WsMessage } from '../../core/services/websocket.service';
import { WakeLockService } from '../../core/services/wake-lock.service';
import { HapticsService } from '../../core/services/haptics.service';
import { CharacterSchema, EquipmentItem } from '../../core/models/character.model';
import { CampaignMessages, RollRequest, Whisper, campaignUrl } from '../../core/models/campaign.model';
import { buildInboxFeed, type InboxEntry } from '../../core/models/campaign-inbox';
import {
  ROLL_PROMPT_TIMEOUT_SECONDS,
  dropStalePrompts,
  isAwaitingPlayer,
  shouldPrompt,
} from '../../core/models/roll-prompt';
import {
  ALL_SKILLS,
  SkillDefinition,
  abilityModifier,
  abilityModifierOf,
  adjustedHp,
  availableHitDice,
  availableHitDieOptions,
  conModifier,
  findSkill,
  formatModifier,
  hasSpellSlotLevel,
  HitDieOption,
  hitDieSize,
  isProficientIn,
  hasExpertiseIn,
  levelUp,
  planShortRest,
  regainSpellSlot,
  resolveLongRest,
  resolveShortRest,
  restoreAllSpellSlots,
  restorePactSpellSlots,
  savingThrowModifier,
  skillModifier,
  skillModifierString,
  spellSlotMax,
  spellSlotUsed,
  spendSpellSlot,
  warlockPactDetails,
} from '../../core/rules';
import {
  ForgeButtonDirective,
  ForgeCardComponent,
  ForgeEmptyStateComponent,
  ForgeModalComponent,
  ForgePageComponent,
  ForgeTab,
  ForgeTextareaDirective,
} from '../../shared/ui';
import { PlayerDashboardHeaderComponent } from './player-dashboard-header/player-dashboard-header.component';
import { CharacterOverviewCardComponent } from './character-overview-card/character-overview-card.component';
import { CharacterTabsComponent } from './character-tabs/character-tabs.component';
import { RollModeSelectorComponent } from './roll-mode-selector/roll-mode-selector.component';
import { SkillsPanelComponent } from './tabs/skills-panel/skills-panel.component';
import { ActionDockComponent } from './action-dock/action-dock.component';
import { CombatPanelComponent } from './tabs/combat-panel/combat-panel.component';
import { SpellsPanelComponent } from './tabs/spells-panel/spells-panel.component';
import { RoleplayPanelComponent } from './tabs/roleplay-panel/roleplay-panel.component';
import { PdfPreviewModalComponent } from './modals/pdf-preview-modal/pdf-preview-modal.component';
import { ValidationModalComponent } from './modals/validation-modal/validation-modal.component';
import { LevelUpModalComponent } from './modals/level-up-modal/level-up-modal.component';
import { ShortRestModalComponent } from './modals/short-rest-modal/short-rest-modal.component';
import { JoinCampaignModalComponent } from './modals/join-campaign-modal/join-campaign-modal.component';
import { RollRequestModalComponent } from './modals/roll-request-modal/roll-request-modal.component';
import { PortraitModalComponent } from './modals/portrait-modal/portrait-modal.component';
import { StrategyGuideModalComponent } from './modals/strategy-guide-modal/strategy-guide-modal.component';
import { EditSheetModalComponent } from './modals/edit-sheet-modal/edit-sheet-modal.component';
import { ConditionsModalComponent } from './modals/conditions-modal/conditions-modal.component';
import { PlayerHomebrewModalComponent } from './modals/player-homebrew-modal/player-homebrew-modal.component';
import { VttGridComponent } from '../campaigns/vtt-grid/vtt-grid.component';
import { QuickDiceDrawerComponent } from './quick-dice-drawer/quick-dice-drawer.component';
import { environment } from '../../../environments/environment';

// The panels and modals under `features/player/` still import this from here.
// It lives in `core/rules` now, next to the maths that consumes it.
export type { SkillDefinition } from '../../core/rules';

/** What the DM's `roll_type` + `stat` pair actually means on this hero's sheet. */
interface RollTarget {
  /** Toast heading, e.g. `🎲 PERCEPTION CHECK`. */
  title: string;
  /** Prose for the prompt, e.g. `Perception check`. */
  label: string;
  /** The modifier read off the sheet, before anything the player adds. */
  modifier: number;
}

@Component({
  selector: 'app-player',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    ForgeButtonDirective,
    ForgeCardComponent,
    ForgeEmptyStateComponent,
    ForgeModalComponent,
    ForgePageComponent,
    ForgeTextareaDirective,
    PlayerDashboardHeaderComponent,
    CharacterOverviewCardComponent,
    CharacterTabsComponent,
    RollModeSelectorComponent,
    SkillsPanelComponent,
    ActionDockComponent,
    CombatPanelComponent,
    SpellsPanelComponent,
    RoleplayPanelComponent,
    PdfPreviewModalComponent,
    ValidationModalComponent,
    LevelUpModalComponent,
    ShortRestModalComponent,
    JoinCampaignModalComponent,
    RollRequestModalComponent,
    PortraitModalComponent,
    StrategyGuideModalComponent,
    EditSheetModalComponent,
    ConditionsModalComponent,
    PlayerHomebrewModalComponent,
    VttGridComponent,
    QuickDiceDrawerComponent,
  ],
  templateUrl: './player.component.html',
  styleUrl: './player.component.css',
})
export class PlayerComponent implements OnInit, OnDestroy, AfterViewChecked {
  @ViewChild('whisperFeed') private whisperFeed?: ElementRef<HTMLElement>;

  sheetSubTab = signal<'skills' | 'combat' | 'spells' | 'roleplay'>('skills');

  readonly sheetTabs: ForgeTab[] = [
    { id: 'skills', label: '📜 Skills & Checks' },
    { id: 'combat', label: '⚔️ Combat & Inventory' },
    { id: 'spells', label: '✨ Spells & Features' },
    { id: 'roleplay', label: '📖 Lore & Roleplay' },
  ];

  selectSheetSubTab(tabId: string): void {
    if (tabId === 'skills' || tabId === 'combat' || tabId === 'spells' || tabId === 'roleplay') {
      this.sheetSubTab.set(tabId);
    }
  }

  // --- Companion Mode State (#170, #175) ---
  isMobileViewport = signal(false);
  companionModeOverride = signal<boolean | null>(null);
  isCompanionMode = computed(() => {
    if (this.companionModeOverride() !== null) {
      return !!this.companionModeOverride();
    }
    return this.isMobileViewport();
  });
  mobileActiveTab = signal<'hero' | 'combat' | 'skills' | 'spells' | 'table'>('hero');
  showQuickDiceDrawer = signal(false);
  showConcentrationPrompt = signal(false);
  concentrationDc = signal(10);
  editMode = signal(false);
  showEditModal = signal(false);
  showConditionsModal = signal(false);
  showPortraitModal = signal(false);
  showJoinModal = signal(false);
  showHomebrewModal = signal(false);
  showShortRestModal = signal(false);
  showProficientOnly = signal(false);
  showLevelUpModal = signal(false);
  showValidationModal = signal(false);
  showWhisperInbox = signal(false);
  showImportModal = signal(false);
  importTab = signal<'pdf' | 'dndbeyond' | 'foundry'>('pdf');
  isImporting = signal(false);
  importError = signal<string | null>(null);
  importWarnings = signal<string[]>([]);
  dndBeyondUrl = '';
  editDraftChar: CharacterSchema | null = null;
  isValidating = false;
  isAutoFixing = false;
  validationResult: any = null;
  levelUpAnalysis: LevelUpAnalysis | null = null;
  levelUpUserChoices: Record<string, any> = {};
  shortRestDiceToSpend = 1;
  shortRestDieSize = 8;
  joinInviteCode = '';
  rollMode: RollMode = 'normal';
  encounterState: any = null;

  portraitPrompt = '';
  strategyGuideText: string | null = null;

  openGroups: { [key: string]: boolean } = {
    STR: true,
    DEX: true,
    INT: false,
    WIS: false,
    CHA: false
  };

  readonly skillAttributes = ['STR', 'DEX', 'INT', 'WIS', 'CHA'];

  // Snapshot of `openGroups` taken when the proficiency filter is switched on,
  // so switching it back off returns the sheet to the user's own layout.
  private openGroupsBeforeFilter: { [key: string]: boolean } | null = null;

  allSkills: SkillDefinition[] = [...ALL_SKILLS];

  private wsSub: Subscription | null = null;
  private openedSub: Subscription | null = null;
  pdfPreviewUrl: string | null = null;
  pdfPreviewBlobUrl: string | null = null;
  whisperHistory: Whisper[] = [];
  rollRequestHistory: RollRequest[] = [];
  /** Both kinds in one chronological thread — the timestamps tell them apart. */
  inboxFeed: InboxEntry[] = [];
  unreadMessages = 0;
  whisperReply = '';
  isSendingWhisperReply = false;
  private loadedCampaignMessageKey: string | null = null;
  private pendingFeedScroll = false;
  private resolvedRollRequestIds = new Set<string>();

  // --- DM roll requests (#26) ---
  // The DM's request is a question, not an order to the dice: it opens a prompt and
  // waits. Requests that arrive while one is open queue behind it, so a reconnect
  // that replays four missed requests asks four times instead of rolling four times.
  activeRollPrompt: RollRequest | null = null;
  promptRollMode: RollMode = 'normal';
  promptSituationalBonus = 0;
  promptSecondsRemaining = 0;
  private rollPromptQueue: RollRequest[] = [];
  private promptTimer: ReturnType<typeof setInterval> | null = null;

  // The HP steppers fire once per click; only the value the user settles on is
  // worth a round trip, so writes are collapsed into a single trailing save.
  private readonly hpSave$ = new Subject<{ char: CharacterSchema; version: number }>();
  private localSaveVersion = 0;

  constructor(
    public charState: CharacterStateService,
    private dice: DiceService,
    private rollToast: RollToastService,
    private http: HttpClient,
    private router: Router,
    private route: ActivatedRoute,
    private wsService: WebSocketService,
    private homebrewService: HomebrewService,
    public wakeLock: WakeLockService,
    public haptics: HapticsService
  ) {
    this.hpSave$
      .pipe(
        debounceTime(700),
        switchMap(({ char, version }) =>
          this.http.put<CharacterSchema>(`${environment.apiBaseUrl}/characters/${char.char_id!}`, char)
            .pipe(
              tap(updated => {
                // ONLY apply the backend response if no newer local edits have occurred
                // during the 700ms debounce + network delay.
                if (this.localSaveVersion === version) {
                  this.charState.activeCharacter.set(updated);
                  // also update the cache silently
                  const list = this.charState.characters();
                  const idx = list.findIndex(c => c.char_id === updated.char_id);
                  if (idx >= 0) {
                    this.charState.characters.set(list.map((c, i) => i === idx ? updated : c));
                  }
                }
              }),
              catchError(() => EMPTY)
            )
        ),
        takeUntilDestroyed()
      )
      .subscribe();

    effect((onCleanup) => {
      const char = this.charState.activeCharacter();
      if (char && char.active_campaign) {
        // The character rides along on the handshake so the server can route
        // private whispers and roll requests to this hero alone.
        this.wsService.connect(char.active_campaign, {
          character: char.char_name,
        });
      } else {
        this.wsService.disconnect();
        this.whisperHistory = [];
        this.rollRequestHistory = [];
        this.unreadMessages = 0;
        this.whisperReply = '';
        this.showWhisperInbox.set(false);
        this.loadedCampaignMessageKey = null;
        this.clearRollPrompts();
        this.rebuildInboxFeed();
      }
      onCleanup(() => { this.wsService.disconnect(); });
    });
  }

  private campaignInitialLoad = new Set<string>();
  private mq?: MediaQueryList;
  private readonly mqListener = (e: MediaQueryListEvent) => this.isMobileViewport.set(e.matches);
  private readonly visibilityListener = () => {
    if (typeof document !== 'undefined' && document.visibilityState === 'visible') {
      const char = this.charState.activeCharacter();
      if (char && char.active_campaign) {
        this.wsService.connect(char.active_campaign, { character: char.char_name });
        this.loadCampaignMessageHistory(char.active_campaign, char.char_name, true);
      }
    }
  };
  private queryParamsSub?: Subscription;

  ngOnInit() {
    this.charState.ensureLoaded().subscribe();

    if (typeof window !== 'undefined' && typeof window.matchMedia === 'function') {
      this.mq = window.matchMedia('(max-width: 1023px)');
      this.isMobileViewport.set(this.mq.matches);
      this.mq.addEventListener('change', this.mqListener);
    }

    if (typeof document !== 'undefined') {
      document.addEventListener('visibilitychange', this.visibilityListener);
    }

    this.queryParamsSub = this.route.queryParams.subscribe((params) => {
      if (params['import'] === '1') {
        this.openImportModal();
      }
    });

    // Every (re)connect re-reads the thread, so a dropped socket costs nothing
    // and the hero never has to reload the page to see what the DM sent.
    this.openedSub = this.wsService.opened$.subscribe((campaignName) => {
      const char = this.charState.activeCharacter();
      if (char?.active_campaign === campaignName) {
        const cacheKey = `${campaignName}::${char.char_name}`;
        const isCatchUp = this.campaignInitialLoad.has(cacheKey);
        this.campaignInitialLoad.add(cacheKey);
        this.loadCampaignMessageHistory(campaignName, char.char_name, isCatchUp);
      }
    });

    this.wsSub = this.wsService.messages$.subscribe((msg: WsMessage) => {
      const char = this.charState.activeCharacter();
      if (!char) return;

      if (msg.type === 'roll_request') {
        const req = msg['payload'];
        // Check if this request is for the active character
        if (this.isRollRequestForCharacter(req, char)) {
          this.addRollRequest(req, true);
          // The prompt itself is the notification — a toast on top of a modal that
          // says the same thing is just noise. Queued requests do get one, because
          // those are the ones the player cannot see yet.
          this.enqueueRollPrompt(req);
        }
      } else if (msg.type === 'encounter_update') {
        const wasMyTurn = this.isMyTurn;
        this.encounterState = msg['payload'];
        if (!wasMyTurn && this.isMyTurn) {
          this.haptics.turnAlert();
          this.rollToast.showMessage('⚔️ IT\'S YOUR TURN!', 'The DM advanced initiative to your turn!');
        }

      } else if (msg.type === 'party_update') {
        const payload = msg['payload'];
        if (payload && payload.action === 'removed' && payload.char_id === char.char_id) {
          this.charState.loadCharacters().subscribe(() => {
            this.router.navigate(['/']);
          });
          return;
        }
        this.applyDmPartyUpdate(payload, char);
      } else if (msg.type === 'campaign_deleted') {
        this.charState.loadCharacters().subscribe(() => {
          this.router.navigate(['/']);
        });
      } else if (msg.type === 'homebrew_created') {
        if (char.active_campaign) {
          this.homebrewService.loadHomebrew(char.active_campaign).subscribe();
        }
      } else if (msg.type === 'loot_distributed') {
        const payload = msg['payload'];
        if (payload?.character_ids?.includes(char.char_id)) {
          this.charState.loadCharacters().subscribe();
          const details: string[] = [];
          if (payload.currency) {
            const currParts: string[] = [];
            if (payload.currency.pp) currParts.push(`${payload.currency.pp}pp`);
            if (payload.currency.gp) currParts.push(`${payload.currency.gp}gp`);
            if (payload.currency.ep) currParts.push(`${payload.currency.ep}ep`);
            if (payload.currency.sp) currParts.push(`${payload.currency.sp}sp`);
            if (payload.currency.cp) currParts.push(`${payload.currency.cp}cp`);
            if (currParts.length) details.push(currParts.join(', '));
          }
          if (payload.items?.length) {
            details.push(`${payload.items.length} item(s)`);
          }
          const summary = details.length ? `: ${details.join(' & ')}` : '';
          this.rollToast.showMessage('💰 LOOT RECEIVED', `The DM awarded loot${summary}!`);
        }
      } else if (msg.type === 'whisper') {
        const whisper = msg['payload'];
        if (!this.isWhisperForCharacter(whisper, char.char_name)) return;

        // The hero's own reply comes back down the socket too; it belongs in the
        // thread, but it is not news worth a toast or an unread badge.
        const isOwnReply = whisper.sender === char.char_name;
        this.addWhisper(whisper, !isOwnReply);
        if (!isOwnReply) {
          this.rollToast.showMessage(`💬 WHISPER FROM ${whisper.sender}`, whisper.message);
        }
      }
    });
  }

  ngOnDestroy() {
    this.mq?.removeEventListener('change', this.mqListener);
    if (typeof document !== 'undefined') {
      document.removeEventListener('visibilitychange', this.visibilityListener);
    }
    this.queryParamsSub?.unsubscribe();
    if (this.wsSub) {
      this.wsSub.unsubscribe();
    }
    this.openedSub?.unsubscribe();
    this.clearPromptCountdown();
  }

  /**
   * The DM tracked a hit or a condition at the table. The sheet is already
   * written server-side, so this only catches the open page up — saving from
   * here would race the DM with a stale copy of the hero.
   */
  private applyDmPartyUpdate(payload: any, char: CharacterSchema) {
    if (!payload || payload.char_id !== char.char_id) return;

    const previousHp = char.hp_current ?? char.hp_max;
    const updated: CharacterSchema = { ...char };
    if (typeof payload.hp_current === 'number') updated.hp_current = payload.hp_current;
    if (Array.isArray(payload.conditions)) updated.conditions = [...payload.conditions];
    this.charState.activeCharacter.set(updated);

    const hp = updated.hp_current ?? updated.hp_max;
    if (hp !== previousHp) {
      const delta = hp - previousHp;
      const verb = delta < 0 ? `took ${Math.abs(delta)} damage` : `healed ${delta}`;
      this.rollToast.showMessage('❤️ DM UPDATED YOUR HP', `You ${verb} — now ${hp}/${updated.hp_max}.`);
    }
  }

  /** A chat thread is only useful if it lands on the newest message. */
  ngAfterViewChecked() {
    if (!this.pendingFeedScroll || !this.whisperFeed) return;
    this.pendingFeedScroll = false;
    const element = this.whisperFeed.nativeElement;
    element.scrollTop = element.scrollHeight;
  }

  private rebuildInboxFeed() {
    this.inboxFeed = buildInboxFeed(this.whisperHistory, this.rollRequestHistory);
    this.pendingFeedScroll = true;
  }

  toggleGroup(attr: string) {
    this.openGroups = { ...this.openGroups, [attr]: !this.openGroups[attr] };
  }

  // Turning the proficiency filter on collapses every ability group that has no
  // proficient skill and expands the ones that do, so the filtered sheet opens
  // straight onto what is actually rollable. Turning it off restores whatever
  // the user had expanded beforehand.
  onShowProficientOnlyChange(showProficientOnly: boolean): void {
    if (showProficientOnly === this.showProficientOnly()) return;
    this.showProficientOnly.set(showProficientOnly);

    if (showProficientOnly) {
      this.openGroupsBeforeFilter = { ...this.openGroups };

      const filtered: { [key: string]: boolean } = { ...this.openGroups };
      for (const attr of this.skillAttributes) {
        filtered[attr] = this.hasProficientSkill(attr);
      }
      this.openGroups = filtered;
      return;
    }

    if (this.openGroupsBeforeFilter) {
      this.openGroups = { ...this.openGroupsBeforeFilter };
      this.openGroupsBeforeFilter = null;
    }
  }

  private hasProficientSkill(attr: string): boolean {
    return this.getSkillsByAttribute(attr).some((skill) => this.isProficient(skill.name));
  }

  getSkillsByAttribute = (attr: string): SkillDefinition[] => {
    return this.allSkills.filter((s) => s.ability === attr);
  }

  getAttributeFullName = (attr: string): string => {
    const names: { [key: string]: string } = {
      STR: 'Strength',
      DEX: 'Dexterity',
      INT: 'Intelligence',
      WIS: 'Wisdom',
      CHA: 'Charisma'
    };
    return names[attr] || attr;
  }

  getAttributeModifier = (attr: string): string => {
    return formatModifier(abilityModifierOf(this.charState.activeCharacter(), attr));
  }

  goToForge() {
    this.router.navigate(['/forge']);
  }

  getClassHitDieSize(): number {
    return hitDieSize(this.charState.activeCharacter());
  }

  getHitDieOptions(): HitDieOption[] {
    return availableHitDieOptions(this.charState.activeCharacter());
  }

  getConModifier(): number {
    return conModifier(this.charState.activeCharacter());
  }

  getAvailableHitDice(): number {
    return availableHitDice(this.charState.activeCharacter());
  }

  getWarlockPactDetails() {
    return warlockPactDetails(this.charState.activeCharacter());
  }

  openShortRestModal() {
    this.shortRestDiceToSpend = this.getAvailableHitDice() > 0 ? 1 : 0;
    this.shortRestDieSize = this.getClassHitDieSize();
    this.showShortRestModal.set(true);
  }

  executeShortRest() {
    const char = this.charState.activeCharacter();
    if (!char) return;

    const plan = planShortRest(char, this.shortRestDiceToSpend, this.shortRestDieSize);
    if (!plan) return;

    const { diceSpent, dieSize, conBonus } = plan;
    const roll = diceSpent > 0
      ? this.dice.roll({ numDice: diceSpent, sides: dieSize, modifier: conBonus })
      : null;
    const rest = resolveShortRest(char, plan, roll ? roll.total : 0);

    char.hp_current = rest.hpAfter;
    char.hit_dice_used = rest.hitDiceUsed;

    if (rest.pactDetails && char.spell_slots) {
      char.spell_slots = restorePactSpellSlots(
        char.spell_slots,
        rest.pactDetails.pactSlotLevel,
        rest.pactDetails.pactSlotCount
      );
    }

    if (char.class_resources) {
      char.class_resources.forEach((r) => {
        if (r.recharge === 'short') {
          r.current = r.max;
        }
      });
    }

    this.saveCurrentChar();
    this.showShortRestModal.set(false);

    if (roll && diceSpent > 0) {
      this.rollToast.showRoll({
        title: `⛺ SHORT REST HEAL (${diceSpent}d${dieSize})`,
        // Every hit die is worth showing here, so this spells them out rather than
        // using the service's summed form.
        expression: `${diceSpent}d${dieSize} (${roll.rolls.join(', ')}) ${this.dice.signed(conBonus)}`,
        raw: roll.raw,
        rolls: roll.rolls,
        sides: dieSize,
        modifier: conBonus,
        // The roll display shows what the dice came to; the message shows what the
        // hero actually got, which is less whenever the rest hits `hp_max`.
        total: rest.rolled,
        message: `Healed for +${rest.hpGained} HP! (${rest.hpBefore} ➡️ ${rest.hpAfter})`
      });
    } else if (rest.restoresPactSlots) {
      this.rollToast.showMessage(
        '⛺ SHORT REST COMPLETED',
        `Warlock Pact Magic spell slots restored for ${char.char_name}.`
      );
    }
  }

  triggerLongRest() {
    const char = this.charState.activeCharacter();
    if (!char) return;

    const rest = resolveLongRest(char);
    char.hp_current = rest.hpCurrent;
    char.hit_dice_used = rest.hitDiceUsed;

    if (char.spell_slots) {
      char.spell_slots = restoreAllSpellSlots(char.spell_slots);
    }
    if (char.class_resources) {
      char.class_resources.forEach((r) => {
        r.current = r.max;
      });
    }
    this.saveCurrentChar();
    this.rollToast.showMessage('🌙 LONG REST COMPLETED', `Full HP, spell slots, and ${rest.hitDiceRecovered} Hit Dice restored for ${char.char_name}.`);
  }

  getSpellSlotMax = (lvl: number): number => {
    return spellSlotMax(this.charState.activeCharacter(), lvl);
  }

  getSpellSlotUsed = (lvl: number): number => {
    return spellSlotUsed(this.charState.activeCharacter(), lvl);
  }

  useSpellSlot(lvl: number) {
    const char = this.charState.activeCharacter();
    // A slot the sheet does not record cannot be spent, and a save that changes
    // nothing is still a round trip.
    if (!char || !hasSpellSlotLevel(char, lvl)) return;

    char.spell_slots = spendSpellSlot(char.spell_slots, lvl);
    this.saveCurrentChar();
  }

  restoreSpellSlot(lvl: number) {
    const char = this.charState.activeCharacter();
    // A level the sheet has never recorded has nothing to give back, and a
    // pointless save is still a round trip.
    if (!char || !hasSpellSlotLevel(char, lvl)) return;

    char.spell_slots = regainSpellSlot(char.spell_slots, lvl);
    this.saveCurrentChar();
  }

  isProficient = (skillName: string): boolean => {
    return isProficientIn(this.charState.activeCharacter(), skillName);
  }

  isExpertise = (skillName: string): boolean => {
    return hasExpertiseIn(this.charState.activeCharacter(), skillName);
  }

  toggleSkillProficiency(skillName: string) {
    const char = this.charState.activeCharacter();
    if (!char) return;
    if (!char.skill_proficiencies) char.skill_proficiencies = [];
    if (!char.skill_expertise) char.skill_expertise = [];

    const index = char.skill_proficiencies.indexOf(skillName);
    if (index > -1) {
      char.skill_proficiencies.splice(index, 1);
      const expIdx = char.skill_expertise.indexOf(skillName);
      if (expIdx > -1) {
        char.skill_expertise.splice(expIdx, 1);
      }
      this.rollToast.showMessage('⚪ PROFICIENCY REMOVED', `${skillName} is no longer proficient.`);
    } else {
      char.skill_proficiencies.push(skillName);
      this.rollToast.showMessage('⭐ PROFICIENCY ADDED', `${skillName} is now proficient.`);
    }

    if (char.skills) {
      const skillDef = ALL_SKILLS.find((s) => s.name === skillName);
      if (skillDef) {
        char.skills[skillName] = skillModifier(char, skillDef);
      }
    }
    this.saveCurrentChar();
  }

  toggleSkillExpertise(skillName: string) {
    const char = this.charState.activeCharacter();
    if (!char) return;
    if (!char.skill_proficiencies) char.skill_proficiencies = [];
    if (!char.skill_expertise) char.skill_expertise = [];

    const expIndex = char.skill_expertise.indexOf(skillName);
    if (expIndex > -1) {
      char.skill_expertise.splice(expIndex, 1);
      this.rollToast.showMessage('⚪ EXPERTISE REMOVED', `${skillName} expertise removed.`);
    } else {
      char.skill_expertise.push(skillName);
      if (!char.skill_proficiencies.includes(skillName)) {
        char.skill_proficiencies.push(skillName);
      }
      this.rollToast.showMessage('🌟 EXPERTISE ADDED', `${skillName} now has Expertise.`);
    }

    if (char.skills) {
      const skillDef = ALL_SKILLS.find((s) => s.name === skillName);
      if (skillDef) {
        char.skills[skillName] = skillModifier(char, skillDef);
      }
    }
    this.saveCurrentChar();
  }

  getSkillModifier(skill: SkillDefinition): number {
    return skillModifier(this.charState.activeCharacter(), skill);
  }

  getSkillModString = (skill: SkillDefinition): string => {
    return skillModifierString(this.charState.activeCharacter(), skill);
  }

  /**
   * Rolls a d20 and pushes the result to the toast. The mode defaults to the sheet's
   * own selector, which is what every button on the sheet wants; a DM roll request
   * passes the mode the player picked in the prompt instead.
   */
  private showD20Roll(title: string, modifier: number, mode: RollMode = this.rollMode) {
    const roll = this.dice.rollD20(modifier, mode);

    this.rollToast.showRoll({
      title: `${title}${this.dice.modeLabel(roll.mode)}`,
      expression: roll.expression,
      raw: roll.raw,
      rolls: roll.rolls,
      sides: roll.sides,
      modifier: roll.modifier,
      total: roll.total,
      mode: roll.mode
    });

    return roll;
  }

  rollSkillCheck(skill: SkillDefinition) {
    return this.showD20Roll(`🎲 ${skill.name.toUpperCase()} CHECK`, this.getSkillModifier(skill));
  }

  rollAbilityCheck(stat: string) {
    const char = this.charState.activeCharacter();
    if (!char || !char.stats) return;

    return this.showD20Roll(`🎲 ${stat} CHECK`, abilityModifierOf(char, stat));
  }

  rollSavingThrow(stat: string) {
    const char = this.charState.activeCharacter();
    if (!char || !char.stats) return;

    return this.showD20Roll(`🛡️ ${stat} SAVING THROW`, savingThrowModifier(char, stat));
  }

  /**
   * Reads the DM's `roll_type` + `stat` off this hero's sheet without throwing
   * anything. The prompt needs the modifier to show the player what they are about
   * to roll, and the roll itself needs the same number — so it is worked out once.
   */
  private resolveRollTarget(rollType: string, stat: string): RollTarget | null {
    const char = this.charState.activeCharacter();
    if (!char || !char.stats) return null;

    const normalizedType = rollType.toLowerCase().replace(/[\s-]+/g, '_');

    if (normalizedType === 'save' || normalizedType === 'saving_throw' || normalizedType === 'savingthrow') {
      return {
        title: `🛡️ ${stat} SAVING THROW`,
        label: `${stat} saving throw`,
        modifier: savingThrowModifier(char, stat),
      };
    }

    if (normalizedType === 'skill' || normalizedType === 'skill_check') {
      const skill = findSkill(this.allSkills, stat);
      // An unknown skill name falls through to a plain ability check, the same way
      // it always has — the DM may have typed a stat where a skill was expected.
      if (skill) {
        return {
          title: `🎲 ${skill.name.toUpperCase()} CHECK`,
          label: `${skill.name} check`,
          modifier: this.getSkillModifier(skill),
        };
      }
    }

    return {
      title: `🎲 ${stat} CHECK`,
      label: `${stat} check`,
      modifier: abilityModifierOf(char, stat),
    };
  }

  private executeRollRequest(
    rollType: string,
    stat: string,
    mode: RollMode,
    situationalBonus: number
  ): DiceRoll | undefined {
    const target = this.resolveRollTarget(rollType, stat);
    if (!target) return undefined;

    return this.showD20Roll(target.title, target.modifier + situationalBonus, mode);
  }

  private rollForRequest(
    request: RollRequest,
    mode: RollMode,
    situationalBonus: number
  ): void {
    if (request.id && this.resolvedRollRequestIds.has(request.id)) return;

    const roll = this.executeRollRequest(request.roll_type, request.stat, mode, situationalBonus);
    if (!roll) return;

    if (request.id) {
      this.resolvedRollRequestIds.add(request.id);
    }
    this.markRollRequestResolved(request, roll, situationalBonus);
    this.submitRollRequestResult(request, roll, situationalBonus);
  }

  // --- The roll request prompt (#26) ---

  get queuedRollPromptCount(): number {
    return this.rollPromptQueue.length;
  }

  /** `Perception check` — what the open prompt is asking for, in the sheet's words. */
  get activeRollPromptLabel(): string {
    return this.activeRollPromptTarget?.label ?? '';
  }

  get activeRollPromptModifier(): number {
    return this.activeRollPromptTarget?.modifier ?? 0;
  }

  private get activeRollPromptTarget(): RollTarget | null {
    const request = this.activeRollPrompt;
    return request ? this.resolveRollTarget(request.roll_type, request.stat) : null;
  }

  /**
   * The one gate every incoming request passes through. Catch-up replays the whole
   * thread on each reconnect, so this is what stops a flaky socket from asking the
   * same question five times.
   */
  private enqueueRollPrompt(request: RollRequest): void {
    const promptable = shouldPrompt(request, {
      answeredIds: this.resolvedRollRequestIds,
      queued: this.rollPromptQueue,
      active: this.activeRollPrompt,
    });
    if (!promptable) return;

    if (this.activeRollPrompt) {
      this.rollPromptQueue = [...this.rollPromptQueue, request];
      this.rollToast.showMessage(
        '🎲 ANOTHER ROLL QUEUED',
        `The DM also wants a ${request.roll_type} (${request.stat}). You will be asked next.`
      );
      return;
    }

    this.startRollPrompt(request);
  }

  /**
   * The inbox's own Roll button. Unlike `enqueueRollPrompt` this deliberately
   * ignores the request's status, so a roll the player let lapse can still be
   * answered — missing one is a slip, not a locked door.
   */
  openRollPrompt(request: RollRequest): void {
    if (request.id && this.resolvedRollRequestIds.has(request.id)) return;
    if (this.activeRollPrompt?.id === request.id) return;

    if (this.activeRollPrompt) {
      // Never swap the question out from under a player mid-decision.
      if (!this.rollPromptQueue.some((queued) => queued.id === request.id)) {
        this.rollPromptQueue = [...this.rollPromptQueue, request];
      }
      return;
    }

    this.rollPromptQueue = this.rollPromptQueue.filter((queued) => queued.id !== request.id);
    this.startRollPrompt(request);
  }

  confirmRollPrompt(): void {
    const request = this.activeRollPrompt;
    if (!request) return;

    this.rollForRequest(request, this.promptRollMode, this.promptSituationalBonus);
    this.finishRollPrompt();
  }

  /** The Skip button, a dismissed dialog, and the countdown reaching zero all land here. */
  dismissRollPrompt(): void {
    const request = this.activeRollPrompt;
    if (!request) return;

    this.markRollRequestMissed(request);
    this.finishRollPrompt();
  }

  /**
   * `forge-modal` emits `openChange(false)` for a programmatic close too, so this
   * only counts as a dismissal while a prompt is genuinely still open — otherwise
   * confirming a roll would immediately mark the request it just answered as missed.
   */
  onRollPromptOpenChange(open: boolean): void {
    if (!open && this.activeRollPrompt) {
      this.dismissRollPrompt();
    }
  }

  private startRollPrompt(request: RollRequest): void {
    this.activeRollPrompt = request;
    // Every request starts from a clean slate: advantage on the last roll says
    // nothing about this one.
    this.promptRollMode = 'normal';
    this.promptSituationalBonus = 0;
    this.promptSecondsRemaining = ROLL_PROMPT_TIMEOUT_SECONDS;
    this.startPromptCountdown();
  }

  private finishRollPrompt(): void {
    this.clearPromptCountdown();
    this.activeRollPrompt = null;

    const [next, ...rest] = this.rollPromptQueue;
    if (!next) return;

    this.rollPromptQueue = rest;
    this.startRollPrompt(next);
  }

  private startPromptCountdown(): void {
    this.clearPromptCountdown();
    this.promptTimer = setInterval(() => {
      this.promptSecondsRemaining -= 1;
      if (this.promptSecondsRemaining > 0) return;

      const request = this.activeRollPrompt;
      this.dismissRollPrompt();
      if (request) {
        this.rollToast.showMessage(
          '⌛ ROLL MISSED',
          `You did not answer the DM's ${request.roll_type} (${request.stat}) in time. You can still roll it from the inbox.`
        );
      }
    }, 1000);
  }

  private clearPromptCountdown(): void {
    if (this.promptTimer === null) return;
    clearInterval(this.promptTimer);
    this.promptTimer = null;
  }

  /** Leaving the campaign takes its unanswered questions with it. */
  private clearRollPrompts(): void {
    this.clearPromptCountdown();
    this.activeRollPrompt = null;
    this.rollPromptQueue = [];
    this.promptSecondsRemaining = 0;
  }

  toggleWhisperInbox(): void {
    this.showWhisperInbox.set(!this.showWhisperInbox());
    if (this.showWhisperInbox()) {
      this.unreadMessages = 0;
      this.pendingFeedScroll = true;
    }
  }

  closeWhisperInbox(): void {
    this.showWhisperInbox.set(false);
  }

  formatWhisperTime(timestamp?: string): string {
    if (!timestamp) return 'Just now';

    const normalized = timestamp.includes('T')
      ? timestamp
      : `${timestamp.replace(' ', 'T')}Z`;
    const date = new Date(normalized);

    if (Number.isNaN(date.getTime())) {
      return timestamp;
    }

    return new Intl.DateTimeFormat('el-GR', {
      day: '2-digit',
      month: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
    }).format(date);
  }

  formatRollRequestTime(timestamp?: string): string {
    return this.formatWhisperTime(timestamp);
  }

  /**
   * `isCatchUp` is the reconnect case: the thread is merged rather than replaced,
   * so whatever the DM sent while the socket was down still lands as unread
   * instead of quietly filling in.
   */
  private loadCampaignMessageHistory(
    campaignName: string,
    characterName: string,
    isCatchUp = false
  ): void {
    const key = `${campaignName}::${characterName}`;
    if (!isCatchUp) {
      if (this.loadedCampaignMessageKey === key) return;
      this.loadedCampaignMessageKey = key;
    }

    this.http
      .get<CampaignMessages>(campaignUrl(campaignName, 'messages'))
      .subscribe({
        next: (messages) => {
          const char = this.charState.activeCharacter();
          if (char?.active_campaign !== campaignName || char?.char_name !== characterName) return;

          const whispers = (messages.whispers || []).filter((whisper) =>
            this.isWhisperForCharacter(whisper, characterName)
          );
          const requests = (messages.roll_requests || []).filter((request) =>
            this.isRollRequestForCharacterName(request, characterName)
          );

          if (!isCatchUp) {
            this.whisperHistory = whispers.sort(
              (a, b) => this.whisperSortValue(a) - this.whisperSortValue(b)
            );
            this.rollRequestHistory = requests.sort(
              (a, b) => this.timestampSortValue(a.created_at) - this.timestampSortValue(b.created_at)
            );
            this.unreadMessages = 0;
            this.rebuildInboxFeed();

            for (const req of this.rollRequestHistory) {
              if (req.status === 'pending') {
                this.enqueueRollPrompt(req);
              }
            }
            return;
          }

          for (const whisper of whispers) {
            this.addWhisper(whisper, whisper.sender !== characterName);
          }
          for (const request of requests) {
            this.mergeRollRequestFromHistory(request);
          }
        },
        error: () => {
          if (isCatchUp) return;
          this.whisperHistory = [];
          this.rollRequestHistory = [];
          this.rebuildInboxFeed();
        },
      });
  }

  /** A request we never saw is news; one we already have just updates in place. */
  private mergeRollRequestFromHistory(request: RollRequest): void {
    const existing = request.id
      ? this.rollRequestHistory.find((item) => item.id === request.id)
      : undefined;

    if (!existing) {
      this.addRollRequest(request, true);
      // Asked while offline. It goes in the queue to be answered deliberately —
      // rolling it here would decide the player's advantage for them, on a roll
      // they have not even read yet (#26).
      this.enqueueRollPrompt(request);
      return;
    }

    if (existing.status !== request.status || existing.result !== request.result) {
      this.rollRequestHistory = this.rollRequestHistory.map((item) =>
        item.id === request.id ? request : item
      );
      this.rebuildInboxFeed();
    }

    // The DM moved on — superseding a request cancels it server-side. A prompt still
    // waiting on it is a question about a moment that has passed.
    this.rollPromptQueue = dropStalePrompts(this.rollPromptQueue, request);
    if (this.activeRollPrompt?.id === request.id && !isAwaitingPlayer(request)) {
      this.finishRollPrompt();
    }
  }

  /** Answers the DM in the same thread the whisper arrived on. */
  sendWhisperReply(): void {
    const char = this.charState.activeCharacter();
    const message = this.whisperReply.trim();
    if (!char?.active_campaign || !message || this.isSendingWhisperReply) return;

    this.isSendingWhisperReply = true;
    this.http
      .post<{ whisper: Whisper }>(campaignUrl(char.active_campaign, 'whisper'), {
        sender: char.char_name,
        recipient: 'DM',
        message,
      })
      .subscribe({
        next: (res) => {
          this.isSendingWhisperReply = false;
          this.whisperReply = '';
          // Thread it straight away rather than waiting on the socket echo, which
          // never arrives if the connection happens to be down.
          if (res?.whisper) {
            this.addWhisper(res.whisper, false);
          }
        },
        error: () => {
          this.isSendingWhisperReply = false;
          this.rollToast.showMessage(
            '⚠️ REPLY NOT SENT',
            'Your whisper did not reach the DM — try again.'
          );
        },
      });
  }

  private addWhisper(whisper: Whisper, markUnread: boolean): void {
    if (whisper.id && this.whisperHistory.some((item) => item.id === whisper.id)) return;

    this.whisperHistory = [...this.whisperHistory, whisper].sort(
      (a, b) => this.whisperSortValue(a) - this.whisperSortValue(b)
    );
    this.rebuildInboxFeed();

    if (markUnread && !this.showWhisperInbox()) {
      this.unreadMessages += 1;
    }
  }

  private addRollRequest(request: RollRequest, markUnread: boolean): void {
    if (request.id && this.rollRequestHistory.some((item) => item.id === request.id)) return;

    this.rollRequestHistory = [...this.rollRequestHistory, request].sort(
      (a, b) => this.timestampSortValue(a.created_at) - this.timestampSortValue(b.created_at)
    );
    this.rebuildInboxFeed();

    if (markUnread && !this.showWhisperInbox()) {
      this.unreadMessages += 1;
    }
  }

  private markRollRequestResolved(
    request: RollRequest,
    roll: DiceRoll,
    situationalBonus: number
  ): void {
    if (!request.id) return;

    this.rollRequestHistory = this.rollRequestHistory.map((item) =>
      item.id === request.id
        ? {
            ...item,
            status: 'resolved',
            result: {
              total: roll.total,
              expression: roll.expression,
              raw: roll.raw,
              rolls: roll.rolls,
              modifier: roll.modifier,
              mode: roll.mode,
              situational_bonus: situationalBonus,
            },
          }
        : item
    );
    this.rebuildInboxFeed();
  }

  /**
   * The DM is told how the roll was made, not just what it came to: a 24 on
   * advantage and a 24 on a straight d20 are different facts at the table.
   */
  private submitRollRequestResult(
    request: RollRequest,
    roll: DiceRoll,
    situationalBonus: number
  ): void {
    const char = this.charState.activeCharacter();
    if (!char?.active_campaign || !request.id) return;

    this.http
      .post(campaignUrl(char.active_campaign, `roll-request/${request.id}/result`), {
        total: roll.total,
        expression: roll.expression,
        raw: roll.raw,
        rolls: roll.rolls,
        modifier: roll.modifier,
        // `roll.mode` is the mode the dice service actually applied, which is not
        // always the one asked for — advantage is meaningless on anything but a d20.
        mode: roll.mode,
        situational_bonus: situationalBonus,
      })
      .subscribe({
        error: () =>
          this.rollToast.showMessage(
            '⚠️ ROLL RESULT NOT SENT',
            'The roll completed locally, but the DM did not receive the result.'
          ),
      });
  }

  /** Local status first, then the DM's board — the player should not wait on a POST. */
  private markRollRequestMissed(request: RollRequest): void {
    if (!request.id) return;

    this.rollRequestHistory = this.rollRequestHistory.map((item) =>
      item.id === request.id ? { ...item, status: 'missed' } : item
    );
    this.rebuildInboxFeed();

    const char = this.charState.activeCharacter();
    if (!char?.active_campaign) return;

    this.http
      .post(campaignUrl(char.active_campaign, `roll-request/${request.id}/miss`), {})
      // Deliberately quiet: the player already knows they skipped it, and a failure
      // toast about a roll they chose not to make is noise. The cost of a lost POST
      // is that the DM's board keeps showing "waiting", which is what it showed
      // before this feature existed.
      .subscribe({ error: () => undefined });
  }

  /** Both sides of this hero's thread with the DM, plus table-wide announcements. */
  private isWhisperForCharacter(whisper: Whisper | undefined, characterName: string): boolean {
    return (
      !!whisper &&
      (whisper.recipient === characterName ||
        whisper.recipient === 'All' ||
        whisper.sender === characterName)
    );
  }

  isOwnWhisper(whisper: Whisper): boolean {
    return whisper.sender === this.charState.activeCharacter()?.char_name;
  }

  private whisperSortValue(whisper: Whisper): number {
    return this.timestampSortValue(whisper.timestamp);
  }

  private timestampSortValue(timestamp?: string): number {
    if (!timestamp) return 0;
    const normalized = timestamp.includes('T')
      ? timestamp
      : `${timestamp.replace(' ', 'T')}Z`;
    const value = new Date(normalized).getTime();
    return Number.isNaN(value) ? 0 : value;
  }

  private isRollRequestForCharacter(request: RollRequest | undefined, char: CharacterSchema): boolean {
    if (!request) return false;
    const raw = (request.char_filename || '').replace(/\.json$/i, '');
    const charId = char.char_id || '';
    const matchesFilename =
      !!charId &&
      !!raw &&
      (raw === charId || raw.endsWith(`_${charId}`) || raw.split('_').pop() === charId);
    return matchesFilename || request.char_name === char.char_name;
  }

  private isRollRequestForCharacterName(request: RollRequest | undefined, characterName: string): boolean {
    return !!request && request.char_name === characterName;
  }

  joinCampaign() {
    const char = this.charState.activeCharacter();
    if (!char || !this.joinInviteCode) return;

    this.http.post<any>(`${environment.apiBaseUrl}/campaigns/join`, {
      invite_code: this.joinInviteCode.toUpperCase(),
      char_filename: `${char.char_name.toLowerCase().replace(/\s+/g, '_')}_${char.char_id}.json`,
      character_id: char.char_id
    }).subscribe({
      next: (res) => {
        this.showJoinModal.set(false);
        // The backend already updated the character's active_campaign.
        // We just need to reload from the server to get the fresh state (and correct version number).
        this.charState.loadCharacters().subscribe();
        this.loadedCampaignMessageKey = null;
        this.rollToast.showMessage('🏰 CAMPAIGN JOINED', `Joined campaign "${res.campaign_name}" successfully!`);
      },
      error: (err) => this.rollToast.showMessage('⚠️ JOIN FAILED', err.error?.detail || 'Failed to join campaign.')
    });
  }

  onSelectCharacter(charId: string) {
    if (!charId) return;
    const success = this.charState.selectCharacter(charId);
    if (!success) {
      this.rollToast.showMessage('⚠️ EDITION MISMATCH', 'You can only select characters matching the active edition mode!');
    }
  }

  openConditionsModal() {
    this.showConditionsModal.set(true);
  }

  saveConditions(data: { conditions: string[], concentratingOn: string }) {
    const char = this.charState.activeCharacter();
    if (!char) return;
    const updated = {
      ...char,
      conditions: data.conditions,
      concentrating_on: data.concentratingOn
    };
    this.charState.activeCharacter.set(updated);
    if (this.isInVault(updated)) {
      this.localSaveVersion++;
      this.hpSave$.next({ char: updated, version: this.localSaveVersion });
    }
    this.showConditionsModal.set(false);
  }

  openEditModal() {
    const char = this.charState.activeCharacter();
    if (char) {
      this.editDraftChar = JSON.parse(JSON.stringify(char));
      this.showEditModal.set(true);
    }
  }

  saveEditModal() {
    if (this.editDraftChar) {
      this.charState.activeCharacter.set(JSON.parse(JSON.stringify(this.editDraftChar)));
      this.showEditModal.set(false);
      this.saveCurrentChar(true);
      this.editDraftChar = null;
    }
  }

  openImportModal(): void {
    this.importError.set(null);
    this.importWarnings.set([]);
    this.dndBeyondUrl = '';
    this.showImportModal.set(true);
  }

  closeImportModal(): void {
    this.showImportModal.set(false);
  }

  onImportPdf(event: Event): void {
    const input = event.target as HTMLInputElement;
    if (!input.files || input.files.length === 0) return;
    const file = input.files[0];
    const formData = new FormData();
    formData.append('file', file);

    this.isImporting.set(true);
    this.importError.set(null);
    this.importWarnings.set([]);

    this.http.post<any>(`${environment.apiBaseUrl}/characters/import-pdf`, formData)
      .subscribe({
        next: (res) => {
          this.isImporting.set(false);
          this.charState.loadCharacters().subscribe(() => {
            this.charState.activeCharacter.set(res);
          });
          if (res.warnings && res.warnings.length > 0) {
            this.importWarnings.set(res.warnings);
          } else {
            this.closeImportModal();
          }
          this.rollToast.showMessage('CHARACTER IMPORTED', `Successfully imported ${res.char_name || 'hero'}.`);
          input.value = '';
        },
        error: (err) => {
          this.isImporting.set(false);
          const detail = err.error?.detail || 'Failed to import character from PDF.';
          this.importError.set(detail);
          input.value = '';
        }
      });
  }

  onImportDndBeyond(): void {
    const url = this.dndBeyondUrl.trim();
    if (!url) return;

    this.isImporting.set(true);
    this.importError.set(null);
    this.importWarnings.set([]);

    this.http.post<any>(`${environment.apiBaseUrl}/characters/import-dndbeyond`, { url_or_id: url })
      .subscribe({
        next: (res) => {
          this.isImporting.set(false);
          this.charState.loadCharacters().subscribe(() => {
            this.charState.activeCharacter.set(res);
          });
          if (res.warnings && res.warnings.length > 0) {
            this.importWarnings.set(res.warnings);
          } else {
            this.closeImportModal();
          }
          this.rollToast.showMessage('CHARACTER IMPORTED', `Successfully imported ${res.char_name || 'hero'} from D&D Beyond.`);
        },
        error: (err) => {
          this.isImporting.set(false);
          const detail = err.error?.detail || 'Failed to import character from D&D Beyond.';
          this.importError.set(detail);
        }
      });
  }

  onImportFoundry(event: Event): void {
    const input = event.target as HTMLInputElement;
    if (!input.files || input.files.length === 0) return;
    const file = input.files[0];
    const formData = new FormData();
    formData.append('file', file);

    this.isImporting.set(true);
    this.importError.set(null);
    this.importWarnings.set([]);

    this.http.post<any>(`${environment.apiBaseUrl}/characters/import-foundry`, formData)
      .subscribe({
        next: (res) => {
          this.isImporting.set(false);
          this.charState.loadCharacters().subscribe(() => {
            this.charState.activeCharacter.set(res);
          });
          if (res.warnings && res.warnings.length > 0) {
            this.importWarnings.set(res.warnings);
          } else {
            this.closeImportModal();
          }
          this.rollToast.showMessage('CHARACTER IMPORTED', `Successfully imported ${res.char_name || 'hero'} from Foundry VTT.`);
          input.value = '';
        },
        error: (err) => {
          this.isImporting.set(false);
          const detail = err.error?.detail || 'Failed to import character from Foundry.';
          this.importError.set(detail);
          input.value = '';
        }
      });
  }

  reportWhisper(whisper: Whisper): void {
    const char = this.charState.activeCharacter();
    if (!char?.active_campaign || !whisper.id) return;
    const reason = window.prompt('Please enter the reason for reporting this message:');
    if (!reason || !reason.trim()) return;

    this.http.post<{ success: boolean; message: string }>(
      `${environment.apiBaseUrl}/campaigns/${char.active_campaign}/whispers/${whisper.id}/report`,
      { reason: reason.trim() }
    ).subscribe({
      next: () => {
        whisper.has_open_report = true;
        this.rollToast.showMessage('REPORT SUBMITTED', 'Whisper has been reported to moderators.');
      },
      error: (err) => {
        const detail = err.error?.detail || 'Failed to submit report.';
        this.rollToast.showMessage('REPORT FAILED', detail);
      }
    });
  }

  toggleEditMode() {
    this.editMode.set(!this.editMode());
    if (!this.editMode()) {
      this.saveCurrentChar(true);
    }
  }

  onDeleteHero() {
    const char = this.charState.activeCharacter();
    if (!char || !char.char_id) return;

    if (confirm(`Are you sure you want to permanently delete ${char.char_name}? This action cannot be undone.`)) {
      this.charState.deleteCharacter(char.char_id).subscribe({
        next: () => {
          this.rollToast.showMessage('🗑️ HERO DELETED', `${char.char_name} has been permanently deleted.`);
        },
        error: (err) => {
          console.error('Failed to delete character', err);
          this.rollToast.showMessage('❌ ERROR', 'Failed to delete character.');
        }
      });
    }
  }

  saveCurrentChar(showToast = false) {
    const char = this.charState.activeCharacter();
    if (!char) return;

    const copy = { ...char };
    this.charState.activeCharacter.set(copy);

    if (!this.isInVault(copy)) {
      this.createInVault(copy, showToast, '💾 HERO FORGED');
      return;
    }

    this.charState.updateCharacter(copy.char_id!, copy).subscribe({
      next: () => {
        if (showToast) {
          this.rollToast.showMessage('💾 SHEET SAVED', `Saved changes for ${copy.char_name}.`);
        }
      },
      // Only a missing record justifies creating one. Any other failure is a real
      // error, and forging a duplicate hero out of it would make things worse.
      error: (err) => {
        if (err?.status === 404) {
          this.createInVault(copy, showToast, '💾 SHEET SAVED');
        } else {
          this.rollToast.showMessage(
            '⚠️ SAVE FAILED',
            `Could not save ${copy.char_name}. Your changes are still on screen — try again.`
          );
        }
      }
    });
  }

  /** A hero without an id, or the built-in fallback, has no vault record yet. */
  private isInVault(char: CharacterSchema): boolean {
    return !!char.char_id && char.char_id !== 'default_paladin';
  }

  private createInVault(char: CharacterSchema, showToast: boolean, title: string) {
    this.charState.saveCharacter(char).subscribe({
      next: () => {
        if (showToast) {
          this.rollToast.showMessage(title, `Saved ${char.char_name} to vault.`);
        }
      },
      error: () =>
        this.rollToast.showMessage('⚠️ SAVE FAILED', `Could not save ${char.char_name} to vault.`)
    });
  }

  // --- In-Person Companion & Turn Methods (#170, #175) ---
  get isMyTurn(): boolean {
    const char = this.charState.activeCharacter();
    if (!char || !this.encounterState?.combatants?.length) return false;
    const active = this.encounterState.combatants.find(
      (c: any) => c.id === this.encounterState.activeCombatantId
    );
    return active ? (active.name || '').toLowerCase() === (char.char_name || '').toLowerCase() : false;
  }

  get isOnDeck(): boolean {
    const char = this.charState.activeCharacter();
    if (!char || !this.encounterState?.combatants?.length || this.isMyTurn) return false;
    const combatants = this.encounterState.combatants;
    const activeIdx = combatants.findIndex((c: any) => c.id === this.encounterState.activeCombatantId);
    if (activeIdx < 0) return false;
    const nextIdx = (activeIdx + 1) % combatants.length;
    const next = combatants[nextIdx];
    return next ? (next.name || '').toLowerCase() === (char.char_name || '').toLowerCase() : false;
  }

  toggleCompanionMode() {
    this.haptics.lightTap();
    if (this.companionModeOverride() === null) {
      this.companionModeOverride.set(!this.isMobileViewport());
    } else {
      this.companionModeOverride.set(!this.companionModeOverride());
    }
  }

  selectMobileTab(tab: 'hero' | 'combat' | 'skills' | 'spells' | 'table') {
    this.haptics.lightTap();
    this.mobileActiveTab.set(tab);
    if (tab === 'combat') this.selectSheetSubTab('combat');
    else if (tab === 'skills') this.selectSheetSubTab('skills');
    else if (tab === 'spells') this.selectSheetSubTab('spells');
    else if (tab === 'table') {
      this.selectSheetSubTab('roleplay');
      this.unreadMessages = 0;
    }
  }

  applyDamage(amount: number) {
    const char = this.charState.activeCharacter();
    if (!char || amount <= 0) return;
    this.haptics.damageTaken();

    const currentTemp = char.hp_temp || 0;
    let remainingDamage = amount;
    let newTemp = currentTemp;

    if (currentTemp > 0) {
      if (remainingDamage >= currentTemp) {
        remainingDamage -= currentTemp;
        newTemp = 0;
      } else {
        newTemp = currentTemp - remainingDamage;
        remainingDamage = 0;
      }
    }

    const currentHp = char.hp_current ?? char.hp_max;
    const newHp = Math.max(0, currentHp - remainingDamage);
    const updated = { ...char, hp_current: newHp, hp_temp: newTemp };
    this.charState.activeCharacter.set(updated);

    if (this.isInVault(updated)) {
      this.localSaveVersion++;
      this.hpSave$.next({ char: updated, version: this.localSaveVersion });
    }

    // Trigger Concentration Check if character was concentrating (even when Temp HP absorbs the hit)
    if (char.concentrating_on && amount > 0) {
      const dc = Math.max(10, Math.floor(amount / 2));
      this.concentrationDc.set(dc);
      this.showConcentrationPrompt.set(true);
    }
  }

  applyHeal(amount: number) {
    const char = this.charState.activeCharacter();
    if (!char || amount <= 0) return;
    this.haptics.lightTap();

    const currentHp = char.hp_current ?? char.hp_max;
    const newHp = Math.min(char.hp_max, currentHp + amount);
    const updated = {
      ...char,
      hp_current: newHp,
      death_saves: currentHp === 0 ? { successes: 0, failures: 0 } : char.death_saves,
    };
    this.charState.activeCharacter.set(updated);

    if (this.isInVault(updated)) {
      this.localSaveVersion++;
      this.hpSave$.next({ char: updated, version: this.localSaveVersion });
    }
  }

  setTempHp(amount: number) {
    const char = this.charState.activeCharacter();
    if (!char) return;
    this.haptics.lightTap();
    const updated = { ...char, hp_temp: Math.max(0, amount) };
    this.charState.activeCharacter.set(updated);
    if (this.isInVault(updated)) {
      this.localSaveVersion++;
      this.hpSave$.next({ char: updated, version: this.localSaveVersion });
    }
  }

  rollDeathSave() {
    const char = this.charState.activeCharacter();
    if (!char) return;
    const roll = this.dice.roll({ numDice: 1, sides: 20, modifier: 0 });
    const currentSaves = { ...(char.death_saves || { successes: 0, failures: 0 }) };
    let newHp = char.hp_current;

    if (roll.raw === 20) {
      this.haptics.critSuccess();
      newHp = 1;
      currentSaves.successes = 0;
      currentSaves.failures = 0;
      this.rollToast.showMessage('🌟 NATURAL 20 ON DEATH SAVE!', 'You regain consciousness with 1 HP!');
    } else if (roll.raw === 1) {
      this.haptics.critFail();
      currentSaves.failures = Math.min(3, currentSaves.failures + 2);
      this.rollToast.showMessage('💀 CRITICAL FAILURE!', 'Natural 1: You take 2 Death Save Failures!');
    } else if (roll.raw >= 10) {
      this.haptics.lightTap();
      currentSaves.successes = Math.min(3, currentSaves.successes + 1);
      this.rollToast.showMessage('✨ DEATH SAVE SUCCESS!', `Rolled ${roll.raw} (Successes: ${currentSaves.successes}/3)`);
    } else {
      this.haptics.critFail();
      currentSaves.failures = Math.min(3, currentSaves.failures + 1);
      this.rollToast.showMessage('❌ DEATH SAVE FAILURE!', `Rolled ${roll.raw} (Failures: ${currentSaves.failures}/3)`);
    }

    const updated: CharacterSchema = {
      ...char,
      hp_current: newHp,
      death_saves: currentSaves,
    };
    this.charState.activeCharacter.set(updated);
    this.saveCurrentChar();
  }

  rollConcentrationSave() {
    const char = this.charState.activeCharacter();
    if (!char) return;
    const saveMod = char.stats ? savingThrowModifier(char, 'CON') : conModifier(char);
    const roll = this.dice.rollD20(saveMod, this.rollMode);
    const dc = this.concentrationDc();

    if (roll.total >= dc) {
      this.haptics.critSuccess();
      this.rollToast.showMessage('🧠 CONCENTRATION MAINTAINED', `Rolled ${roll.total} vs DC ${dc} — concentration held!`);
      this.showConcentrationPrompt.set(false);
    } else {
      this.haptics.critFail();
      this.rollToast.showMessage('💥 CONCENTRATION BROKEN', `Rolled ${roll.total} vs DC ${dc} — concentration dropped.`);
      this.dropConcentration();
    }
  }

  dropConcentration() {
    const char = this.charState.activeCharacter();
    if (!char) return;
    const updated: CharacterSchema = { ...char, concentrating_on: undefined };
    this.charState.activeCharacter.set(updated);
    this.saveCurrentChar();
    this.showConcentrationPrompt.set(false);
  }

  onCastSpell(event: { spellName: string; level: number; isRitual: boolean }) {
    const char = this.charState.activeCharacter();
    if (!char) return;
    this.haptics.lightTap();
    const lvlText = event.level === 0 ? 'Cantrip' : (event.isRitual ? 'Ritual' : `Level ${event.level}`);
    this.rollToast.showMessage('✨ CAST SPELL', `${char.char_name} cast ${event.spellName} (${lvlText})`);
  }

  onConsumePotion(event: { item: EquipmentItem; dice: string; bonus: number; name: string }) {
    const char = this.charState.activeCharacter();
    if (!char) return;
    this.haptics.lightTap();
    const numDice = parseInt(event.dice.split('d')[0], 10) || 2;
    const roll = this.dice.roll({ numDice, sides: 4, modifier: event.bonus });

    const currentHp = char.hp_current ?? char.hp_max;
    const newHp = Math.min(char.hp_max, currentHp + roll.total);

    const currentEquipment = char.equipment || [];
    const currentQty = event.item.quantity ?? 1;
    const updatedEquipment =
      currentQty <= 1
        ? currentEquipment.filter((eq) => eq !== event.item)
        : currentEquipment.map((eq) =>
            eq === event.item ? { ...eq, quantity: currentQty - 1 } : eq
          );

    const updated: CharacterSchema = {
      ...char,
      hp_current: newHp,
      death_saves: currentHp === 0 ? { successes: 0, failures: 0 } : char.death_saves,
      equipment: updatedEquipment,
    };
    this.charState.activeCharacter.set(updated);
    this.saveCurrentChar();
    this.rollToast.showMessage('🧪 DRANK POTION', `Healed for +${roll.total} HP! (${event.name})`);
  }

  sendQuickWhisper(text: string) {
    this.whisperReply = text;
    this.sendWhisperReply();
  }

  onCustomRoll(event: {
    title: string;
    expression: string;
    total: number;
    rolls: number[];
    modifier: number;
    broadcast: boolean;
  }) {
    const char = this.charState.activeCharacter();
    if (!event.broadcast || !char?.active_campaign) return;

    this.http
      .post<{ whisper: Whisper }>(campaignUrl(char.active_campaign, 'whisper'), {
        sender: char.char_name,
        recipient: 'DM',
        message: `${event.title}: ${event.expression} = ${event.total} [${event.rolls.join(', ')}]`,
      })
      .subscribe({
        next: (res) => {
          if (res?.whisper) {
            this.addWhisper(res.whisper, false);
          }
        },
        error: () => undefined,
      });
  }

  adjustHp(delta: number) {
    const char = this.charState.activeCharacter();
    if (!char) return;
    const updated = { ...char, hp_current: adjustedHp(char, delta) };
    this.charState.activeCharacter.set(updated);
    if (this.isInVault(updated)) {
      this.localSaveVersion++;
      this.hpSave$.next({ char: updated, version: this.localSaveVersion });
    }
  }

  adjustTempHp(delta: number) {
    const char = this.charState.activeCharacter();
    if (!char) return;
    const newTemp = Math.max(0, (char.hp_temp || 0) + delta);
    const updated = { ...char, hp_temp: newTemp };
    this.charState.activeCharacter.set(updated);
    if (this.isInVault(updated)) {
      this.localSaveVersion++;
      this.hpSave$.next({ char: updated, version: this.localSaveVersion });
    }
  }

  setDeathSave(type: 'successes' | 'failures', value: number) {
    const char = this.charState.activeCharacter();
    if (!char) return;
    const updated = {
      ...char,
      death_saves: { ...(char.death_saves || { successes: 0, failures: 0 }) }
    };
    updated.death_saves[type] = Math.max(0, Math.min(3, value));
    this.charState.activeCharacter.set(updated);
    if (this.isInVault(updated)) {
      this.localSaveVersion++;
      this.hpSave$.next({ char: updated, version: this.localSaveVersion });
    }
  }

  addWeapon() {
    const char = this.charState.activeCharacter();
    if (!char) return;
    if (!char.weapons) char.weapons = [];
    char.weapons.push({ name: 'New Weapon', attack_bonus: '+5', damage_dice: '1d8+3' });
    this.saveCurrentChar();
  }

  deleteWeapon(index: number) {
    const char = this.charState.activeCharacter();
    if (!char || !char.weapons) return;
    char.weapons.splice(index, 1);
    this.saveCurrentChar();
  }

  addEquipment() {
    const char = this.charState.activeCharacter();
    if (!char) return;
    if (!char.equipment) char.equipment = [];
    char.equipment.push({ name: 'New Item', equipped: false });
    this.saveCurrentChar();
  }

  deleteEquipment(index: number) {
    const char = this.charState.activeCharacter();
    if (!char || !char.equipment) return;
    char.equipment.splice(index, 1);
    this.saveCurrentChar();
  }

  toggleEquipped(item: EquipmentItem) {
    item.equipped = !item.equipped;
    this.saveCurrentChar();
  }

  getPortraitUrl(char: any): string {
    if (char && char.char_portrait && !char.char_portrait.includes('anvil.png')) {
      return char.char_portrait;
    }
    const className = (char?.char_class || '').toLowerCase();
    if (className.includes('paladin') || className.includes('fighter') || className.includes('barbarian')) {
      return 'https://image.pollinations.ai/prompt/sir%20valeros%20dnd%20paladin%20knight%20in%20shining%20armor%20cinematic%20portrait?width=300&height=300&nologo=true';
    } else if (className.includes('wizard') || className.includes('sorcerer') || className.includes('warlock') || className.includes('mage')) {
      return 'https://image.pollinations.ai/prompt/epic%20dnd%20wizard%20archmage%20glowing%20runes%20cinematic%20portrait?width=300&height=300&nologo=true';
    } else if (className.includes('rogue') || className.includes('ranger') || className.includes('monk')) {
      return 'https://image.pollinations.ai/prompt/epic%20dnd%20shadow%20rogue%20assassin%20hooded%20cinematic%20portrait?width=300&height=300&nologo=true';
    }
    return 'https://image.pollinations.ai/prompt/epic%20dnd%20heroic%20paladin%20knight%20in%20shining%20armor%20cinematic%20portrait?width=300&height=300&nologo=true';
  }

  generateAiPortrait() {
    const char = this.charState.activeCharacter();
    if (!char || !char.char_id) return;
    this.http.post<any>(`${environment.apiBaseUrl}/forge/portrait`, {
      char_id: char.char_id,
      prompt: this.portraitPrompt
    }).subscribe((res) => {
      this.showPortraitModal.set(false);
      if (res.portrait_url) {
        if (typeof res.version === 'number') {
          char.version = res.version;
        }
        char.char_portrait = res.portrait_url;
        this.saveCurrentChar();
      }
    });
  }

  onLevelUp() {
    const char = this.charState.activeCharacter();
    if (!char) return;
    const initialClass =
      char.classes && char.classes.length > 0
        ? char.classes[0].class_name
        : char.char_class || 'Fighter';
    this.levelUpUserChoices = { 'level_up_class': initialClass };
    this.http.post<any>(`${environment.apiBaseUrl}/forge/level-up-analysis`, {
      character: char,
      user_choices: this.levelUpUserChoices,
    }).subscribe((analysis) => {
      this.levelUpAnalysis = analysis;
      this.showLevelUpModal.set(true);
    });
  }

  onLevelUpChoicesChange(choices: Record<string, any>) {
    const oldClass = this.levelUpUserChoices['level_up_class'];
    const newClass = choices['level_up_class'];
    this.levelUpUserChoices = choices;

    if (newClass && oldClass !== newClass) {
      const char = this.charState.activeCharacter();
      if (!char) return;
      this.http.post<any>(`${environment.apiBaseUrl}/forge/level-up-analysis`, {
        character: char,
        user_choices: this.levelUpUserChoices
      }).subscribe((analysis) => {
        this.levelUpAnalysis = analysis;
      });
    }
  }

  applyLevelUp() {
    const char = this.charState.activeCharacter();
    if (!char || !this.levelUpAnalysis) return;

    const payload: LevelUpApplyRequest = {
      character_id: char.char_id!,
      analysis: this.levelUpAnalysis,
      user_choices: this.levelUpUserChoices
    };

    this.http.post<CharacterSchema>(`${environment.apiBaseUrl}/forge/level-up-apply`, payload)
      .subscribe({
        next: (syncedChar) => {
          this.charState.activeCharacter.set(syncedChar);
          // Assuming upsertCharacter is a public method or the state relies on a refresh:
          // Just refreshing the character list is safer.
          this.charState.loadCharacters();
          this.showLevelUpModal.set(false);
          this.levelUpAnalysis = null;
          this.levelUpUserChoices = {};
          this.rollToast.showMessage(`⚡ LEVEL UP: ${syncedChar.char_name}`, `Successfully leveled up to ${syncedChar.char_level}!`);
        },
        error: () => this.rollToast.showMessage('⚠️ LEVEL UP FAILED', 'Failed to save leveled up character.')
      });
  }

  onValidateCharacter() {
    const char = this.charState.activeCharacter();
    if (!char) return;
    this.isValidating = true;
    this.validationResult = null;
    this.showValidationModal.set(true);

    this.http.post<any>(`${environment.apiBaseUrl}/rules/validate`, { character: char }).subscribe({
      next: (res) => {
        this.isValidating = false;
        this.validationResult = res.validation_result;
      },
      error: () => {
        this.isValidating = false;
        this.rollToast.showMessage('⚠️ VALIDATION FAILED', 'Failed to validate character build.');
      }
    });
  }

  applyAutoFix() {
    const char = this.charState.activeCharacter();
    if (!char) return;
    this.isAutoFixing = true;

    this.http.post<any>(`${environment.apiBaseUrl}/rules/autofix`, { character: char }).subscribe({
      next: (res) => {
        this.isAutoFixing = false;
        this.showValidationModal.set(false);
        if (res.character) {
          this.charState.activeCharacter.set(res.character);
          this.saveCurrentChar(false);
          this.rollToast.showMessage('✅ HERO AUTO-FIXED', `All rule issues for ${res.character.char_name} have been fixed & synchronized!`);
        }
      },
      error: () => {
        this.isAutoFixing = false;
        this.rollToast.showMessage('⚠️ AUTO-FIX FAILED', 'Failed to auto-fix character build.');
      }
    });
  }

  isGeneratingStrategy = signal(false);

  onGenerateStrategy() {
    const char = this.charState.activeCharacter();
    if (!char) return;
    this.isGeneratingStrategy.set(true);
    this.http.post<any>(`${environment.apiBaseUrl}/forge/playstyle-guide`, char).subscribe({
      next: (res) => {
        this.isGeneratingStrategy.set(false);
        this.strategyGuideText = res.guide_markdown;
      },
      error: () => {
        this.isGeneratingStrategy.set(false);
        this.rollToast.showMessage('⚠️ GENERATION FAILED', 'Failed to generate playstyle guide.');
      }
    });
  }

  onExportPdf() {
    const char = this.charState.activeCharacter();
    if (!char || !char.char_id) return;
    this.rollToast.showMessage('📄 EXPORTING PDF', 'Generating your character sheet...');
    this.http.post(`${environment.apiBaseUrl}/characters/${char.char_id}/export-pdf`, {}, { responseType: 'blob' })
      .subscribe({
        next: (blob) => {
          const url = window.URL.createObjectURL(blob);
          this.pdfPreviewBlobUrl = url;
          this.pdfPreviewUrl = url;
        },
        error: () => this.rollToast.showMessage('⚠️ EXPORT FAILED', 'Failed to generate character sheet.')
      });
  }


  closePdfPreview() {
    if (this.pdfPreviewBlobUrl) {
      window.URL.revokeObjectURL(this.pdfPreviewBlobUrl);
    }
    this.pdfPreviewBlobUrl = null;
    this.pdfPreviewUrl = null;
  }

  getStatsArray(stats: any) {
    if (!stats) return [];
    return Object.keys(stats).map((key) => ({ key, value: stats[key] }));
  }

  getModifierString = (val: number): string => {
    return formatModifier(abilityModifier(val));
  }
}
