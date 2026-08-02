import {
  AfterViewChecked,
  ChangeDetectionStrategy,
  Component,
  ElementRef,
  EventEmitter,
  Input,
  OnChanges,
  Output,
  ViewChild,
} from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import {
  ForgeBadgeComponent,
  ForgeButtonDirective,
  ForgeSelectDirective,
  ForgeTextareaDirective,
} from '../../../shared/ui';
import type { RollRequest, Whisper } from '../../../core/models/campaign.model';
import {
  buildInboxFeed,
  formatInboxTime,
  type InboxEntry,
} from '../../../core/models/campaign-inbox';
import type { PartyMember } from '../dm.component';

/**
 * The DM's live end of the table chatter: whispers in both directions and roll
 * requests with the answer the player rolled, in one chronological thread.
 *
 * Mirrors the player's dock (`features/player/player.component.html`) so both
 * sides of the table read the same way.
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
export class DmInboxComponent implements OnChanges, AfterViewChecked {
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

  @ViewChild('feedList') private feedList?: ElementRef<HTMLElement>;

  feed: InboxEntry[] = [];

  private pendingScroll = false;

  ngOnChanges(): void {
    this.feed = buildInboxFeed(this.whispers, this.rollRequests);
    this.pendingScroll = true;
  }

  /** A chat thread is only useful if it lands on the newest message. */
  ngAfterViewChecked(): void {
    if (!this.pendingScroll || !this.feedList) return;
    this.pendingScroll = false;
    const element = this.feedList.nativeElement;
    element.scrollTop = element.scrollHeight;
  }

  toggle(): void {
    this.openChange.emit(!this.open);
  }

  trackEntry(_index: number, entry: InboxEntry): string {
    return entry.key;
  }

  formatTime(timestamp?: string): string {
    return formatInboxTime(timestamp);
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
}
