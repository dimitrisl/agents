import { ChangeDetectionStrategy, Component, EventEmitter, Input, Output } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import {
  ForgeBadgeComponent,
  ForgeButtonDirective,
  ForgeEmptyStateComponent,
  ForgeInputDirective,
} from '../../../../shared/ui';
import type { PartyMember } from '../../../../core/models/party.model';
import {
  ConditionCountermeasure,
  describeDmModifiers,
  detectConditionWarnings,
  speedLockReason,
} from '../../../../core/rules';
import { BrokenPortraitTracker } from '../../../../core/utils/portrait';

@Component({
  selector: 'app-party-panel',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    ForgeBadgeComponent,
    ForgeButtonDirective,
    ForgeEmptyStateComponent,
    ForgeInputDirective,
  ],
  templateUrl: './party-panel.component.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class PartyPanelComponent {
  readonly portraits = new BrokenPortraitTracker();
  readonly stats = ['STR', 'DEX', 'CON', 'INT', 'WIS', 'CHA'] as const;

  @Input({ required: true }) campaignName!: string;
  @Input() partyMembers: PartyMember[] = [];
  @Input() availableConditions: string[] = [];

  @Output() addMember = new EventEmitter<void>();
  @Output() distributeLoot = new EventEmitter<void>();
  @Output() longRest = new EventEmitter<void>();
  @Output() partyActionUnlock = new EventEmitter<{
    actionType: 'short_rest' | 'long_rest' | 'level_up' | 'suppress_magic_items';
    unlocked: boolean;
  }>();
  @Output() memberActionToggle = new EventEmitter<{
    member: PartyMember;
    field: 'dm_short_rest_unlocked' | 'dm_long_rest_unlocked' | 'dm_level_up_unlocked' | 'magic_items_suppressed' | 'exhaustion_bypass' | 'inspiration';
    value: boolean;
  }>();
  @Output() adjustExhaustion = new EventEmitter<{ member: PartyMember; delta: number }>();
  @Output() openModifiers = new EventEmitter<PartyMember>();
  @Output() adjustHp = new EventEmitter<{ member: PartyMember; delta: number }>();
  @Output() setHp = new EventEmitter<{ member: PartyMember; hp: number }>();
  @Output() quickStatRoll = new EventEmitter<{ member: PartyMember; stat: string }>();
  @Output() toggleCondition = new EventEmitter<{ member: PartyMember; condition: string }>();
  @Output() privateRollRequest = new EventEmitter<PartyMember>();
  @Output() removeMember = new EventEmitter<PartyMember>();

  get allMagicSuppressed(): boolean {
    const serverMembers = this.partyMembers.filter((m) => !!m.char_id);
    return serverMembers.length > 0 && serverMembers.every((m) => !!m.magic_items_suppressed);
  }

  get anyShortRestUnlocked(): boolean {
    return this.partyMembers.some((m) => !!m.char_id && !!m.dm_short_rest_unlocked);
  }

  get anyLongRestUnlocked(): boolean {
    return this.partyMembers.some((m) => !!m.char_id && !!m.dm_long_rest_unlocked);
  }

  get anyLevelUpUnlocked(): boolean {
    return this.partyMembers.some((m) => !!m.char_id && m.level < 20 && !!m.dm_level_up_unlocked);
  }

  dmModifierSummary(member: PartyMember): string[] {
    return describeDmModifiers(member.dm_modifiers);
  }

  conditionAntidotes(member: PartyMember): ConditionCountermeasure[] {
    return detectConditionWarnings(member, member.conditions || []);
  }

  speedLock(member: PartyMember): string | null {
    return speedLockReason(member);
  }

  hasStatusBadges(member: PartyMember): boolean {
    return !!(
      member.inspiration ||
      (member.exhaustion_level ?? 0) > 0 ||
      member.magic_items_suppressed ||
      this.dmModifierSummary(member).length > 0 ||
      member.dm_short_rest_unlocked ||
      member.dm_long_rest_unlocked ||
      member.dm_level_up_unlocked ||
      member.concentrating_on ||
      this.speedLock(member) ||
      this.conditionAntidotes(member).length > 0 ||
      (member.hp_current <= 0 && member.death_saves)
    );
  }

  isDeceasedByExhaustion(member: PartyMember): boolean {
    return (member.exhaustion_level ?? 0) >= 6 && !member.exhaustion_bypass;
  }

  hasCondition(member: PartyMember, condition: string): boolean {
    const low = condition.trim().toLowerCase();
    return (member.conditions || []).some((c) => String(c || '').trim().toLowerCase() === low);
  }

  conditionTone(member: PartyMember, condition: string): 'danger' | 'muted' {
    return this.hasCondition(member, condition) ? 'danger' : 'muted';
  }

  memberKey(member: PartyMember): string {
    return member.char_id || member.name;
  }

  trackMember(_index: number, member: PartyMember): string {
    return member.char_id || member.name;
  }

  /**
   * Committed on blur, clamped, and written back to the element — the field
   * used to mutate the member object straight through `ngModel`, which left the
   * roster holding a number nothing else in the workspace agreed with.
   */
  onHpInput(member: PartyMember, input: HTMLInputElement): void {
    const raw = (input.value || '').trim();
    let hp = member.hp_current;
    if (raw.startsWith('+') || raw.startsWith('-')) {
      const delta = parseInt(raw, 10);
      if (!isNaN(delta)) {
        hp = Math.max(0, Math.min(member.hp_max, member.hp_current + delta));
      }
    } else {
      const typed = parseInt(raw, 10);
      if (!isNaN(typed)) {
        hp = Math.max(0, Math.min(member.hp_max, typed));
      }
    }

    input.value = `${hp}`;
    this.setHp.emit({ member, hp });
  }

  hpPercent(member: PartyMember): number {
    if (!member.hp_max) return 0;
    return Math.max(0, Math.min(100, (member.hp_current / member.hp_max) * 100));
  }

  isConditionsOpen(member: PartyMember): boolean {
    return this.openConditionEditors.has(this.memberKey(member));
  }

  toggleConditions(member: PartyMember): void {
    const key = this.memberKey(member);
    const newSet = new Set(this.openConditionEditors);
    if (newSet.has(key)) {
      newSet.delete(key);
    } else {
      newSet.add(key);
    }
    this.openConditionEditors = newSet;
  }

  private openConditionEditors = new Set<string>();
}
