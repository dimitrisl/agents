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

  @Output() hpDown = new EventEmitter<void>();
  @Output() hpUp = new EventEmitter<void>();

  get percentage(): number {
    if (!this.max) return 0;
    return Math.max(0, Math.min(100, (this.current / this.max) * 100));
  }
}
