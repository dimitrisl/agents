import { Component, OnDestroy, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { HttpClient, HttpErrorResponse } from '@angular/common/http';
import { AuthService } from '../../core/services/auth.service';
import { RollToastService } from '../../core/services/roll-toast.service';
import { CharacterStateService } from '../../core/services/character-state.service';
import { DiceService } from '../../core/services/dice.service';
import { Subscription } from 'rxjs';
import { WebSocketService, WsMessage } from '../../core/services/websocket.service';
import {
  Campaign,
  CampaignMessages,
  RollRequest,
  Whisper,
  campaignUrl,
} from '../../core/models/campaign.model';
import {
  EncounterResponse,
  NpcResponse,
  SessionPrepResponse,
} from '../../core/models/dm-tools.model';
import {
  CombatantCondition,
  InitiativeCombatant,
} from '../../core/models/initiative.model';
import { EncounterStorageService } from '../../core/services/encounter-storage.service';
import { environment } from '../../../environments/environment';
import {
  ForgeButtonDirective,
  ForgeCardComponent,
  ForgeEmptyStateComponent,
  ForgePageComponent,
  ForgeTab,
  ForgeTabsComponent,
} from '../../shared/ui';
import { CampaignHeaderComponent } from './campaign-header/campaign-header.component';
import { NotesPanelComponent } from './panels/notes-panel/notes-panel.component';
import { PartyPanelComponent } from './panels/party-panel/party-panel.component';
import { InitiativePanelComponent } from './panels/initiative-panel/initiative-panel.component';
import { GeneratorsPanelComponent } from './panels/generators-panel/generators-panel.component';
import { PrepPanelComponent } from './panels/prep-panel/prep-panel.component';
import { WhisperModalComponent } from './modals/whisper-modal/whisper-modal.component';
import { RollRequestModalComponent } from './modals/roll-request-modal/roll-request-modal.component';
import { StatblockModalComponent } from './modals/statblock-modal/statblock-modal.component';
import { NewCampaignModalComponent } from './modals/new-campaign-modal/new-campaign-modal.component';
import { AddMemberModalComponent } from './modals/add-member-modal/add-member-modal.component';
import { DmInboxComponent } from './dm-inbox/dm-inbox.component';

export interface PartyMember {
  char_id?: string;
  name: string;
  char_class: string;
  level: number;
  hp_current: number;
  hp_max: number;
  ac: number;
  passive_perception: number;
  conditions: string[];
  stats?: { [key: string]: number };
  portrait?: string;
}

type LoadStatus = 'loading' | 'ready' | 'error';

/** What the DM may write back to a hero's sheet from the workspace. */
interface PartyStateChanges {
  hp_current?: number;
  conditions?: string[];
}

interface PartyStatePayload extends PartyStateChanges {
  char_id?: string;
}

/**
 * Long enough that holding a hit-point button is one write, short enough that
 * the player sees the hit while it still means something.
 */
const PARTY_STATE_DEBOUNCE_MS = 400;

@Component({
  selector: 'app-dm',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    ForgeButtonDirective,
    ForgeCardComponent,
    ForgeEmptyStateComponent,
    ForgePageComponent,
    ForgeTabsComponent,
    CampaignHeaderComponent,
    NotesPanelComponent,
    PartyPanelComponent,
    InitiativePanelComponent,
    GeneratorsPanelComponent,
    PrepPanelComponent,
    WhisperModalComponent,
    RollRequestModalComponent,
    StatblockModalComponent,
    NewCampaignModalComponent,
    AddMemberModalComponent,
    DmInboxComponent,
  ],
  templateUrl: './dm.component.html',
  styleUrl: './dm.component.css',
})
export class DmComponent implements OnInit, OnDestroy {
  activeTab: 'notes' | 'party' | 'initiative' | 'generators' | 'prep' = 'party';
  readonly dmTabs: ForgeTab[] = [
    { id: 'notes', label: '📝 Campaign Notes' },
    { id: 'party', label: '👥 Live Party Tracker' },
    { id: 'initiative', label: '⚔️ Initiative Tracker' },
    { id: 'generators', label: '🎲 AI Generators' },
    { id: 'prep', label: '📜 Session Prep' },
  ];

  userCampaigns: Campaign[] = [];
  campaignName = '';
  campaignNotes = '';
  inviteCode = '';

  /**
   * Load outcomes are rendered, never papered over: a DM who cannot tell a failed
   * request from an empty table will hand out an invite code nobody can use.
   */
  campaignsStatus: LoadStatus = 'loading';
  partyStatus: LoadStatus = 'ready';
  isCreatingCampaign = false;

  showWhisperModal = false;
  showRollModal = false;
  showNewCampaignModal = false;
  showAddMemberModal = false;

  newCampaignTitle = '';
  newCampaignNotes = '';

  newMemberName = '';
  newMemberClass = 'Fighter';
  newMemberLevel = 5;
  newMemberHp = 40;
  newMemberAc = 16;

  selectedStatblockCombatant: InitiativeCombatant | null = null;

  whisperRecipient = 'All';
  whisperMessage = '';

  // --- Live table inbox ---
  showDmInbox = false;
  inboxWhispers: Whisper[] = [];
  inboxRollRequests: RollRequest[] = [];
  unreadInboxMessages = 0;
  inboxReplyRecipient = 'All';
  inboxReplyMessage = '';
  isSendingInboxReply = false;

  rollTargetMember = '';
  rollType = 'saving_throw';
  rollStat = 'DEX';
  rollReason = 'Dragon Breath Fire Save';
  isSecretRoll = false;

  avgLevel = 5;
  location = 'Crypt';
  encounterResult: EncounterResponse | null = null;

  npcConcept = 'Shady underworld broker';
  npcResult = '';

  prepNotes = '';
  prepResult = '';

  availableConditions = ['Poisoned', 'Concentrating', 'Stunned', 'Unconscious', 'Blinded', 'Charmed', 'Frightened', 'Grappled', 'Incapacitated', 'Invisible', 'Paralyzed', 'Petrified', 'Prone', 'Restrained'];

