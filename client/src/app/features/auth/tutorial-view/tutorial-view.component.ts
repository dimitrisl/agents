import { ChangeDetectionStrategy, Component, EventEmitter, Input, Output } from '@angular/core';
import { ForgeButtonDirective, ForgeCardComponent } from '../../../shared/ui';

const ACTIVE_DOT_CLASSES = 'h-3 w-3 rounded-full bg-accent shadow-[0_0_10px_var(--theme-accent)] transition-all';
const INACTIVE_DOT_CLASSES = 'h-3 w-3 rounded-full bg-white/20 transition-all';

@Component({
  selector: 'app-tutorial-view',
  standalone: true,
  imports: [ForgeButtonDirective, ForgeCardComponent],
  templateUrl: './tutorial-view.component.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
  host: {
    class: 'block w-full max-w-lg',
  },
})
export class TutorialViewComponent {
  @Input() step = 0;
  @Output() stepChange = new EventEmitter<number>();
  @Output() back = new EventEmitter<void>();
  @Output() finish = new EventEmitter<void>();

  previous(): void {
    if (this.step > 0) {
      this.stepChange.emit(this.step - 1);
    } else {
      this.back.emit();
    }
  }

  next(): void {
    this.stepChange.emit(this.step + 1);
  }

  dotClasses(index: number): string {
    return this.step === index ? ACTIVE_DOT_CLASSES : INACTIVE_DOT_CLASSES;
  }
}
