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
  readonly stats = ['STR', 'DEX', 'CON', 'INT', 'WIS', 'CHA'];

  @Input({ required: true }) campaignName!: string;
  @Input() partyMembers: PartyMember[] = [];
  @Input() availableConditions: string[] = [];

  @Output() addMember = new EventEmitter<void>();
  @Output() adjustHp = new EventEmitter<{ member: PartyMember; delta: number }>();
  @Output() setHp = new EventEmitter<{ member: PartyMember; hp: number }>();
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

  /**
   * Committed on blur, clamped, and written back to the element — the field
   * used to mutate the member object straight through `ngModel`, which left the
   * roster holding a number nothing else in the workspace agreed with.
   */
  onHpInput(member: PartyMember, input: HTMLInputElement): void {
    const typed = input.valueAsNumber;
    const hp = Number.isFinite(typed)
      ? Math.max(0, Math.min(member.hp_max, Math.round(typed)))
      : member.hp_current;

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
    if (this.openConditionEditors.has(key)) {
      this.openConditionEditors.delete(key);
    } else {
      this.openConditionEditors.add(key);
    }
  }

  private readonly openConditionEditors = new Set<string>();
}
