import {
  AfterViewChecked,
  Component,
  ElementRef,
  OnDestroy,
  OnInit,
  ViewChild,
  effect,
} from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { HttpClient } from '@angular/common/http';
import { Router } from '@angular/router';
import { EMPTY, Subject, Subscription, catchError, debounceTime, switchMap } from 'rxjs';
import { CharacterStateService } from '../../core/services/character-state.service';
import { DiceRoll, DiceService, RollMode } from '../../core/services/dice.service';
import { RollToastService } from '../../core/services/roll-toast.service';
import { WebSocketService, WsMessage } from '../../core/services/websocket.service';
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
  ForgeButtonDirective,
  ForgeCardComponent,
  ForgeEmptyStateComponent,
  ForgePageComponent,
  ForgeTab,
  ForgeTextareaDirective,
} from '../../shared/ui';
import { PlayerDashboardHeaderComponent } from './player-dashboard-header/player-dashboard-header.component';
import { CharacterOverviewCardComponent } from './character-overview-card/character-overview-card.component';
import { CharacterTabsComponent } from './character-tabs/character-tabs.component';
import { RollModeSelectorComponent } from './roll-mode-selector/roll-mode-selector.component';
import { SkillsPanelComponent } from './skills-panel/skills-panel.component';
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
import { environment } from '../../../environments/environment';

export interface SkillDefinition {
  name: string;
  ability: 'STR' | 'DEX' | 'CON' | 'INT' | 'WIS' | 'CHA';
}

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
  ],
  templateUrl: './player.component.html',
  styleUrl: './player.component.css', 
})
export class PlayerComponent implements OnInit, OnDestroy, AfterViewChecked {
  @ViewChild('whisperFeed') private whisperFeed?: ElementRef<HTMLElement>;

  activeTab: 'sheet' = 'sheet';
  sheetSubTab: 'skills' | 'combat' | 'spells' | 'roleplay' = 'skills';

  readonly sheetTabs: ForgeTab[] = [
    { id: 'skills', label: '📜 Skills & Checks' },
    { id: 'combat', label: '⚔️ Combat & Inventory' },
    { id: 'spells', label: '✨ Spells & Features' },
    { id: 'roleplay', label: '📖 Lore & Roleplay' },
  ];

  selectSheetSubTab(tabId: string): void {
    if (tabId === 'skills' || tabId === 'combat' || tabId === 'spells' || tabId === 'roleplay') {
      this.sheetSubTab = tabId;
    }
  }
  editMode = false;
  showEditModal = false;
  showPortraitModal = false;
  showJoinModal = false;
  showShortRestModal = false;
  showProficientOnly = false;
  showLevelUpModal = false;
  showValidationModal = false;
  showWhisperInbox = false;
  isValidating = false;
  isAutoFixing = false;
  validationResult: any = null;
  levelUpAnalysis: any = null;
  shortRestDiceToSpend = 1;
  joinInviteCode = '';
  rollMode: RollMode = 'normal';

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

  allSkills: SkillDefinition[] = [
    { name: 'Athletics', ability: 'STR' },
    { name: 'Acrobatics', ability: 'DEX' },
    { name: 'Sleight of Hand', ability: 'DEX' },
    { name: 'Stealth', ability: 'DEX' },
    { name: 'Arcana', ability: 'INT' },
    { name: 'History', ability: 'INT' },
    { name: 'Investigation', ability: 'INT' },
    { name: 'Nature', ability: 'INT' },
    { name: 'Religion', ability: 'INT' },
    { name: 'Animal Handling', ability: 'WIS' },
    { name: 'Insight', ability: 'WIS' },
    { name: 'Medicine', ability: 'WIS' },
    { name: 'Perception', ability: 'WIS' },
    { name: 'Survival', ability: 'WIS' },
    { name: 'Deception', ability: 'CHA' },
    { name: 'Intimidation', ability: 'CHA' },
    { name: 'Performance', ability: 'CHA' },
    { name: 'Persuasion', ability: 'CHA' },
  ];

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
  private readonly hpSave$ = new Subject<CharacterSchema>();

