import { ChangeDetectionStrategy, Component, EventEmitter, Input, Output } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import {
  ForgeButtonDirective,
  ForgeModalComponent,
  ForgeSelectDirective,
  ForgeTextareaDirective,
} from '../../../../shared/ui';
import type { PartyMember } from '../../dm.component';

@Component({
  selector: 'app-whisper-modal',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    ForgeButtonDirective,
    ForgeModalComponent,
    ForgeSelectDirective,
    ForgeTextareaDirective,
  ],
  templateUrl: './whisper-modal.component.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class WhisperModalComponent {
  @Input() open = false;
  @Input() partyMembers: PartyMember[] = [];
  @Input() whisperRecipient = 'All';
  @Input() whisperMessage = '';

  @Output() openChange = new EventEmitter<boolean>();
  @Output() closed = new EventEmitter<void>();
  @Output() whisperRecipientChange = new EventEmitter<string>();
  @Output() whisperMessageChange = new EventEmitter<string>();
  @Output() send = new EventEmitter<void>();
}