  /**
   * Rosters the DM edited locally this session, keyed by campaign. Only ever
   * written from a successful fetch or a deliberate add — a failed fetch leaves
   * the party empty rather than resurrecting a stale roster as if it were live.
   */
  campaignParties: { [campaignName: string]: PartyMember[] } = {};

  partyMembers: PartyMember[] = [];
  combatants: InitiativeCombatant[] = [];
  /**
   * The combatant whose turn it is, held by id — never by index. The list is
   * re-sorted on every initiative roll and spliced on every removal, so an index
   * silently starts pointing at a different creature.
   */
  activeCombatantId: string | null = null;
  /**
   * 0 means the encounter has not started — the first Next Turn opens round 1.
   * It climbs only when the order wraps back to the top, which is the one
   * moment D&D calls a new round.
   */
  round = 0;

  newCombatantName = '';
  newCombatantInit = 10;
  newCombatantHp = 20;

  addMemberTab: 'existing' | 'custom' | 'invite' = 'existing';
  selectedExistingCharId = '';

  constructor(
    private rollToast: RollToastService,
    private dice: DiceService,
    private http: HttpClient,
    public charState: CharacterStateService,
    private wsService: WebSocketService,
    private auth: AuthService,
    private encounterStorage: EncounterStorageService
  ) {}

  // The campaign whose party/socket is currently live, so re-picking the same
  // one from the dropdown does not refetch it.
  private activeWorkspace: string | null = null;
  private wsSub: Subscription | null = null;
  private openedSub: Subscription | null = null;

  /**
   * Whether the tracker currently holds a real fight for this campaign. The
   * party fetch used to seed it unconditionally; doing that over a restored
   * encounter would wipe it moments after it reappeared.
   */
  private hasLiveEncounter = false;

  /** Coalesced writes back to the heroes' sheets, keyed by character. */
  private pendingPartyState = new Map<string, PartyStateChanges>();
  private partyStateTimers = new Map<string, ReturnType<typeof setTimeout>>();

  ngOnInit() {
    this.loadCampaigns();

    // Every (re)connect re-reads the thread, so a dropped socket costs nothing
    // and nobody ever has to reload the page to catch up.
    this.openedSub = this.wsService.opened$.subscribe((campaignName) => {
      if (campaignName === this.campaignName) {
        this.loadCampaignMessages(campaignName, true);
      }
    });

    this.wsSub = this.wsService.messages$.subscribe((msg: WsMessage) => {
      const payload = msg['payload'];
      if (!payload) return;

      if (msg.type === 'roll_request') {
        // Echo of what this DM (or a co-DM) just asked for — it belongs on the
        // board immediately so the answer has somewhere to land.
        this.cancelSupersededRollRequests(payload);
        this.upsertRollRequest(payload, false);
      } else if (msg.type === 'roll_result') {
        // A missed request comes down this same channel with no result on it — the
        // player never rolled. It still has to reach the board, or the request sits
        // there as "waiting" for the rest of the session.
        if (payload.status === 'missed') {
          this.upsertRollRequest(payload, true);
          this.rollToast.showMessage(
            `⌛ NO ANSWER: ${payload.char_name}`,
            `${payload.roll_type} (${payload.stat}) went unanswered.`
          );
          return;
        }

        const result = payload.result;
        if (!result) return;

        this.upsertRollRequest(payload, true);
        // The mode belongs in the headline: a 24 rolled with advantage and a 24
        // rolled straight are different facts at the table.
        const mode = result.mode && result.mode !== 'normal' ? ` (${result.mode})` : '';
        const secret = payload.rolled_by === 'dm';
        this.rollToast.showMessage(
          `${secret ? '🔒 SECRET ROLL' : '🎲 ROLL RESULT'}: ${payload.char_name}`,
          `${payload.roll_type} (${payload.stat}) = ${result.total}${mode}` +
            (secret ? ' — the player was not asked.' : '')
        );
      } else if (msg.type === 'party_update') {
        this.applyPartyUpdate(payload);
      } else if (msg.type === 'whisper') {
        const isOwnWhisper = payload.sender === 'DM';
        this.addInboxWhisper(payload, !isOwnWhisper);
        if (!isOwnWhisper) {
          this.rollToast.showMessage(`💬 ${payload.sender} REPLIED`, payload.message);
        }
      }
    });
  }

  ngOnDestroy() {
    this.wsSub?.unsubscribe();
    this.openedSub?.unsubscribe();

    // A hit recorded a moment before leaving the page still has to land.
    for (const timer of this.partyStateTimers.values()) clearTimeout(timer);
    this.partyStateTimers.clear();
    for (const charId of [...this.pendingPartyState.keys()]) this.flushPartyState(charId);
  }

  // --- Live table inbox ---

  onDmInboxOpenChange(open: boolean) {
    this.showDmInbox = open;
    if (open) {
      this.unreadInboxMessages = 0;
    }
  }

  /** Whispers back to a player from inside the inbox, without leaving the thread. */
  sendInboxReply() {
    const message = this.inboxReplyMessage.trim();
    if (!message || this.isSendingInboxReply) return;

    this.isSendingInboxReply = true;
    this.http
      .post<{ whisper: Whisper }>(campaignUrl(this.campaignName, 'whisper'), {
        sender: 'DM',
        recipient: this.inboxReplyRecipient,
        message,
      })
      .subscribe({
        next: (res) => {
          this.isSendingInboxReply = false;
          this.inboxReplyMessage = '';
          // Thread it locally too: the socket echo is a nicety, not a guarantee.
          if (res?.whisper) {
            this.addInboxWhisper(res.whisper, false);
          }
        },
        error: () => {
          this.isSendingInboxReply = false;
          this.rollToast.showMessage('⚠️ WHISPER NOT SENT', 'The whisper did not reach the table.');
        },
      });
  }

