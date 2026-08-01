import { ChangeDetectionStrategy, Component, EventEmitter, Input, Output } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ForgeButtonDirective, ForgeInputDirective, ForgeModalComponent } from '../../../../shared/ui';

@Component({
  selector: 'app-short-rest-modal',
  standalone: true,
  imports: [CommonModule, FormsModule, ForgeButtonDirective, ForgeInputDirective, ForgeModalComponent],
  templateUrl: './short-rest-modal.component.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ShortRestModalComponent {
  @Input() open = false;
  @Input() classHitDieSize = 8;
  @Input() conModifier = 0;
  @Input() availableHitDice = 0;
  @Input() characterLevel?: number;
  @Input() shortRestDiceToSpend = 1;

  @Output() openChange = new EventEmitter<boolean>();
  @Output() shortRestDiceToSpendChange = new EventEmitter<number>();
  @Output() executeShortRest = new EventEmitter<void>();
}
