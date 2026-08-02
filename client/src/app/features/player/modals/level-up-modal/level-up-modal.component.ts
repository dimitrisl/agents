import { ChangeDetectionStrategy, Component, EventEmitter, Input, Output } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ForgeButtonDirective, ForgeModalComponent } from '../../../../shared/ui';

@Component({
  selector: 'app-level-up-modal',
  standalone: true,
  imports: [CommonModule, ForgeButtonDirective, ForgeModalComponent],
  templateUrl: './level-up-modal.component.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class LevelUpModalComponent {
  @Input() open = false;
  @Input() nextLevel = 1;
  @Input() levelUpAnalysis: any = null;

  @Output() openChange = new EventEmitter<boolean>();
  @Output() applyLevelUp = new EventEmitter<void>();
}
