import { ChangeDetectionStrategy, Component, EventEmitter, Input, Output } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ForgeButtonDirective } from '../../../shared/ui';

@Component({
  selector: 'app-hit-points-control',
  standalone: true,
  imports: [CommonModule, ForgeButtonDirective],
  templateUrl: './hit-points-control.component.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class HitPointsControlComponent {
  @Input() current = 0;
  @Input() max = 0;
  @Input() temp = 0;
  @Input() deathSaves: { successes: number; failures: number } | undefined;

  @Output() hpDown = new EventEmitter<void>();
  @Output() hpUp = new EventEmitter<void>();
  @Output() tempDown = new EventEmitter<void>();
  @Output() tempUp = new EventEmitter<void>();
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
