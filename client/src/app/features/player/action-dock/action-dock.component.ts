import { ChangeDetectionStrategy, Component, EventEmitter, Output } from '@angular/core';
import { ForgeButtonDirective } from '../../../shared/ui';

@Component({
  selector: 'app-action-dock',
  standalone: true,
  imports: [ForgeButtonDirective],
  templateUrl: './action-dock.component.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ActionDockComponent {
  @Output() shortRest = new EventEmitter<void>();
  @Output() longRest = new EventEmitter<void>();
  @Output() levelUp = new EventEmitter<void>();
  @Output() audit = new EventEmitter<void>();
  @Output() strategy = new EventEmitter<void>();
  @Output() exportPdf = new EventEmitter<void>();
}