  constructor(
    public charState: CharacterStateService,
    private dice: DiceService,
    private rollToast: RollToastService,
    private http: HttpClient,
    private router: Router,
    private wsService: WebSocketService
  ) {
    this.hpSave$
      .pipe(
        debounceTime(700),
        // switchMap aborts a still-flying save, so a stale response can never
        // overwrite the HP the user just clicked to.
        switchMap((char) =>
          this.charState
            .updateCharacter(char.char_id!, char)
            .pipe(catchError(() => EMPTY))
        ),
        takeUntilDestroyed()
      )
      .subscribe();

    effect(() => {
      const char = this.charState.activeCharacter();
      if (char && char.active_campaign) {
        // The character rides along on the handshake so the server can route
        // private whispers and roll requests to this hero alone.
        this.wsService.connect(char.active_campaign, {
          role: 'player',
          character: char.char_name,
        });
        this.loadCampaignMessageHistory(char.active_campaign, char.char_name);
      } else {
        this.wsService.disconnect();
        this.whisperHistory = [];
        this.rollRequestHistory = [];
        this.unreadMessages = 0;
        this.whisperReply = '';
        this.showWhisperInbox = false;
        this.loadedCampaignMessageKey = null;
        this.clearRollPrompts();
        this.rebuildInboxFeed();
      }
    });
  }

