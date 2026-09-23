import { ChangeDetectionStrategy, Component, EventEmitter, Input, Output } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ForgeButtonDirective } from '../../../shared/ui';

@Component({
  selector: 'app-hit-points-control',
  standalone: true,
  imports: [CommonModule, FormsModule, ForgeButtonDirective],
  templateUrl: './hit-points-control.component.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class HitPointsControlComponent {
  @Input() current = 0;
  @Input() max = 0;
  @Input() temp = 0;
  @Input() deathSaves: { successes: number; failures: number } | undefined;

  @Output() hpChange = new EventEmitter<number>();
  @Output() tempChange = new EventEmitter<number>();
  modifierAmount: number | null = null;

  applyHpChange(multiplier: number) {
    const amount = this.modifierAmount || 1;
    this.hpChange.emit(amount * multiplier);
    this.modifierAmount = null;
  }

  applyTempHpChange(multiplier: number) {
    const amount = this.modifierAmount || 1;
    this.tempChange.emit(amount * multiplier);
    this.modifierAmount = null;
  }
  @Output() deathSaveChange = new EventEmitter<{ type: 'successes' | 'failures'; value: number }>();

  get percentage(): number {
    if (!this.max) return 0;
    return Math.max(0, Math.min(100, (this.current / this.max) * 100));
  }

  get deathSaveArray(): number[] {
    return [1, 2, 3];
  }

  toggleDeathSave(type: 'successes' | 'failures', index: number) {
    const currentCount = this.deathSaves ? this.deathSaves[type] : 0;
    // If clicking the current highest filled box, uncheck it
    const newValue = currentCount === index ? index - 1 : index;
    this.deathSaveChange.emit({ type, value: newValue });
  }
}
