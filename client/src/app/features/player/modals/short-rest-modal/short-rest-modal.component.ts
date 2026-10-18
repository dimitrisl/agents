import { ChangeDetectionStrategy, Component, EventEmitter, Input, Output } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import {
  ForgeButtonDirective,
  ForgeInputDirective,
  ForgeModalComponent,
  ForgeSelectDirective,
} from '../../../../shared/ui';
import { HitDieOption } from '../../../../core/rules/rest';

@Component({
  selector: 'app-short-rest-modal',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    ForgeButtonDirective,
    ForgeInputDirective,
    ForgeModalComponent,
    ForgeSelectDirective,
  ],
  templateUrl: './short-rest-modal.component.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ShortRestModalComponent {
  @Input() open = false;
  @Input() classHitDieSize = 8;
  @Input() conModifier = 0;
  @Input() availableHitDice = 0;
  @Input() hasPactSlots = false;
  @Input() characterLevel?: number;
  @Input() shortRestDiceToSpend = 1;
  @Input() hitDieOptions: HitDieOption[] = [];
  @Input() selectedDieSize = 8;

  @Output() openChange = new EventEmitter<boolean>();
  @Output() shortRestDiceToSpendChange = new EventEmitter<number>();
  @Output() selectedDieSizeChange = new EventEmitter<number>();
  @Output() executeShortRest = new EventEmitter<void>();

  get selectedClassMaxDice(): number {
    if (this.hitDieOptions && this.hitDieOptions.length > 1) {
      const matchingLevels = this.hitDieOptions
        .filter((opt) => opt.dieSize === this.selectedDieSize)
        .reduce((sum, opt) => sum + (opt.level || 0), 0);
      if (matchingLevels > 0) {
        return Math.min(this.availableHitDice, matchingLevels);
      }
    }
    return this.availableHitDice;
  }
}