  /**
   * `isCatchUp` is the reconnect case: the thread is merged rather than replaced,
   * so anything that happened while the socket was down still lands as unread
   * instead of silently filling in.
   */
  private loadCampaignMessages(campaignName: string, isCatchUp = false) {
    this.http
      .get<CampaignMessages>(campaignUrl(campaignName, 'messages'))
      .subscribe({
        next: (messages) => {
          if (campaignName !== this.campaignName) return;

          if (!isCatchUp) {
            this.inboxWhispers = [...(messages.whispers || [])].sort(
              (a, b) => this.timestampSortValue(a.timestamp) - this.timestampSortValue(b.timestamp)
            );
            this.inboxRollRequests = [...(messages.roll_requests || [])].sort(
              (a, b) => this.timestampSortValue(a.created_at) - this.timestampSortValue(b.created_at)
            );
            this.unreadInboxMessages = 0;
            return;
          }

          for (const whisper of messages.whispers || []) {
            this.addInboxWhisper(whisper, whisper.sender !== 'DM');
          }
          for (const request of messages.roll_requests || []) {
            this.mergeRollRequestFromHistory(request);
          }
        },
        error: () => {
          if (isCatchUp || campaignName !== this.campaignName) return;
          this.inboxWhispers = [];
          this.inboxRollRequests = [];
          this.unreadInboxMessages = 0;
        },
      });
  }

  /** Only a request we have never seen, or one that changed state, is news. */
  private mergeRollRequestFromHistory(request: RollRequest) {
    const existing = request.id
      ? this.inboxRollRequests.find((item) => item.id === request.id)
      : undefined;
    if (existing && existing.status === request.status) return;

    this.upsertRollRequest(request, request.status === 'resolved');
  }

  private addInboxWhisper(whisper: Whisper, markUnread: boolean) {
    if (whisper.id && this.inboxWhispers.some((item) => item.id === whisper.id)) return;

    this.inboxWhispers = [...this.inboxWhispers, whisper].sort(
      (a, b) => this.timestampSortValue(a.timestamp) - this.timestampSortValue(b.timestamp)
    );

    if (markUnread && !this.showDmInbox) {
      this.unreadInboxMessages += 1;
    }
  }

  /**
   * A new ask retires the hero's previous unanswered one — the same rule the
   * server applies when it stores the request, mirrored so the board does not
   * keep showing a request nobody will ever roll.
   */
  private cancelSupersededRollRequests(request: RollRequest) {
    this.inboxRollRequests = this.inboxRollRequests.map((item) =>
      item.id !== request.id &&
      item.char_filename === request.char_filename &&
      item.status === 'pending'
        ? { ...item, status: 'cancelled' }
        : item
    );
  }

  /** Roll requests arrive twice — once when issued, once answered. */
  private upsertRollRequest(request: RollRequest, markUnread: boolean) {
    const index = request.id
      ? this.inboxRollRequests.findIndex((item) => item.id === request.id)
      : -1;

    if (index >= 0) {
      const next = [...this.inboxRollRequests];
      next[index] = request;
      this.inboxRollRequests = next;
    } else {
      this.inboxRollRequests = [...this.inboxRollRequests, request].sort(
        (a, b) => this.timestampSortValue(a.created_at) - this.timestampSortValue(b.created_at)
      );
    }

    if (markUnread && !this.showDmInbox) {
      this.unreadInboxMessages += 1;
    }
  }

  private timestampSortValue(timestamp?: string): number {
    if (!timestamp) return 0;
    const normalized = timestamp.includes('T') ? timestamp : `${timestamp.replace(' ', 'T')}Z`;
    const value = new Date(normalized).getTime();
    return Number.isNaN(value) ? 0 : value;
  }

  /** The vault is only needed for the "existing hero" picker, so it loads with it. */
  openAddMemberModal() {
    this.showAddMemberModal = true;
    this.charState.ensureLoaded().subscribe();
  }

  // --- Session board (presentation only, derived from the live workspace state) ---

  get partyAverageLevel(): number {
    if (this.partyMembers.length === 0) return 0;
    const total = this.partyMembers.reduce((sum, member) => sum + (member.level || 0), 0);
    return Math.round(total / this.partyMembers.length);
  }

  get currentTurnName(): string {
    return this.combatants.find((c) => c.id === this.activeCombatantId)?.name || '—';
  }

  get roundLabel(): string {
    return this.round > 0 ? `Round ${this.round}` : 'Not started';
  }

  hpPercent(member: PartyMember): number {
    if (!member.hp_max) return 0;
    return Math.max(0, Math.min(100, (member.hp_current / member.hp_max) * 100));
  }

  trackPartyMember(_index: number, member: PartyMember): string {
    return member.char_id || member.name;
  }

  loadCampaigns() {
    this.campaignsStatus = 'loading';
    this.http.get<Campaign[]>(`${environment.apiBaseUrl}/campaigns/`).subscribe({
      next: (camps) => {
        this.userCampaigns = camps || [];
        this.campaignsStatus = 'ready';

        if (this.userCampaigns.length === 0) {
          this.clearWorkspace();
          return;
        }

        if (!this.userCampaigns.some((c) => c.campaign_name === this.campaignName)) {
          this.campaignName = this.userCampaigns[0].campaign_name;
        }
        this.onCampaignSelect();
      },
      error: (err) => {
        if (this.handleAuthFailure(err)) return;
        this.userCampaigns = [];
        this.campaignsStatus = 'error';
        this.clearWorkspace();
      }
    });
  }

  /**
   * An expired session is not a workspace error — it is a login. Anything else
   * has to surface as a visible failure the DM can retry.
   */
  private handleAuthFailure(error: unknown): boolean {
    if (error instanceof HttpErrorResponse && error.status === 401) {
      this.auth.logout();
      return true;
    }
    return false;
  }

  /** Drops every trace of the previous campaign so nothing lingers on screen. */
  private clearWorkspace() {
    this.activeWorkspace = null;
    this.campaignName = '';
    this.campaignNotes = '';
    this.inviteCode = '';
    this.partyMembers = [];
    this.partyStatus = 'ready';
    this.rollTargetMember = '';
    this.combatants = [];
    this.activeCombatantId = null;
    this.round = 0;
    this.hasLiveEncounter = false;
    this.inboxWhispers = [];
    this.inboxRollRequests = [];
    this.unreadInboxMessages = 0;
    this.showDmInbox = false;
  }

