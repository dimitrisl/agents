import { ChangeDetectionStrategy, Component, EventEmitter, Input, Output } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ForgeButtonDirective, ForgeModalComponent } from '../../../../shared/ui';

@Component({
  selector: 'app-strategy-guide-modal',
  standalone: true,
  imports: [CommonModule, ForgeButtonDirective, ForgeModalComponent],
  templateUrl: './strategy-guide-modal.component.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class StrategyGuideModalComponent {
  @Input() open = false;
  @Input() isGenerating = false;
  @Input() strategyGuideText: string | null = null;

  @Output() closed = new EventEmitter<void>();
}
