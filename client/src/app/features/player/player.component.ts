import { Component, OnInit, effect, OnDestroy } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { HttpClient } from '@angular/common/http';
import { Router } from '@angular/router';
import { EMPTY, Subject, Subscription, catchError, debounceTime, switchMap } from 'rxjs';
import { CharacterStateService } from '../../core/services/character-state.service';
import { DiceService, RollMode } from '../../core/services/dice.service';
import { RollToastService } from '../../core/services/roll-toast.service';
import { WebSocketService, WsMessage } from '../../core/services/websocket.service';
import { CharacterSchema, EquipmentItem } from '../../core/models/character.model';
import { Campaign, Whisper } from '../../core/models/campaign.model';
import {
  ForgeButtonDirective,
  ForgeCardComponent,
  ForgeEmptyStateComponent,
  ForgePageComponent,
  ForgeTab,
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
import { PortraitModalComponent } from './modals/portrait-modal/portrait-modal.component';
import { StrategyGuideModalComponent } from './modals/strategy-guide-modal/strategy-guide-modal.component';
import { EditSheetModalComponent } from './modals/edit-sheet-modal/edit-sheet-modal.component';
import { environment } from '../../../environments/environment';

export interface SkillDefinition {
  name: string;
  ability: 'STR' | 'DEX' | 'CON' | 'INT' | 'WIS' | 'CHA';
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
    PortraitModalComponent,
    StrategyGuideModalComponent,
    EditSheetModalComponent,
  ],
  templateUrl: './player.component.html',
  styleUrl: './player.component.css', 
})
export class PlayerComponent implements OnInit, OnDestroy {
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
  pdfPreviewUrl: string | null = null;
  pdfPreviewBlobUrl: string | null = null;
  whisperHistory: Whisper[] = [];
  unreadWhispers = 0;
  private loadedWhisperKey: string | null = null;

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
        this.wsService.connect(char.active_campaign);
        this.loadWhisperHistory(char.active_campaign, char.char_name);
      } else {
        this.wsService.disconnect();
        this.whisperHistory = [];
        this.unreadWhispers = 0;
        this.showWhisperInbox = false;
        this.loadedWhisperKey = null;
      }
    });
  }

  ngOnInit() {
    this.charState.ensureLoaded().subscribe();

    this.wsSub = this.wsService.messages$.subscribe((msg: WsMessage) => {
      const char = this.charState.activeCharacter();
      if (!char) return;

      if (msg.type === 'roll_request') {
        const req = msg['payload'];
        // Check if this request is for the active character
        const charId = req.char_filename.replace('.json', '').split('_').pop();
        if (char.char_id === charId || req.char_name === char.char_name) {
          const secText = req.is_secret ? '🔒 SECRET' : 'DM';
          const title = `⚠️ ${secText} ROLL REQUESTED`;
          const details = `The DM has requested a ${req.roll_type} (${req.stat}) check!\nReason: ${req.reason}`;
          this.rollToast.showMessage(title, details);

          // Execute the roll automatically (or we could open a modal, but auto-rolling is faster)
          this.executeRollRequest(req.roll_type, req.stat);
        }
      } else if (msg.type === 'whisper') {
        const whisper = msg['payload'];
        if (this.isWhisperForCharacter(whisper, char.char_name)) {
          this.addWhisper(whisper, true);
          this.rollToast.showMessage(`💬 WHISPER FROM ${whisper.sender}`, whisper.message);
        }
      }
    });
  }

  ngOnDestroy() {
    if (this.wsSub) {
      this.wsSub.unsubscribe();
    }
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

  /** Rolls a d20 in the sheet's current mode and pushes the result to the toast. */
  private showD20Roll(title: string, modifier: number) {
    const roll = this.dice.rollD20(modifier, this.rollMode);

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
  }

  rollSkillCheck(skill: SkillDefinition) {
    this.showD20Roll(`🎲 ${skill.name.toUpperCase()} CHECK`, this.getSkillModifier(skill));
  }

  rollAbilityCheck(stat: string) {
    const char = this.charState.activeCharacter();
    if (!char || !char.stats) return;
    const val = char.stats[stat] || 10;
    const mod = Math.floor((val - 10) / 2);

    this.showD20Roll(`🎲 ${stat} CHECK`, mod);
  }

  rollSavingThrow(stat: string) {
    const char = this.charState.activeCharacter();
    if (!char || !char.stats) return;
    const val = char.stats[stat] || 10;
    const mod = Math.floor((val - 10) / 2);
    const isSaveProf = char.saving_throws?.includes(stat);
    const profBonus = char.proficiency_bonus || 2;

    this.showD20Roll(`🛡️ ${stat} SAVING THROW`, mod + (isSaveProf ? profBonus : 0));
  }

  executeRollRequest(rollType: string, stat: string) {
    if (rollType.toLowerCase() === 'save') {
      this.rollSavingThrow(stat);
    } else if (rollType.toLowerCase() === 'skill') {
      const skill = this.allSkills.find(s => s.name.toLowerCase() === stat.toLowerCase());
      if (skill) this.rollSkillCheck(skill);
      else this.rollAbilityCheck(stat);
    } else {
      this.rollAbilityCheck(stat);
    }
  }

  toggleWhisperInbox(): void {
    this.showWhisperInbox = !this.showWhisperInbox;
    if (this.showWhisperInbox) {
      this.unreadWhispers = 0;
    }
  }

  closeWhisperInbox(): void {
    this.showWhisperInbox = false;
  }

  trackWhisper(index: number, whisper: Whisper): string {
    return whisper.id || `${whisper.timestamp || 'no-time'}-${index}`;
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

  private loadWhisperHistory(campaignName: string, characterName: string): void {
    const key = `${campaignName}::${characterName}`;
    if (this.loadedWhisperKey === key) return;
    this.loadedWhisperKey = key;

    this.http.get<Campaign[]>(`${environment.apiBaseUrl}/campaigns/`).subscribe({
      next: (campaigns) => {
        const campaign = campaigns.find((item) => item.campaign_name === campaignName);
        this.whisperHistory = (campaign?.whispers || [])
          .filter((whisper) => this.isWhisperForCharacter(whisper, characterName))
          .sort((a, b) => this.whisperSortValue(a) - this.whisperSortValue(b));
        this.unreadWhispers = 0;
      },
      error: () => {
        this.whisperHistory = [];
      },
    });
  }

  private addWhisper(whisper: Whisper, markUnread: boolean): void {
    if (whisper.id && this.whisperHistory.some((item) => item.id === whisper.id)) return;

    this.whisperHistory = [...this.whisperHistory, whisper].sort(
      (a, b) => this.whisperSortValue(a) - this.whisperSortValue(b)
    );

    if (markUnread && !this.showWhisperInbox) {
      this.unreadWhispers += 1;
    }
  }

  private isWhisperForCharacter(whisper: Whisper | undefined, characterName: string): boolean {
    return !!whisper && (whisper.recipient === characterName || whisper.recipient === 'All');
  }

  private whisperSortValue(whisper: Whisper): number {
    if (!whisper.timestamp) return 0;
    const normalized = whisper.timestamp.includes('T')
      ? whisper.timestamp
      : `${whisper.timestamp.replace(' ', 'T')}Z`;
    const value = new Date(normalized).getTime();
    return Number.isNaN(value) ? 0 : value;
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
        this.loadedWhisperKey = null;
        this.loadWhisperHistory(res.campaign_name, char.char_name);
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