  onCampaignSelect() {
    if (!this.campaignName || this.activeWorkspace === this.campaignName) return;
    const isFirstLoad = this.activeWorkspace === null;
    this.activeWorkspace = this.campaignName;

    const selected = this.userCampaigns.find((c) => c.campaign_name === this.campaignName);
    // No code yet — the DM forges one from the header button when they need it.
    this.inviteCode = selected?.invite_code || '';
    this.campaignNotes = selected?.notes || '';

    // Before anything async: an encounter left running in this campaign is put
    // straight back on the table, so the fight is on screen while the roster is
    // still in flight rather than flashing empty first.
    this.restoreEncounter(this.campaignName);

    // role=dm means the server routes every whisper and roll result here, even
    // the private ones addressed to a single hero.
    this.wsService.connect(this.campaignName, { role: 'dm' });

    this.showDmInbox = false;
    this.inboxReplyMessage = '';
    this.inboxReplyRecipient = 'All';
    this.loadCampaignMessages(this.campaignName);
    this.loadParty();

    if (!isFirstLoad) {
      this.rollToast.showMessage('🏰 CAMPAIGN SWITCHED', `Active workspace set to "${this.campaignName}".`);
    }
  }

  /** Also the retry target for the party error state, hence its own method. */
  loadParty() {
    if (!this.campaignName) return;

    this.partyStatus = 'loading';
    this.http
      .get<any[]>(campaignUrl(this.campaignName, 'party'))
      .subscribe({
        next: (chars) => {
          this.partyMembers = (chars || []).map((char) => ({
            char_id: char.char_id,
            name: char.char_name || 'Unknown',
            char_class: char.char_class || 'Unknown',
            level: char.char_level || 1,
            hp_current: char.hp_current ?? char.hp_max ?? 10,
            hp_max: char.hp_max ?? 10,
            ac: char.armor_class ?? 10,
            passive_perception: 10 + Math.floor(((char.stats?.WIS || 10) - 10) / 2),
            // The sheet has carried conditions all along; the workspace used to
            // throw them away and start every session from a clean hero.
            conditions: char.conditions || [],
            stats: char.stats || { STR: 10, DEX: 10, CON: 10, INT: 10, WIS: 10, CHA: 10 },
            portrait: char.char_portrait
          }));
          this.campaignParties[this.campaignName] = [...this.partyMembers];
          this.partyStatus = 'ready';
          this.rollTargetMember = this.partyMembers[0]?.name || '';
          this.seedInitiativeFromParty();
        },
        error: (err) => {
          if (this.handleAuthFailure(err)) return;
          // The roster is unknown, not empty — say so instead of inventing heroes.
          this.partyMembers = [];
          this.partyStatus = 'error';
          this.rollTargetMember = '';
          this.seedInitiativeFromParty();
        }
      });
  }

  getSelectedHero() {
    if (!this.selectedExistingCharId) return null;
    return this.charState.characters().find((c) => c.char_id === this.selectedExistingCharId) || null;
  }

  addExistingPartyMember() {
    const char = this.getSelectedHero();
    if (!char) return;

    const member: PartyMember = {
      char_id: char.char_id,
      name: char.char_name,
      char_class: char.char_class,
      level: char.char_level,
      hp_current: char.hp_current ?? char.hp_max,
      hp_max: char.hp_max,
      ac: char.armor_class,
      passive_perception: 10 + Math.floor(((char.stats?.WIS || 10) - 10) / 2),
      conditions: [],
      stats: char.stats || { STR: 10, DEX: 10, CON: 10, INT: 10, WIS: 10, CHA: 10 },
      portrait: char.char_portrait
    };

    if (!this.partyMembers.some((m) => m.name === member.name)) {
      this.partyMembers.push(member);
      if (!this.campaignParties[this.campaignName]) {
        this.campaignParties[this.campaignName] = [];
      }
      this.campaignParties[this.campaignName] = [...this.partyMembers];
      this.importPartyToInitiative();
      this.rollToast.showMessage('👤 HERO ENLISTED', `Added ${member.name} (${member.char_class}) to ${this.campaignName} party roster.`);
    } else {
      this.rollToast.showMessage('⚠️ ALREADY IN PARTY', `${member.name} is already in the active party roster.`);
    }
    this.showAddMemberModal = false;
    this.selectedExistingCharId = '';
  }

  copyInviteCode() {
    // A placeholder code copied to the clipboard is worse than none: the players
    // it is handed to simply cannot join.
    if (!this.inviteCode) {
      this.rollToast.showMessage('⚠️ NO INVITE CODE', 'Forge an invite code for this campaign first.');
      return;
    }

    // The clipboard is allowed to say no — denied permission, or an insecure
    // context where the API is not even there. Announcing success regardless
    // sends the DM off to paste a code that was never copied, so the toast and
    // the modal closing both wait for the write to actually land.
    const code = this.inviteCode;
    if (!navigator.clipboard) {
      this.showClipboardFailure(code);
      return;
    }

    navigator.clipboard.writeText(code).then(
      () => {
        this.rollToast.showMessage('📋 CODE COPIED', `Invite code "${code}" copied to clipboard! Share with players.`);
        this.showAddMemberModal = false;
      },
      () => this.showClipboardFailure(code)
    );
  }

  private showClipboardFailure(code: string) {
    this.rollToast.showMessage(
      '⚠️ COPY FAILED',
      `The clipboard refused the write. Share this invite code by hand: ${code}`
    );
  }

