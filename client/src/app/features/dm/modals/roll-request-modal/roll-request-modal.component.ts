import { ChangeDetectionStrategy, Component, EventEmitter, Input, Output } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import {
  ForgeButtonDirective,
  ForgeInputDirective,
  ForgeModalComponent,
  ForgeSelectDirective,
} from '../../../../shared/ui';
import type { PartyMember } from '../../dm.component';

@Component({
  selector: 'app-roll-request-modal',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    ForgeButtonDirective,
    ForgeInputDirective,
    ForgeModalComponent,
    ForgeSelectDirective,
  ],
  templateUrl: './roll-request-modal.component.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class RollRequestModalComponent {
  readonly stats = ['STR', 'DEX', 'CON', 'INT', 'WIS', 'CHA'];

  @Input() open = false;
  @Input() partyMembers: PartyMember[] = [];
  @Input() rollTargetMember = '';
  @Input() rollType = 'saving_throw';
  @Input() rollStat = 'DEX';
  @Input() rollReason = '';
  @Input() isSecretRoll = false;

  @Output() openChange = new EventEmitter<boolean>();
  @Output() closed = new EventEmitter<void>();
  @Output() rollTargetMemberChange = new EventEmitter<string>();
  @Output() rollTypeChange = new EventEmitter<string>();
  @Output() rollStatChange = new EventEmitter<string>();
  @Output() rollReasonChange = new EventEmitter<string>();
  @Output() isSecretRollChange = new EventEmitter<boolean>();
  @Output() requestRoll = new EventEmitter<void>();
}
