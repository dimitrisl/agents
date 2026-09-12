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
import type { PartyMember } from '../../../core/models/party.model';

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
  rollRequestTone(request: RollRequest): 'accent' | 'success' | 'muted' | 'gold' {
    const status = this.rollRequestStatus(request);
    if (status === 'resolved') return 'success';
    if (status === 'pending') return 'accent';
    // A missed roll is not the same as one the DM withdrew: someone was asked and
    // never answered, and that is worth reading differently from a cancellation.
    if (status === 'missed') return 'gold';
    return 'muted';
  }

  rollRequestLabel(request: RollRequest): string {
    const status = this.rollRequestStatus(request);
    // A secret roll was never asked of anyone, so "answered" would misdescribe it.
    if (request.rolled_by === 'dm') return '🔒 You rolled it';
    if (status === 'resolved') return '✓ Answered';
    if (status === 'pending') return '⏳ Waiting';
    if (status === 'missed') return '⌛ No answer';
    return `✕ ${status}`;
  }

  /**
   * `ability_check` + `WIS` reads as `WIS ability check`. The raw enum on its own
   * line was what forced the old layout to truncate the hero's name.
   */
  rollAsk(request: RollRequest): string {
    const type = (request.roll_type || '').toLowerCase().replace(/[\s-]+/g, '_');
    const stat = request.stat;

    if (type === 'save' || type === 'saving_throw' || type === 'savingthrow') {
      return `${stat} saving throw`;
    }
    if (type === 'attack_roll') return `${stat} attack roll`;
    if (type === 'skill' || type === 'skill_check') return `${stat} check`;
    return `${stat} ability check`;
  }

  /**
   * How the player chose to throw it. Blank on a straight roll, and on anything
   * rolled before the client started reporting the mode at all.
   */
  rollModeLabel(request: RollRequest): string {
    const mode = request.result?.mode;
    if (!mode || mode === 'normal') return '';
    return mode === 'advantage' ? '▲ Advantage' : '▼ Disadvantage';
  }

  /** The part of the total the player added by hand, if any. */
  situationalBonusLabel(request: RollRequest): string {
    const bonus = request.result?.situational_bonus;
    if (!bonus) return '';
    return `${bonus > 0 ? '+' : ''}${bonus} situational`;
  }
}
