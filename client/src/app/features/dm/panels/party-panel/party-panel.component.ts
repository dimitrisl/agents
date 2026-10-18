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
  readonly stats = ['STR', 'DEX', 'CON', 'INT', 'WIS', 'CHA'] as const;

  @Input({ required: true }) campaignName!: string;
  @Input() partyMembers: PartyMember[] = [];
  @Input() availableConditions: string[] = [];

  @Output() addMember = new EventEmitter<void>();
  @Output() adjustHp = new EventEmitter<{ member: PartyMember; delta: number }>();
  @Output() setHp = new EventEmitter<{ member: PartyMember; hp: number }>();
  @Output() quickStatRoll = new EventEmitter<{ member: PartyMember; stat: string }>();
  @Output() toggleCondition = new EventEmitter<{ member: PartyMember; condition: string }>();
  @Output() privateRollRequest = new EventEmitter<PartyMember>();
  @Output() removeMember = new EventEmitter<PartyMember>();

  conditionTone(member: PartyMember, condition: string): 'danger' | 'muted' {
    return member.conditions.includes(condition) ? 'danger' : 'muted';
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