  addPartyMember() {
    if (!this.newMemberName.trim()) return;
    const member: PartyMember = {
      name: this.newMemberName.trim(),
      char_class: this.newMemberClass || 'Fighter',
      level: this.newMemberLevel || 5,
      hp_current: this.newMemberHp || 40,
      hp_max: this.newMemberHp || 40,
      ac: this.newMemberAc || 16,
      passive_perception: 10 + Math.floor(((12) - 10) / 2),
      conditions: [],
      stats: { STR: 14, DEX: 14, CON: 14, INT: 10, WIS: 12, CHA: 10 }
    };

    this.partyMembers.push(member);
    if (!this.campaignParties[this.campaignName]) {
      this.campaignParties[this.campaignName] = [];
    }
    this.campaignParties[this.campaignName] = [...this.partyMembers];

    this.showAddMemberModal = false;
    this.newMemberName = '';
    this.importPartyToInitiative();
    this.rollToast.showMessage('👤 HERO ENLISTED', `Added ${member.name} (${member.char_class}) to ${this.campaignName} party roster.`);
  }

  createNewCampaign() {
    if (!this.newCampaignTitle.trim() || this.isCreatingCampaign) return;
    const newCamp: Campaign = {
      campaign_name: this.newCampaignTitle.trim(),
      notes: this.newCampaignNotes,
      party: [],
      dnd_edition: '2014 Edition'
    };

    this.isCreatingCampaign = true;
    this.http.post<Campaign>(`${environment.apiBaseUrl}/campaigns/`, newCamp).subscribe({
      next: (res) => {
        this.isCreatingCampaign = false;
        this.userCampaigns.push(res);
        this.campaignsStatus = 'ready';
        this.campaignName = res.campaign_name;
        this.showNewCampaignModal = false;
        this.newCampaignTitle = '';
        this.newCampaignNotes = '';
        this.onCampaignSelect();
        this.generateInviteCode();
        this.rollToast.showMessage('🏰 CAMPAIGN CREATED', `Successfully forged campaign: ${res.campaign_name}`);
      },
      error: (err) => {
        this.isCreatingCampaign = false;
        if (this.handleAuthFailure(err)) return;
        // The modal stays open with the title intact: nothing was created, so the
        // DM gets to retry instead of being told a lie and handed a dead campaign.
        this.rollToast.showMessage(
          '⚠️ CAMPAIGN NOT CREATED',
          `The server refused to forge "${newCamp.campaign_name}". Nothing was saved — try again.`
        );
      }
    });
  }

  saveCampaignNotes() {
    this.http.post(campaignUrl(this.campaignName, 'notes'), {
      notes: this.campaignNotes
    }).subscribe({
      next: () => this.rollToast.showMessage('📝 NOTES SAVED', 'Campaign notes auto-saved to database.'),
      error: (err) => {
        if (this.handleAuthFailure(err)) return;
        this.rollToast.showMessage('⚠️ SAVE FAILED', 'Failed to save campaign notes.');
      }
    });
  }

  generateInviteCode() {
    this.http
      .post<{ invite_code: string }>(campaignUrl(this.campaignName, 'invite-code'), {})
      .subscribe({
        next: (res) => {
          this.inviteCode = res.invite_code;
          const selected = this.userCampaigns.find((c) => c.campaign_name === this.campaignName);
          if (selected) selected.invite_code = res.invite_code;
        },
        error: (err) => {
          if (this.handleAuthFailure(err)) return;
          this.rollToast.showMessage('⚠️ NO INVITE CODE', 'The server could not forge an invite code.');
        }
      });
  }

  // --- One hero, one state ---
  //
  // Hit points and conditions for a hero are owned by the `PartyMember`. The
  // initiative row for that hero is a view of it, never a second copy: both
  // tabs used to hold their own numbers and drift apart in the middle of a
  // fight, with the DM left to guess which one was true.

  adjustHp(member: PartyMember, delta: number) {
    this.setPartyHp(member, member.hp_current + delta);
  }

  setPartyHp(member: PartyMember, hp: number) {
    const clamped = Math.max(0, Math.min(member.hp_max, Math.round(hp) || 0));
    if (clamped === member.hp_current) return;

    member.hp_current = clamped;
    this.projectMemberOntoCombatants(member);
    this.pushPartyState(member, { hp_current: clamped });
  }

  toggleCondition(member: PartyMember, cond: string) {
    const idx = member.conditions.indexOf(cond);
    if (idx >= 0) {
      member.conditions = member.conditions.filter((c) => c !== cond);
      this.dropConditionFromCombatants(member, cond);
    } else {
      member.conditions = [...member.conditions, cond];
      // Set from the roster, so it has no combat timer — it lasts until lifted.
      this.addConditionToCombatants(member, cond, null);
    }

    this.pushPartyState(member, { conditions: member.conditions });
  }

  /** The party member behind an initiative row, when the row is a hero. */
  private memberFor(combatant: InitiativeCombatant): PartyMember | undefined {
    if (!combatant.is_player) return undefined;
    return this.partyMembers.find((m) =>
      combatant.char_id ? m.char_id === combatant.char_id : m.name === combatant.name
    );
  }

  private combatantsFor(member: PartyMember): InitiativeCombatant[] {
    return this.combatants.filter(
      (c) => c.is_player && (c.char_id ? c.char_id === member.char_id : c.name === member.name)
    );
  }

  /** Pushes the member's hit points onto its initiative row. */
  private projectMemberOntoCombatants(member: PartyMember) {
    const linked = new Set(this.combatantsFor(member).map((c) => c.id));
    if (linked.size === 0) return;

    this.combatants = this.combatants.map((c) =>
      linked.has(c.id) ? { ...c, hp: member.hp_current, max_hp: member.hp_max } : c
    );
    this.persistEncounter();
  }

  private addConditionToCombatants(
    member: PartyMember,
    condition: string,
    expiresAtRound: number | null
  ) {
    const linked = new Set(this.combatantsFor(member).map((c) => c.id));
    if (linked.size === 0) return;

    this.combatants = this.combatants.map((c) =>
      linked.has(c.id)
        ? {
            ...c,
            conditions: [
              ...c.conditions.filter((existing) => existing.name !== condition),
              { name: condition, expiresAtRound },
            ],
          }
        : c
    );
    this.persistEncounter();
  }

