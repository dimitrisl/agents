import { ChangeDetectionStrategy, Component, EventEmitter, Input, Output } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ForgeBadgeComponent, ForgeButtonDirective, ForgeInputDirective, ForgeModalComponent } from '../../../../shared/ui';
import { RollModeSelectorComponent } from '../../roll-mode-selector/roll-mode-selector.component';
import type { RollMode } from '../../../../core/services/dice.service';
import type { RollRequest } from '../../../../core/models/campaign.model';

/**
 * The DM asked for a roll; this is where the player decides how to answer it.
 *
 * Before #26 the client threw the dice the instant the request arrived, so
 * advantage, disadvantage and any situational bonus were unreachable on the one
 * roll where they matter most.
 */
@Component({
  selector: 'app-roll-request-modal',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    ForgeBadgeComponent,
    ForgeButtonDirective,
    ForgeInputDirective,
    ForgeModalComponent,
    RollModeSelectorComponent,
  ],
  templateUrl: './roll-request-modal.component.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class RollRequestModalComponent {
  @Input() open = false;
  @Input() request: RollRequest | null = null;
  /** `Perception` — what the sheet calls the thing being rolled. */
  @Input() modifierLabel = '';
  /** Read off the sheet: ability modifier plus proficiency where it applies. */
  @Input() baseModifier = 0;
  @Input() rollMode: RollMode = 'normal';
  @Input() situationalBonus = 0;
  @Input() secondsRemaining = 0;
  /** How many more requests are waiting behind this one. */
  @Input() queuedCount = 0;

  @Output() openChange = new EventEmitter<boolean>();
  @Output() rollModeChange = new EventEmitter<RollMode>();
  @Output() situationalBonusChange = new EventEmitter<number>();
  @Output() confirm = new EventEmitter<void>();
  @Output() dismiss = new EventEmitter<void>();

  get totalModifier(): number {
    return this.baseModifier + (this.situationalBonus || 0);
  }

  get totalModifierString(): string {
    const total = this.totalModifier;
    return total >= 0 ? `+${total}` : `${total}`;
  }

  /** Turns urgent only at the end, so the countdown is not a constant alarm. */
  get isRunningOut(): boolean {
    return this.secondsRemaining > 0 && this.secondsRemaining <= 10;
  }

  /**
   * The bonus is free-typed, so it arrives as a string from an empty field or as
   * `null` from a cleared number input. Anything unreadable is worth 0, never NaN
   * — a NaN here would silently poison the total the DM sees.
   */
  onSituationalBonusInput(value: unknown): void {
    const parsed = typeof value === 'number' ? value : parseInt(String(value ?? ''), 10);
    this.situationalBonusChange.emit(Number.isFinite(parsed) ? parsed : 0);
  }
}
