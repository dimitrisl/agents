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
  @Output() rollModeChange = new EventEmitter<RollMode>();
}
