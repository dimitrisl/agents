import { Component, OnDestroy, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { HttpClient } from '@angular/common/http';
import { RollToastService } from '../../core/services/roll-toast.service';
import { CharacterStateService } from '../../core/services/character-state.service';
import { DiceService } from '../../core/services/dice.service';
import { Subscription } from 'rxjs';
import { WebSocketService, WsMessage } from '../../core/services/websocket.service';
import { CampaignMessages, RollRequest, Whisper } from '../../core/models/campaign.model';
import {
  EncounterResponse,
  NpcResponse,
  SessionPrepResponse,
} from '../../core/models/dm-tools.model';
import { environment } from '../../../environments/environment';
import {
  ForgeCardComponent,
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

export interface InitiativeCombatant {
  id: string;
  name: string;
  initiative: number;
  hp: number;
  max_hp: number;
  ac: number;
  dex: number;
  is_player: boolean;
  portrait?: string;
  statblock?: string;
}

@Component({
  selector: 'app-dm',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    ForgeCardComponent,
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

  userCampaigns: any[] = [];
  campaignName = 'The Obsidian Citadel';
  campaignNotes = 'Chapter 3: The heroes enter the Sunless Citadel in search of the lost Gulthias Tree...';
  inviteCode = '';

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

  rollTargetMember = 'Valeros';
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

  // Unique campaign party rosters
  campaignParties: { [campaignName: string]: PartyMember[] } = {
    'The Obsidian Citadel': [
      { name: 'Valeros', char_class: 'Paladin', level: 5, hp_current: 44, hp_max: 44, ac: 18, passive_perception: 14, conditions: ['Concentrating'], stats: { STR: 18, DEX: 12, CON: 15, INT: 10, WIS: 14, CHA: 16 } },
      { name: 'Ezren', char_class: 'Wizard', level: 5, hp_current: 28, hp_max: 28, ac: 13, passive_perception: 12, conditions: [], stats: { STR: 10, DEX: 14, CON: 12, INT: 18, WIS: 13, CHA: 10 } },
      { name: 'Merisiel', char_class: 'Rogue', level: 5, hp_current: 35, hp_max: 35, ac: 16, passive_perception: 16, conditions: [], stats: { STR: 12, DEX: 18, CON: 14, INT: 12, WIS: 14, CHA: 12 } },
    ],
    'Curse of Strahd': [
      { name: 'Ismark Kolyanovich', char_class: 'Fighter', level: 4, hp_current: 38, hp_max: 38, ac: 17, passive_perception: 12, conditions: [], stats: { STR: 16, DEX: 12, CON: 14, INT: 10, WIS: 11, CHA: 14 } },
      { name: 'Ireena Kolyana', char_class: 'Cleric', level: 3, hp_current: 24, hp_max: 24, ac: 15, passive_perception: 13, conditions: [], stats: { STR: 10, DEX: 14, CON: 12, INT: 12, WIS: 16, CHA: 15 } },
      { name: 'Rudolph van Richten', char_class: 'Ranger', level: 8, hp_current: 58, hp_max: 58, ac: 16, passive_perception: 18, conditions: [], stats: { STR: 11, DEX: 16, CON: 13, INT: 16, WIS: 18, CHA: 14 } },
    ],
    'Phyrexia Awakens': [
      { name: 'Elspeth Tirel', char_class: 'Paladin', level: 7, hp_current: 64, hp_max: 64, ac: 20, passive_perception: 15, conditions: [], stats: { STR: 18, DEX: 12, CON: 16, INT: 11, WIS: 14, CHA: 18 } },
      { name: 'Karn', char_class: 'Barbarian', level: 8, hp_current: 85, hp_max: 85, ac: 18, passive_perception: 13, conditions: [], stats: { STR: 20, DEX: 14, CON: 18, INT: 14, WIS: 12, CHA: 10 } },
      { name: 'Teferi', char_class: 'Wizard', level: 7, hp_current: 42, hp_max: 42, ac: 14, passive_perception: 17, conditions: [], stats: { STR: 9, DEX: 14, CON: 14, INT: 20, WIS: 16, CHA: 13 } },
    ]
  };

  partyMembers: PartyMember[] = [];
  combatants: InitiativeCombatant[] = [];
  /**
   * The combatant whose turn it is, held by id — never by index. The list is
   * re-sorted on every initiative roll and spliced on every removal, so an index
   * silently starts pointing at a different creature.
   */
  activeCombatantId: string | null = null;

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
    private wsService: WebSocketService
  ) {}

  // The campaign whose party/socket is currently live, so re-picking the same
  // one from the dropdown does not refetch it.
  private activeWorkspace: string | null = null;
  private wsSub: Subscription | null = null;
  private openedSub: Subscription | null = null;

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
        const result = payload.result;
        if (!result) return;

        this.upsertRollRequest(payload, true);
        this.rollToast.showMessage(
          `🎲 ROLL RESULT: ${payload.char_name}`,
          `${payload.roll_type} (${payload.stat}) = ${result.total}`
        );
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
      .post<{ whisper: Whisper }>(
        `${environment.apiBaseUrl}/campaigns/${encodeURIComponent(this.campaignName)}/whisper`,
        {
          sender: 'DM',
          recipient: this.inboxReplyRecipient,
          message,
        }
      )
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
      .get<CampaignMessages>(
        `${environment.apiBaseUrl}/campaigns/${encodeURIComponent(campaignName)}/messages`
      )
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

  hpPercent(member: PartyMember): number {
    if (!member.hp_max) return 0;
    return Math.max(0, Math.min(100, (member.hp_current / member.hp_max) * 100));
  }

  trackPartyMember(_index: number, member: PartyMember): string {
    return member.char_id || member.name;
  }

  loadCampaigns() {
    this.http.get<any[]>(`${environment.apiBaseUrl}/campaigns/`).subscribe({
      next: (camps) => {
        this.userCampaigns = camps || [];
        if (this.userCampaigns.length > 0 && !this.userCampaigns.some((c) => c.campaign_name === this.campaignName)) {
          this.campaignName = this.userCampaigns[0].campaign_name;
        }
        this.onCampaignSelect();
      },
      error: () => {
        this.userCampaigns = [
          { campaign_name: 'The Obsidian Citadel', invite_code: '4D0705', notes: 'Chapter 3: The heroes enter the Sunless Citadel...' },
          { campaign_name: 'Curse of Strahd', invite_code: 'BAROV1', notes: 'Chapter 1: Mist creeps into Castle Ravenloft...' },
          { campaign_name: 'Phyrexia Awakens', invite_code: 'PHY001', notes: 'Chapter 1: The glistened oil spreads...' }
        ];
        this.onCampaignSelect();
      }
    });
  }

  onCampaignSelect() {
    if (this.activeWorkspace === this.campaignName) return;
    const isFirstLoad = this.activeWorkspace === null;
    this.activeWorkspace = this.campaignName;

    const selected = this.userCampaigns.find((c) => c.campaign_name === this.campaignName);
    if (selected) {
      this.inviteCode = selected.invite_code || '';
      if (selected.notes) this.campaignNotes = selected.notes;
    } else {
      // No code yet — the DM forges one from the header button when they need it.
      this.inviteCode = '';
    }

    // role=dm means the server routes every whisper and roll result here, even
    // the private ones addressed to a single hero.
    this.wsService.connect(this.campaignName, { role: 'dm' });

    this.showDmInbox = false;
    this.inboxReplyMessage = '';
    this.inboxReplyRecipient = 'All';
    this.loadCampaignMessages(this.campaignName);

    this.http.get<any[]>(`${environment.apiBaseUrl}/campaigns/${this.campaignName}/party`).subscribe({
      next: (chars) => {
        this.partyMembers = chars.map(char => ({
          char_id: char.char_id,
          name: char.char_name || 'Unknown',
          char_class: char.char_class || 'Unknown',
          level: char.char_level || 1,
          hp_current: char.hp_current ?? char.hp_max ?? 10,
          hp_max: char.hp_max ?? 10,
          ac: char.armor_class ?? 10,
          passive_perception: 10 + Math.floor(((char.stats?.WIS || 10) - 10) / 2),
          conditions: [],
          stats: char.stats || { STR: 10, DEX: 10, CON: 10, INT: 10, WIS: 10, CHA: 10 },
          portrait: char.char_portrait
        }));
        this.campaignParties[this.campaignName] = [...this.partyMembers];

        if (this.partyMembers.length > 0) {
          this.rollTargetMember = this.partyMembers[0].name;
        }
        this.importPartyToInitiative(true);
      },
      error: () => {
        if (this.campaignParties[this.campaignName]) {
          this.partyMembers = [...this.campaignParties[this.campaignName]];
        } else {
          this.partyMembers = [];
        }
        if (this.partyMembers.length > 0) {
          this.rollTargetMember = this.partyMembers[0].name;
        }
        this.importPartyToInitiative(true);
      }
    });

    if (!isFirstLoad) {
      this.rollToast.showMessage('🏰 CAMPAIGN SWITCHED', `Active workspace set to "${this.campaignName}".`);
    }
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
    const code = this.inviteCode || '4D0705';
    navigator.clipboard.writeText(code);
    this.rollToast.showMessage('📋 CODE COPIED', `Invite code "${code}" copied to clipboard! Share with players.`);
    this.showAddMemberModal = false;
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
    if (!this.newCampaignTitle.trim()) return;
    const newCamp = {
      campaign_name: this.newCampaignTitle.trim(),
      notes: this.newCampaignNotes,
      party: [],
      dnd_edition: '2014 Edition'
    };

    this.http.post<any>(`${environment.apiBaseUrl}/campaigns/`, newCamp).subscribe({
      next: (res) => {
        this.userCampaigns.push(res);
        this.campaignName = res.campaign_name;
        this.campaignNotes = res.notes || '';
        this.showNewCampaignModal = false;
        this.newCampaignTitle = '';
        this.newCampaignNotes = '';
        this.generateInviteCode();
        this.rollToast.showMessage('🏰 CAMPAIGN CREATED', `Successfully forged campaign: ${res.campaign_name}`);
      },
      error: () => {
        // Local state fallback
        this.userCampaigns.push(newCamp);
        this.campaignName = newCamp.campaign_name;
        this.showNewCampaignModal = false;
        this.newCampaignTitle = '';
        this.newCampaignNotes = '';
        this.rollToast.showMessage('🏰 CAMPAIGN CREATED', `Created campaign locally: ${newCamp.campaign_name}`);
      }
    });
  }

  saveCampaignNotes() {
    this.http.post(`${environment.apiBaseUrl}/campaigns/${this.campaignName}/notes`, {
      notes: this.campaignNotes
    }).subscribe({
      next: () => this.rollToast.showMessage('📝 NOTES SAVED', 'Campaign notes auto-saved to database.'),
      error: () => this.rollToast.showMessage('⚠️ SAVE FAILED', 'Failed to save campaign notes.')
    });
  }

  generateInviteCode() {
    this.http.post<any>(`${environment.apiBaseUrl}/campaigns/${this.campaignName}/invite-code`, {}).subscribe((res) => {
      this.inviteCode = res.invite_code;
    });
  }

  adjustHp(member: PartyMember, delta: number) {
    member.hp_current = Math.max(0, Math.min(member.hp_max, member.hp_current + delta));
  }

  toggleCondition(member: PartyMember, cond: string) {
    const idx = member.conditions.indexOf(cond);
    if (idx >= 0) member.conditions.splice(idx, 1);
    else member.conditions.push(cond);
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

    this.http.post(`${environment.apiBaseUrl}/campaigns/${encodeURIComponent(this.campaignName)}/roll-request`, {
      char_filename: charFilename,
      char_name: this.rollTargetMember,
      roll_type: this.rollType,
      stat: this.rollStat,
      reason: this.rollReason,
      is_secret: this.isSecretRoll
    }).subscribe({
      next: () => {
        const secTag = this.isSecretRoll ? ' 🔒 [SECRET]' : '';
        this.rollToast.showMessage('🎲 ROLL REQUEST SENT', `Issued ${this.rollType} (${this.rollStat}) to ${this.rollTargetMember}${secTag}.`);
      },
      error: () =>
        this.rollToast.showMessage('⚠️ REQUEST NOT SENT', `Could not reach ${this.rollTargetMember}.`)
    });
  }

  importPartyToInitiative(silent = false) {
    if (silent) {
      // Remove old campaign player combatants
      this.combatants = this.combatants.filter((c) => !c.is_player);
      // A campaign switch is a new table: the previous encounter's turn is void.
      this.activeCombatantId = null;
    }
    this.partyMembers.forEach((p) => {
      if (!this.combatants.some((c) => c.name === p.name)) {
        const dexVal = p.stats?.['DEX'] || 10;
        const dexMod = Math.floor((dexVal - 10) / 2);
        this.combatants.push({
          id: Math.random().toString(36).substring(2, 9),
          name: p.name,
          initiative: 10 + dexMod,
          hp: p.hp_current,
          max_hp: p.hp_max,
          ac: p.ac,
          dex: dexVal,
          is_player: true,
          portrait: p.portrait
        });
      }
    });
    this.sortCombatants();
    if (!silent) {
      this.rollToast.showMessage('👥 PARTY IMPORTED', 'Imported active party members into Initiative Tracker.');
    }
  }

  addCombatant() {
    if (!this.newCombatantName) return;
    this.combatants.push({
      id: Math.random().toString(36).substring(2, 9),
      name: this.newCombatantName,
      initiative: this.newCombatantInit,
      hp: this.newCombatantHp,
      max_hp: this.newCombatantHp,
      ac: 12,
      dex: 10,
      is_player: false,
    });
    this.sortCombatants();
    this.newCombatantName = '';
  }

  removeCombatant(idx: number) {
    const [removed] = this.combatants.splice(idx, 1);
    if (!removed || removed.id !== this.activeCombatantId) return;

    // The active combatant left the fight, so the turn passes to whoever slid
    // into its slot — or wraps to the top of the order if it was the last one.
    this.activeCombatantId = this.combatants[idx]?.id ?? this.combatants[0]?.id ?? null;
  }

  rollAllInitiative() {
    this.combatants.forEach((c) => {
      const dexMod = Math.floor((c.dex - 10) / 2);
      c.initiative = this.dice.rollD20(dexMod).total;
    });
    this.sortCombatants();
    this.rollToast.showMessage('🎲 INITIATIVE ROLLED', 'Rolled initiative for all active combatants!');
  }

  sortCombatants() {
    this.combatants.sort((a, b) => b.initiative - a.initiative);
  }

  nextTurn() {
    if (this.combatants.length === 0) {
      this.activeCombatantId = null;
      return;
    }

    // No active turn yet (-1) advances to the top of the order.
    const current = this.combatants.findIndex((c) => c.id === this.activeCombatantId);
    this.activeCombatantId = this.combatants[(current + 1) % this.combatants.length].id;
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

    this.encounterResult.monsters.forEach((m) => {
      const qty = m.quantity || 1;
      for (let i = 0; i < qty; i++) {
        const monsterName = qty > 1 ? `${m.name} ${i + 1}` : m.name;
        const dexMod = Math.floor((m.dex - 10) / 2);
        this.combatants.push({
          id: Math.random().toString(36).substring(2, 9),
          name: monsterName,
          initiative: 10 + dexMod,
          hp: m.hp,
          max_hp: m.hp,
          ac: m.ac,
          dex: m.dex,
          is_player: false,
          statblock: m.statblock_summary
        });
      }
    });
    this.sortCombatants();
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
    this.http.post<{ whisper: Whisper }>(
      `${environment.apiBaseUrl}/campaigns/${encodeURIComponent(this.campaignName)}/whisper`,
      {
        sender: 'DM',
        recipient: this.whisperRecipient,
        message: this.whisperMessage
      }
    ).subscribe({
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