  ngOnInit() {
    this.charState.ensureLoaded().subscribe();

    // Every (re)connect re-reads the thread, so a dropped socket costs nothing
    // and the hero never has to reload the page to see what the DM sent.
    this.openedSub = this.wsService.opened$.subscribe((campaignName) => {
      const char = this.charState.activeCharacter();
      if (char?.active_campaign === campaignName) {
        this.loadCampaignMessageHistory(campaignName, char.char_name, true);
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
      } else if (msg.type === 'party_update') {
        this.applyDmPartyUpdate(msg['payload'], char);
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
    if (typeof payload.hp_current === 'number') char.hp_current = payload.hp_current;
    if (Array.isArray(payload.conditions)) char.conditions = [...payload.conditions];

    const hp = char.hp_current ?? char.hp_max;
    if (hp !== previousHp) {
      const delta = hp - previousHp;
      const verb = delta < 0 ? `took ${Math.abs(delta)} damage` : `healed ${delta}`;
      this.rollToast.showMessage('❤️ DM UPDATED YOUR HP', `You ${verb} — now ${hp}/${char.hp_max}.`);
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
    if (showProficientOnly === this.showProficientOnly) return;
    this.showProficientOnly = showProficientOnly;

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

  getSkillsByAttribute(attr: string): SkillDefinition[] {
    return this.allSkills.filter((s) => s.ability === attr);
  }

  getAttributeFullName(attr: string): string {
    const names: { [key: string]: string } = {
      STR: 'Strength',
      DEX: 'Dexterity',
      INT: 'Intelligence',
      WIS: 'Wisdom',
      CHA: 'Charisma'
    };
    return names[attr] || attr;
  }

  getAttributeModifier(attr: string): string {
    const char = this.charState.activeCharacter();
    const value = char?.stats?.[attr] || 10;
    return this.getModifierString(value);
  }

  goToForge() {
    this.router.navigate(['/forge']);
  }

  getClassHitDieSize(): number {
    const char = this.charState.activeCharacter();
    const c = (char?.char_class || '').toLowerCase();
    if (c.includes('barbarian')) return 12;
    if (c.includes('fighter') || c.includes('paladin') || c.includes('ranger')) return 10;
    if (c.includes('sorcerer') || c.includes('wizard')) return 6;
    return 8; // Bard, Cleric, Druid, Monk, Rogue, Warlock
  }

  getConModifier(): number {
    const char = this.charState.activeCharacter();
    const conVal = char?.stats?.['CON'] || 10;
    return Math.floor((conVal - 10) / 2);
  }

  getAvailableHitDice(): number {
    const char = this.charState.activeCharacter();
    if (!char) return 0;
    const total = char.char_level || 1;
    const used = char.hit_dice_used || 0;
    return Math.max(0, total - used);
  }

  openShortRestModal() {
    this.shortRestDiceToSpend = 1;
    this.showShortRestModal = true;
  }

  executeShortRest() {
    const char = this.charState.activeCharacter();
    if (!char) return;
    const available = this.getAvailableHitDice();
    if (available <= 0) return;

    const count = Math.min(available, Math.max(1, this.shortRestDiceToSpend));
    const dieSize = this.getClassHitDieSize();
    const conMod = this.getConModifier();

    const conBonus = conMod * count;
    const roll = this.dice.roll({ numDice: count, sides: dieSize, modifier: conBonus });
    const totalHealed = Math.max(0, roll.total);

    const oldHp = char.hp_current ?? char.hp_max;
    const newHp = Math.min(char.hp_max, oldHp + totalHealed);

    char.hp_current = newHp;
    char.hit_dice_used = (char.hit_dice_used || 0) + count;

    if (char.char_class.toLowerCase().includes('warlock') && char.spell_slots) {
      Object.keys(char.spell_slots).forEach((key) => {
        if (char.spell_slots) char.spell_slots[key].used = 0;
      });
    }

    this.saveCurrentChar();
    this.showShortRestModal = false;

    this.rollToast.showRoll({
      title: `⛺ SHORT REST HEAL (${count}d${dieSize})`,
      // Every hit die is worth showing here, so this spells them out rather than
      // using the service's summed form.
      expression: `${count}d${dieSize} (${roll.rolls.join(', ')}) ${this.dice.signed(conBonus)}`,
      raw: roll.raw,
      rolls: roll.rolls,
      sides: dieSize,
      modifier: conBonus,
      total: totalHealed,
      message: `Healed for +${totalHealed} HP! (${oldHp} ➡️ ${newHp})`
    });
  }

  triggerLongRest() {
    const char = this.charState.activeCharacter();
    if (!char) return;
    char.hp_current = char.hp_max;

    const totalHd = char.char_level || 1;
    const currentUsed = char.hit_dice_used || 0;
    const recoverCount = Math.floor(totalHd / 2) || 1;
    char.hit_dice_used = Math.max(0, currentUsed - recoverCount);

    if (char.spell_slots) {
      Object.keys(char.spell_slots).forEach((key) => {
        if (char.spell_slots) char.spell_slots[key].used = 0;
      });
    }
    this.saveCurrentChar();
    this.rollToast.showMessage('🌙 LONG REST COMPLETED', `Full HP, spell slots, and ${recoverCount} Hit Dice restored for ${char.char_name}.`);
  }

  getSpellSlotMax(lvl: number): number {
    const char = this.charState.activeCharacter();
    return char?.spell_slots?.[`level_${lvl}`]?.max || 0;
  }

  getSpellSlotUsed(lvl: number): number {
    const char = this.charState.activeCharacter();
    return char?.spell_slots?.[`level_${lvl}`]?.used || 0;
  }

  useSpellSlot(lvl: number) {
    const char = this.charState.activeCharacter();
    if (!char) return;
    if (!char.spell_slots) char.spell_slots = {};
    const key = `level_${lvl}`;
    if (!char.spell_slots[key]) char.spell_slots[key] = { max: 4, used: 0 };
    char.spell_slots[key].used = Math.min(char.spell_slots[key].max, char.spell_slots[key].used + 1);
    this.saveCurrentChar();
  }

  restoreSpellSlot(lvl: number) {
    const char = this.charState.activeCharacter();
    if (!char || !char.spell_slots) return;
    const key = `level_${lvl}`;
    if (char.spell_slots[key]) {
      char.spell_slots[key].used = Math.max(0, char.spell_slots[key].used - 1);
      this.saveCurrentChar();
    }
  }

  isProficient(skillName: string): boolean {
    const char = this.charState.activeCharacter();
    return char?.skill_proficiencies?.includes(skillName) || false;
  }

  getSkillModifier(skill: SkillDefinition): number {
    const char = this.charState.activeCharacter();
    if (!char || !char.stats) return 0;
    const statVal = char.stats[skill.ability] || 10;
    const statMod = Math.floor((statVal - 10) / 2);
    const profBonus = char.proficiency_bonus || 2;
    const isProf = this.isProficient(skill.name);
    return statMod + (isProf ? profBonus : 0);
  }

  getSkillModString(skill: SkillDefinition): string {
    const mod = this.getSkillModifier(skill);
    return mod >= 0 ? `+${mod}` : `${mod}`;
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
    const val = char.stats[stat] || 10;
    const mod = Math.floor((val - 10) / 2);

    return this.showD20Roll(`🎲 ${stat} CHECK`, mod);
  }

  rollSavingThrow(stat: string) {
    const char = this.charState.activeCharacter();
    if (!char || !char.stats) return;
    const val = char.stats[stat] || 10;
    const mod = Math.floor((val - 10) / 2);
    const isSaveProf = char.saving_throws?.includes(stat);
    const profBonus = char.proficiency_bonus || 2;

    return this.showD20Roll(`🛡️ ${stat} SAVING THROW`, mod + (isSaveProf ? profBonus : 0));
  }

  /**
   * Reads the DM's `roll_type` + `stat` off this hero's sheet without throwing
   * anything. The prompt needs the modifier to show the player what they are about
   * to roll, and the roll itself needs the same number — so it is worked out once.
   */
  private resolveRollTarget(rollType: string, stat: string): RollTarget | null {
    const char = this.charState.activeCharacter();
    if (!char || !char.stats) return null;

    const abilityModifier = (ability: string) =>
      Math.floor(((char.stats?.[ability] || 10) - 10) / 2);

    const normalizedType = rollType.toLowerCase().replace(/[\s-]+/g, '_');

    if (normalizedType === 'save' || normalizedType === 'saving_throw' || normalizedType === 'savingthrow') {
      const isSaveProf = char.saving_throws?.includes(stat);
      const profBonus = char.proficiency_bonus || 2;
      return {
        title: `🛡️ ${stat} SAVING THROW`,
        label: `${stat} saving throw`,
        modifier: abilityModifier(stat) + (isSaveProf ? profBonus : 0),
      };
    }

    if (normalizedType === 'skill' || normalizedType === 'skill_check') {
      const skill = this.allSkills.find((s) => s.name.toLowerCase() === stat.toLowerCase());
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
      modifier: abilityModifier(stat),
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
    this.showWhisperInbox = !this.showWhisperInbox;
    if (this.showWhisperInbox) {
      this.unreadMessages = 0;
      this.pendingFeedScroll = true;
    }
  }

  closeWhisperInbox(): void {
    this.showWhisperInbox = false;
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

    if (markUnread && !this.showWhisperInbox) {
      this.unreadMessages += 1;
    }
  }

  private addRollRequest(request: RollRequest, markUnread: boolean): void {
    if (request.id && this.rollRequestHistory.some((item) => item.id === request.id)) return;

    this.rollRequestHistory = [...this.rollRequestHistory, request].sort(
      (a, b) => this.timestampSortValue(a.created_at) - this.timestampSortValue(b.created_at)
    );
    this.rebuildInboxFeed();

    if (markUnread && !this.showWhisperInbox) {
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
    const requestedCharId = request.char_filename?.replace('.json', '').split('_').pop();
    return (
      (!!requestedCharId && requestedCharId === char.char_id) ||
      request.char_name === char.char_name
    );
  }

  private isRollRequestForCharacterName(request: RollRequest | undefined, characterName: string): boolean {
    return !!request && request.char_name === characterName;
  }

  joinCampaign() {
    const char = this.charState.activeCharacter();
    if (!char || !this.joinInviteCode) return;

    this.http.post<any>(`${environment.apiBaseUrl}/campaigns/join`, {
      invite_code: this.joinInviteCode.toUpperCase(),
      char_filename: `${char.char_name.toLowerCase()}_${char.char_id}.json`
    }).subscribe({
      next: (res) => {
        this.showJoinModal = false;
        char.active_campaign = res.campaign_name;
        this.saveCurrentChar();
        this.loadedCampaignMessageKey = null;
        this.loadCampaignMessageHistory(res.campaign_name, char.char_name);
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

  openEditModal() {
    this.showEditModal = true;
  }

  saveEditModal() {
    this.showEditModal = false;
    this.saveCurrentChar(true);
  }

  toggleEditMode() {
    this.editMode = !this.editMode;
    if (!this.editMode) {
      this.saveCurrentChar(true);
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

  adjustHp(delta: number) {
    const char = this.charState.activeCharacter();
    if (!char) return;
    const current = char.hp_current ?? char.hp_max;
    const updatedHp = Math.max(0, Math.min(char.hp_max, current + delta));
    const updated = { ...char, hp_current: updatedHp };
    this.charState.activeCharacter.set(updated);
    if (this.isInVault(updated)) {
      this.hpSave$.next(updated);
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
      this.showPortraitModal = false;
      if (res.portrait_url) {
        char.char_portrait = res.portrait_url;
        this.saveCurrentChar();
      }
    });
  }

  onLevelUp() {
    const char = this.charState.activeCharacter();
    if (!char) return;
    this.http.post<any>(`${environment.apiBaseUrl}/forge/level-up-analysis`, {
      character: char
    }).subscribe((analysis) => {
      this.levelUpAnalysis = analysis;
      this.showLevelUpModal = true;
    });
  }

  applyLevelUp() {
    const char = this.charState.activeCharacter();
    if (!char || !this.levelUpAnalysis) return;

    // Apply basic stat changes
    char.char_level = (char.char_level || 1) + 1;
    char.hp_max = this.levelUpAnalysis.new_total_hp;
    char.hp_current = char.hp_max;

    // Apply new features
    if (this.levelUpAnalysis.new_features) {
      if (!char.features_traits) char.features_traits = [];
      char.features_traits = [...char.features_traits, ...this.levelUpAnalysis.new_features];
    }

    // Save back to API
    this.charState.updateCharacter(char.char_id!, char)
      .subscribe({
        next: () => {
          this.showLevelUpModal = false;
          this.levelUpAnalysis = null;
          this.rollToast.showMessage(`⚡ LEVEL UP: ${char.char_name}`, `Successfully leveled up to ${char.char_level}!`);
        },
        error: () => this.rollToast.showMessage('⚠️ LEVEL UP FAILED', 'Failed to save leveled up character.')
      });
  }

  onValidateCharacter() {
    const char = this.charState.activeCharacter();
    if (!char) return;
    this.isValidating = true;
    this.validationResult = null;
    this.showValidationModal = true;

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
        this.showValidationModal = false;
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

  onGenerateStrategy() {
    const char = this.charState.activeCharacter();
    if (!char) return;
    this.http.post<any>(`${environment.apiBaseUrl}/forge/playstyle-guide`, char).subscribe((res) => {
      this.strategyGuideText = res.guide_markdown;
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

  onImportPdf(event: any) {
    const file = event.target.files[0];
    if (!file) return;

    const formData = new FormData();
    formData.append('file', file);

    this.http.post<CharacterSchema>(`${environment.apiBaseUrl}/characters/import-pdf`, formData).subscribe({
      next: (imported) => {
        this.charState.saveCharacter(imported).subscribe();
        this.rollToast.showMessage('📥 PDF IMPORTED', `Successfully imported ${imported.char_name}!`);
      },
      error: () => this.rollToast.showMessage('⚠️ IMPORT FAILED', 'Failed to import PDF character sheet.')
    });
  }

  getStatsArray(stats: any) {
    if (!stats) return [];
    return Object.keys(stats).map((key) => ({ key, value: stats[key] }));
  }

  getModifierString(val: number): string {
    const mod = Math.floor((val - 10) / 2);
    return mod >= 0 ? `+${mod}` : `${mod}`;
  }
}
