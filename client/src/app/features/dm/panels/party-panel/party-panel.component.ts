import { ChangeDetectionStrategy, Component, EventEmitter, Input, Output } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import {
  ForgeBadgeComponent,
  ForgeButtonDirective,
  ForgeCardComponent,
  ForgeEmptyStateComponent,
  ForgeInputDirective,
  ForgeMetricComponent,
  ForgeMetricStripComponent,
  ForgeSectionComponent,
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
    ForgeCardComponent,
    ForgeEmptyStateComponent,
    ForgeInputDirective,
    ForgeMetricComponent,
    ForgeMetricStripComponent,
    ForgeSectionComponent,
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
}