  private dropConditionFromCombatants(member: PartyMember, condition: string) {
    const linked = new Set(this.combatantsFor(member).map((c) => c.id));
    if (linked.size === 0) return;

    this.combatants = this.combatants.map((c) =>
      linked.has(c.id)
        ? { ...c, conditions: c.conditions.filter((existing) => existing.name !== condition) }
        : c
    );
    this.persistEncounter();
  }

  /**
   * A condition whose timer ran out is a real event, not just something the
   * tracker stops drawing: the roster has to lose it too, and so does the
   * database. Walking the round back re-adds it, which is why the expiry is
   * kept rather than deleted.
   */
  private reconcileLapsedConditions() {
    for (const member of this.partyMembers) {
      const combatant = this.combatantsFor(member)[0];
      if (!combatant) continue;

      const active = combatant.conditions
        .filter((c) => c.expiresAtRound === null || c.expiresAtRound > this.round)
        .map((c) => c.name);

      const unchanged =
        active.length === member.conditions.length &&
        active.every((name) => member.conditions.includes(name));
      if (unchanged) continue;

      member.conditions = active;
      this.pushPartyState(member, { conditions: active });
    }
  }

  quickDmStatRoll(member: PartyMember, stat: string) {
    const val = member.stats?.[stat] || 10;
    const mod = Math.floor((val - 10) / 2);
    const roll = this.dice.rollD20(mod);

    this.rollToast.showRoll({
      title: `🎲 DM CHECK: ${member.name.toUpperCase()} (${stat})`,
      expression: roll.expression,
      raw: roll.raw,
      rolls: roll.rolls,
      sides: roll.sides,
      modifier: roll.modifier,
      total: roll.total,
      mode: roll.mode
    });
  }

  openSingleRollModal(m: PartyMember) {
    this.rollTargetMember = m.name;
    this.showRollModal = true;
  }

  sendRollRequest() {
    this.showRollModal = false;
    // Vault heroes are addressed by their real sheet filename, so the player's
    // dashboard matches the request to the exact character, not just a name.
    const target = this.partyMembers.find((m) => m.name === this.rollTargetMember);
    const charFilename = target?.char_id
      ? `${this.rollTargetMember.toLowerCase()}_${target.char_id}.json`
      : `${this.rollTargetMember.toLowerCase()}.json`;

    this.http.post(campaignUrl(this.campaignName, 'roll-request'), {
      char_filename: charFilename,
      char_name: this.rollTargetMember,
      roll_type: this.rollType,
      stat: this.rollStat,
      reason: this.rollReason,
      is_secret: this.isSecretRoll
    }).subscribe({
      next: () => {
        // A secret roll is already thrown by the time this returns, and its result
        // arrives on the socket a moment later — announcing it as "sent" here would
        // both be wrong and step on that toast.
        if (this.isSecretRoll) return;
        this.rollToast.showMessage('🎲 ROLL REQUEST SENT', `Issued ${this.rollType} (${this.rollStat}) to ${this.rollTargetMember}.`);
      },
      error: () =>
        this.rollToast.showMessage('⚠️ REQUEST NOT SENT', `Could not reach ${this.rollTargetMember}.`)
    });
  }

  /**
   * The party fetch's own call into the tracker. It seeds a fresh table, but
   * never touches a fight that came back from storage — the restored encounter
   * already holds those heroes, with the HP and conditions they earned.
   */
  private seedInitiativeFromParty() {
    if (this.hasLiveEncounter) return;
    this.importPartyToInitiative(true);
  }

  importPartyToInitiative(silent = false) {
    const additions = this.partyMembers
      .filter((p) => !this.combatants.some((c) => c.name === p.name))
      .map((p) => {
        const dexVal = p.stats?.['DEX'] || 10;
        const dexMod = Math.floor((dexVal - 10) / 2);
        return this.buildCombatant({
          char_id: p.char_id,
          name: p.name,
          initiative: 10 + dexMod,
          hp: p.hp_current,
          max_hp: p.hp_max,
          ac: p.ac,
          dex: dexVal,
          is_player: true,
          portrait: p.portrait,
          conditions: p.conditions.map((name) => ({ name, expiresAtRound: null })),
        });
      });

    this.combatants = this.sortCombatants([...this.combatants, ...additions]);
    this.persistEncounter();

    if (!silent) {
      this.rollToast.showMessage('👥 PARTY IMPORTED', 'Imported active party members into Initiative Tracker.');
    }
  }

  addCombatant() {
    if (!this.newCombatantName) return;

    const added = this.buildCombatant({
      name: this.newCombatantName,
      initiative: this.newCombatantInit,
      hp: this.newCombatantHp,
      max_hp: this.newCombatantHp,
      ac: 12,
      dex: 10,
      is_player: false,
    });

    this.combatants = this.sortCombatants([...this.combatants, added]);
    this.newCombatantName = '';
    this.persistEncounter();
  }

  removeCombatant(idx: number) {
    const removed = this.combatants[idx];
    if (!removed) return;

    this.combatants = this.combatants.filter((_, index) => index !== idx);

    if (removed.id === this.activeCombatantId) {
      // The active combatant left the fight, so the turn passes to whoever slid
      // into its slot — or wraps to the top of the order if it was the last one.
      this.activeCombatantId = this.combatants[idx]?.id ?? this.combatants[0]?.id ?? null;
    }

    // An emptied table is no longer a fight in progress.
    if (this.combatants.length === 0) this.round = 0;
    this.persistEncounter();
  }

  rollAllInitiative() {
    const rolled = this.combatants.map((c) => {
      const dexMod = Math.floor((c.dex - 10) / 2);
      return { ...c, initiative: this.dice.rollD20(dexMod).total };
    });

    this.combatants = this.sortCombatants(rolled);
    this.persistEncounter();
    this.rollToast.showMessage('🎲 INITIATIVE ROLLED', 'Rolled initiative for all active combatants!');
  }

  /** Highest initiative first. Returns a new array — OnPush children need one. */
  private sortCombatants(combatants: InitiativeCombatant[]): InitiativeCombatant[] {
    return [...combatants].sort((a, b) => b.initiative - a.initiative);
  }

