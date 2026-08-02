import { ChangeDetectionStrategy, Component, EventEmitter, Input, Output } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import {
  ForgeBadgeComponent,
  ForgeButtonDirective,
  ForgeSelectDirective,
  ForgeTextareaDirective,
} from '../../../shared/ui';
import type { RollRequest, Whisper } from '../../../core/models/campaign.model';
import type { PartyMember } from '../dm.component';

/**
 * The DM's live end of the table chatter: every whisper in both directions and
 * every roll request with the answer the player rolled, as they happen.
 *
 * Mirrors the player's whisper dock (`features/player/player.component.html`)
 * so both sides of the table read the same way.
 */
@Component({
  selector: 'app-dm-inbox',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    ForgeBadgeComponent,
    ForgeButtonDirective,
    ForgeSelectDirective,
    ForgeTextareaDirective,
  ],
  templateUrl: './dm-inbox.component.html',
  styleUrl: './dm-inbox.component.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class DmInboxComponent {
  @Input() open = false;
  @Input() campaignName = '';
  @Input() partyMembers: PartyMember[] = [];
  @Input() whispers: Whisper[] = [];
  @Input() rollRequests: RollRequest[] = [];
  @Input() unreadCount = 0;
  @Input() replyRecipient = 'All';
  @Input() replyMessage = '';
  @Input() isSendingReply = false;

  @Output() openChange = new EventEmitter<boolean>();
  @Output() replyRecipientChange = new EventEmitter<string>();
  @Output() replyMessageChange = new EventEmitter<string>();
  @Output() sendReply = new EventEmitter<void>();

  toggle(): void {
    this.openChange.emit(!this.open);
  }

  trackWhisper(index: number, whisper: Whisper): string {
    return whisper.id || `${whisper.timestamp || 'no-time'}-${index}`;
  }

  trackRollRequest(index: number, request: RollRequest): string {
    return request.id || `${request.created_at || 'no-time'}-${index}`;
  }

  /** A whisper the DM sent, as opposed to a player answering back. */
  isFromDm(whisper: Whisper): boolean {
    return whisper.sender === 'DM';
  }

  whisperDirection(whisper: Whisper): string {
    if (this.isFromDm(whisper)) {
      return whisper.recipient === 'All' ? 'Sent to everyone' : `Sent to ${whisper.recipient}`;
    }
    return `↩ ${whisper.sender} replied`;
  }

  rollRequestStatus(request: RollRequest): string {
    return request.status || 'pending';
  }

  /** Status colour is paired with an icon and a word — never colour alone. */
  rollRequestTone(request: RollRequest): 'accent' | 'success' | 'muted' {
    const status = this.rollRequestStatus(request);
    if (status === 'resolved') return 'success';
    if (status === 'pending') return 'accent';
    return 'muted';
  }

  rollRequestLabel(request: RollRequest): string {
    const status = this.rollRequestStatus(request);
    if (status === 'resolved') return '✓ Answered';
    if (status === 'pending') return '⏳ Waiting';
    return `✕ ${status}`;
  }

  formatTime(timestamp?: string): string {
    if (!timestamp) return 'Just now';

    // Mongo stores a naive UTC string; the trailing Z is what makes it read as
    // the player's local time rather than drifting by the timezone offset.
    const normalized = timestamp.includes('T') ? timestamp : `${timestamp.replace(' ', 'T')}Z`;
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
}
