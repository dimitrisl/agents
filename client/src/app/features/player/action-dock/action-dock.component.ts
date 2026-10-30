import { ChangeDetectionStrategy, Component, EventEmitter, Output, Input } from '@angular/core';
import { ForgeButtonDirective } from '../../../shared/ui';

@Component({
  selector: 'app-action-dock',
  standalone: true,
  imports: [ForgeButtonDirective],
  templateUrl: './action-dock.component.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ActionDockComponent {
  @Input() canLevelUp = true;
  @Input() isGeneratingStrategy = false;
  /** The level-up analysis is an AI call; spins the button until it answers. */
  @Input() isLevelUpLoading = false;
  @Output() shortRest = new EventEmitter<void>();
  @Output() longRest = new EventEmitter<void>();
  @Output() levelUp = new EventEmitter<void>();
  @Output() audit = new EventEmitter<void>();
  @Output() strategy = new EventEmitter<void>();
  @Output() exportPdf = new EventEmitter<void>();
  @Output() importCharacter = new EventEmitter<void>();
}
