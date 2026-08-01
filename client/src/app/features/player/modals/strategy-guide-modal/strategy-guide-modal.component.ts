import { ChangeDetectionStrategy, Component, EventEmitter, Input, Output } from '@angular/core';
import { ForgeButtonDirective, ForgeModalComponent } from '../../../../shared/ui';

@Component({
  selector: 'app-strategy-guide-modal',
  standalone: true,
  imports: [ForgeButtonDirective, ForgeModalComponent],
  templateUrl: './strategy-guide-modal.component.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class StrategyGuideModalComponent {
  @Input() open = false;
  @Input() strategyGuideText: string | null = null;

  @Output() closed = new EventEmitter<void>();
}
