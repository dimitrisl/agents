import { ChangeDetectionStrategy, Component, EventEmitter, Input, Output } from '@angular/core';
import { NgClass } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { RollMode } from '../../../core/services/dice.service';

export type { RollMode };

@Component({
  selector: 'app-roll-mode-selector',
  standalone: true,
  imports: [FormsModule, NgClass],
  templateUrl: './roll-mode-selector.component.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class RollModeSelectorComponent {
  @Input() rollMode: RollMode = 'normal';

  /**
   * Radio groups are scoped by `name` across the whole document, not by component.
   * A second selector rendered at the same time — the roll-request prompt over the
   * sheet — must pass its own name, or picking a mode in one silently clears the other.
   */
  @Input() name = 'rollMode';

  /** The caption beside the control — the prompt words it differently. */
  @Input() label = 'Roll mode';

  @Output() rollModeChange = new EventEmitter<RollMode>();
}
