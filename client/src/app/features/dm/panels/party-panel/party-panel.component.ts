import { ChangeDetectionStrategy, Component, EventEmitter, Input, Output } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import {
  ForgeBadgeComponent,
  ForgeButtonDirective,
  ForgeEmptyStateComponent,
  ForgeInputDirective,
} from '../../../../shared/ui';
import type { PartyMember } from '../../dm.component';

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
  readonly stats = ['STR', 'DEX', 'CON', 'INT', 'WIS', 'CHA'];

  @Input({ required: true }) campaignName!: string;
  @Input() partyMembers: PartyMember[] = [];
  @Input() availableConditions: string[] = [];

  @Output() addMember = new EventEmitter<void>();
  @Output() issueRollRequest = new EventEmitter<void>();
  @Output() adjustHp = new EventEmitter<{ member: PartyMember; delta: number }>();
  @Output() quickStatRoll = new EventEmitter<{ member: PartyMember; stat: string }>();
  @Output() toggleCondition = new EventEmitter<{ member: PartyMember; condition: string }>();
  @Output() privateRollRequest = new EventEmitter<PartyMember>();

  conditionTone(member: PartyMember, condition: string): 'danger' | 'muted' {
    return member.conditions.includes(condition) ? 'danger' : 'muted';
  }

  memberKey(member: PartyMember): string {
    return member.char_id || member.name;
  }

  trackMember(_index: number, member: PartyMember): string {
    return member.char_id || member.name;
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
    if (this.openConditionEditors.has(key)) {
      this.openConditionEditors.delete(key);
    } else {
      this.openConditionEditors.add(key);
    }
  }

  private readonly openConditionEditors = new Set<string>();
}