  private buildCombatant(
    seed: Omit<InitiativeCombatant, 'id' | 'conditions'> & { conditions?: CombatantCondition[] }
  ): InitiativeCombatant {
    return {
      ...seed,
      id: Math.random().toString(36).substring(2, 9),
      conditions: seed.conditions ?? [],
    };
  }

  // --- The round engine ---

  nextTurn() {
    if (this.combatants.length === 0) {
      this.activeCombatantId = null;
      this.round = 0;
      this.persistEncounter();
      return;
    }

    // No active turn yet (-1) advances to the top of the order, which is also
    // what opens round 1.
    const current = this.combatants.findIndex((c) => c.id === this.activeCombatantId);
    const next = (current + 1) % this.combatants.length;

    // Wrapping to the top is the only thing that makes a new round.
    if (next === 0) this.round += 1;

    this.activeCombatantId = this.combatants[next].id;
    this.persistEncounter();
    this.reconcileLapsedConditions();
  }

  previousTurn() {
    // Nothing has happened yet — there is no turn to take back.
    if (this.combatants.length === 0 || this.round === 0) return;

    const current = this.combatants.findIndex((c) => c.id === this.activeCombatantId);
    if (current < 0) return;

    if (current === 0) {
      // Stepping off the top of the order walks the round counter back with it.
      // Round 1 is the floor: before it, combat had not begun.
      if (this.round <= 1) {
        this.activeCombatantId = null;
        this.round = 0;
        this.persistEncounter();
        this.reconcileLapsedConditions();
        return;
      }
      this.round -= 1;
    }

    const previous = (current - 1 + this.combatants.length) % this.combatants.length;
    this.activeCombatantId = this.combatants[previous].id;
    this.persistEncounter();
    this.reconcileLapsedConditions();
  }

  endCombat() {
    this.combatants = [];
    this.activeCombatantId = null;
    this.round = 0;
    this.hasLiveEncounter = false;
    this.encounterStorage.clear(this.campaignName);
    this.rollToast.showMessage('⏹️ COMBAT ENDED', 'The encounter was cleared. Initiative starts fresh.');
  }

  // --- Conditions, hit points and death saves ---

  /** `rounds` of 0 means "until the DM lifts it". */
  applyCombatantCondition(combatant: InitiativeCombatant, condition: string, rounds: number) {
    // Durations are anchored to the round they expire on, not counted down, so
    // Previous Turn restores a lapsed condition instead of losing it. Combat
    // that has not started yet is treated as round 1 for the arithmetic.
    const startRound = Math.max(1, this.round);
    const expiresAtRound = rounds > 0 ? startRound + rounds : null;

    this.updateCombatant(combatant.id, (c) => ({
      ...c,
      conditions: [
        ...c.conditions.filter((existing) => existing.name !== condition),
        { name: condition, expiresAtRound },
      ],
    }));

    // A hero's conditions belong to the roster and the database as well.
    const member = this.memberFor(combatant);
    if (member && !member.conditions.includes(condition)) {
      member.conditions = [...member.conditions, condition];
      this.pushPartyState(member, { conditions: member.conditions });
    }
  }

  removeCombatantCondition(combatant: InitiativeCombatant, condition: string) {
    this.updateCombatant(combatant.id, (c) => ({
      ...c,
      conditions: c.conditions.filter((existing) => existing.name !== condition),
    }));

    const member = this.memberFor(combatant);
    if (member && member.conditions.includes(condition)) {
      member.conditions = member.conditions.filter((c) => c !== condition);
      this.pushPartyState(member, { conditions: member.conditions });
    }
  }

  setCombatantHp(combatant: InitiativeCombatant, hp: number) {
    // A hero is edited through the roster, so the party tab, the tracker and
    // the player's own sheet all move together.
    const member = this.memberFor(combatant);
    if (member) {
      this.setPartyHp(member, hp);
      this.clearDeathSavesIfStanding(combatant.id, member.hp_current);
      return;
    }

    const clamped = Math.max(0, Math.min(combatant.max_hp, Math.round(hp) || 0));
    this.updateCombatant(combatant.id, (c) => ({ ...c, hp: clamped }));
    this.clearDeathSavesIfStanding(combatant.id, clamped);
  }

  private clearDeathSavesIfStanding(combatantId: string, hp: number) {
    if (hp <= 0) return;
    // Back on their feet: the tally that was counting them out is void.
    this.updateCombatant(combatantId, (c) => {
      const next = { ...c };
      delete next.deathSaves;
      return next;
    });
  }

  /**
   * The DM records what the player rolled. Clicking the dot that is already the
   * last one lit clears it, so a mis-click costs one click, not a life.
   */
  setDeathSave(combatant: InitiativeCombatant, kind: 'successes' | 'failures', value: number) {
    this.updateCombatant(combatant.id, (c) => {
      const saves = c.deathSaves ?? { successes: 0, failures: 0 };
      const next = saves[kind] === value ? value - 1 : value;
      return { ...c, deathSaves: { ...saves, [kind]: Math.max(0, Math.min(3, next)) } };
    });
  }

  private updateCombatant(
    id: string,
    change: (combatant: InitiativeCombatant) => InitiativeCombatant
  ) {
    this.combatants = this.combatants.map((c) => (c.id === id ? change(c) : c));
    this.persistEncounter();
  }

  // --- Party state persistence ---

  /**
   * Writes a hero's tracked state back to their sheet, so the player sees it and
   * a refresh does not throw the session's damage away.
   *
   * Coalesced per character: holding the − button is one intent, not eleven
   * requests. A member the DM invented by hand has no sheet to write to, so it
   * stays local and says nothing.
   */
  private pushPartyState(member: PartyMember, changes: PartyStateChanges) {
    if (!member.char_id || !this.campaignName) return;

    const charId = member.char_id;
    const pending = { ...(this.pendingPartyState.get(charId) ?? {}), ...changes };
    this.pendingPartyState.set(charId, pending);

    const timer = this.partyStateTimers.get(charId);
    if (timer) clearTimeout(timer);

    this.partyStateTimers.set(
      charId,
      setTimeout(() => this.flushPartyState(charId), PARTY_STATE_DEBOUNCE_MS)
    );
  }

