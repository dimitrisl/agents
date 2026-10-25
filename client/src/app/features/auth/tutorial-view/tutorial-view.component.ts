import { ChangeDetectionStrategy, Component, EventEmitter, Input, Output } from '@angular/core';
import { CommonModule } from '@angular/common';
import {
  ForgeBadgeComponent,
  ForgeButtonDirective,
  ForgeCardComponent,
  ForgeListRowComponent,
} from '../../../shared/ui';

const ACTIVE_DOT_CLASSES =
  'h-3 w-3 rounded-full bg-accent shadow-[0_0_10px_var(--theme-accent)] transition-all';
const ACTIVE_DOT_CLASSES_GOLD =
  'h-3 w-3 rounded-full bg-gold shadow-[0_0_10px_var(--color-gold,#d4af37)] transition-all';
const INACTIVE_DOT_CLASSES = 'h-3 w-3 rounded-full bg-tile transition-all';

@Component({
  selector: 'app-tutorial-view',
  standalone: true,
  imports: [
    CommonModule,
    ForgeBadgeComponent,
    ForgeButtonDirective,
    ForgeCardComponent,
    ForgeListRowComponent,
  ],
  templateUrl: './tutorial-view.component.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
  host: {
    class: 'block w-full max-w-lg',
  },
})
export class TutorialViewComponent {
  @Input() step = 0;
  @Input() role: 'none' | 'player' | 'dm' | 'intro' = 'none';
  @Output() stepChange = new EventEmitter<number>();
  @Output() roleChange = new EventEmitter<'none' | 'player' | 'dm' | 'intro'>();
  @Output() back = new EventEmitter<void>();
  @Output() finish = new EventEmitter<void>();

  selectRole(role: 'player' | 'dm' | 'intro'): void {
    this.role = role;
    this.roleChange.emit(role);
    this.stepChange.emit(0);
  }

  previous(): void {
    if (this.role === 'none') {
      this.back.emit();
    } else {
      if (this.step > 0) {
        this.stepChange.emit(this.step - 1);
      } else {
        this.role = 'none';
        this.roleChange.emit('none');
      }
    }
  }

  next(): void {
    this.stepChange.emit(this.step + 1);
  }

  dotClasses(index: number): string {
    if (this.step !== index) {
      return INACTIVE_DOT_CLASSES;
    }
    return this.role === 'intro' || this.role === 'dm' ? ACTIVE_DOT_CLASSES_GOLD : ACTIVE_DOT_CLASSES;
  }
}