  private flushPartyState(charId: string) {
    const changes = this.pendingPartyState.get(charId);
    this.pendingPartyState.delete(charId);
    this.partyStateTimers.delete(charId);
    if (!changes || !this.campaignName) return;

    const campaignName = this.campaignName;
    this.http
      .patch(`${campaignUrl(campaignName, 'party')}/${encodeURIComponent(charId)}/state`, changes)
      .subscribe({
        error: (err) => {
          if (this.handleAuthFailure(err)) return;
          // The table keeps playing on what is on screen, but the DM is told the
          // sheet did not take it — silence here is how a session's damage
          // quietly fails to reach the player.
          const member = this.partyMembers.find((m) => m.char_id === charId);
          this.rollToast.showMessage(
            '⚠️ NOT SAVED',
            `${member?.name || 'That hero'}'s state stayed in this browser — the server refused it.`
          );
        },
      });
  }

  /**
   * The server's echo of a party change — including this DM's own writes. A
   * character with a write still in flight is skipped: the echo is older than
   * what the DM is doing right now.
   */
  private applyPartyUpdate(payload: PartyStatePayload) {
    if (!payload?.char_id || this.pendingPartyState.has(payload.char_id)) return;

    const member = this.partyMembers.find((m) => m.char_id === payload.char_id);
    if (!member) return;

    if (typeof payload.hp_current === 'number') member.hp_current = payload.hp_current;
    if (Array.isArray(payload.conditions)) member.conditions = [...payload.conditions];

    this.projectMemberOntoCombatants(member);
  }

  // --- Encounter persistence ---

  /**
   * Browser-local, per campaign. The API has no encounter document, so this is
   * what a refresh can hold on to — it does not follow the DM to another
   * machine, and the players never see it.
   */
  private persistEncounter() {
    if (!this.campaignName) return;

    this.hasLiveEncounter = this.combatants.length > 0;
    if (!this.hasLiveEncounter) {
      this.encounterStorage.clear(this.campaignName);
      return;
    }

    this.encounterStorage.save(this.campaignName, {
      round: this.round,
      activeCombatantId: this.activeCombatantId,
      combatants: this.combatants,
    });
  }

  private restoreEncounter(campaignName: string) {
    const saved = this.encounterStorage.load(campaignName);

    if (saved && saved.combatants.length > 0) {
      this.combatants = this.sortCombatants(saved.combatants);
      this.activeCombatantId = saved.activeCombatantId;
      this.round = saved.round;
      this.hasLiveEncounter = true;
      return;
    }

    // Encounters belong to one campaign each, so nothing carries over from the
    // table we just left — not the monsters, and not whose turn it was.
    this.combatants = [];
    this.activeCombatantId = null;
    this.round = 0;
    this.hasLiveEncounter = false;
  }

  openStatblock(c: InitiativeCombatant) {
    this.selectedStatblockCombatant = c;
  }

  openBeyondUrl(name: string) {
    const slug = name.toLowerCase().replace(/[^a-z0-9 ]/g, '').replace(/ /g, '-');
    window.open(`https://www.dndbeyond.com/monsters/${slug}`, '_blank');
  }

  generateEncounter() {
    this.http.post<EncounterResponse>(`${environment.apiBaseUrl}/dm/encounter`, {
      party_size: 4,
      avg_level: this.avgLevel,
      location: this.location,
      edition: '2014 Edition',
      difficulty: 'Medium'
    }).subscribe((res) => {
      this.encounterResult = res;
    });
  }

  addEncounterMonstersToInitiative() {
    if (!this.encounterResult || !this.encounterResult.monsters) return;

    const added: InitiativeCombatant[] = [];
    this.encounterResult.monsters.forEach((m) => {
      const qty = m.quantity || 1;
      for (let i = 0; i < qty; i++) {
        const monsterName = qty > 1 ? `${m.name} ${i + 1}` : m.name;
        const dexMod = Math.floor((m.dex - 10) / 2);
        added.push(this.buildCombatant({
          name: monsterName,
          initiative: 10 + dexMod,
          hp: m.hp,
          max_hp: m.hp,
          ac: m.ac,
          dex: m.dex,
          is_player: false,
          statblock: m.statblock_summary
        }));
      }
    });

    this.combatants = this.sortCombatants([...this.combatants, ...added]);
    this.persistEncounter();
    this.rollToast.showMessage('⚔️ MONSTERS ADDED', `Added ${this.encounterResult.monsters.length} monster groups to the Initiative Tracker.`);
  }

  generateNpc() {
    this.http.post<NpcResponse>(`${environment.apiBaseUrl}/dm/npc`, {
      npc_concept: this.npcConcept,
      edition: '2014 Edition'
    }).subscribe((res) => {
      this.npcResult = res.npc_markdown;
    });
  }

  generatePrep() {
    this.http.post<SessionPrepResponse>(`${environment.apiBaseUrl}/dm/session-prep`, {
      campaign_notes: this.prepNotes,
      party_info: this.partyMembers.map(m => m.name).join(', ')
    }).subscribe((res) => {
      this.prepResult = res.session_markdown;
    });
  }

  sendWhisper() {
    this.http.post<{ whisper: Whisper }>(campaignUrl(this.campaignName, 'whisper'), {
      sender: 'DM',
      recipient: this.whisperRecipient,
      message: this.whisperMessage
    }).subscribe({
      next: (res) => {
        this.showWhisperModal = false;
        this.rollToast.showMessage('💬 WHISPER SENT', `Whisper delivered to ${this.whisperRecipient}.`);
        this.whisperMessage = '';
        if (res?.whisper) {
          this.addInboxWhisper(res.whisper, false);
        }
      },
      error: () =>
        this.rollToast.showMessage('⚠️ WHISPER NOT SENT', 'The whisper did not reach the table.')
    });
  }
}
