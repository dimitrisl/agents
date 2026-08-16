import { ChangeDetectionStrategy, Component, EventEmitter, Input, Output } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ForgeButtonDirective, ForgeModalComponent } from '../../../../shared/ui';
import type { InitiativeCombatant } from '../../dm.component';

@Component({
  selector: 'app-statblock-modal',
  standalone: true,
  imports: [CommonModule, ForgeButtonDirective, ForgeModalComponent],
  templateUrl: './statblock-modal.component.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class StatblockModalComponent {
  @Input() open = false;
  @Input() combatant: InitiativeCombatant | null = null;

  @Output() openChange = new EventEmitter<boolean>();
  @Output() closed = new EventEmitter<void>();
  @Output() viewBeyond = new EventEmitter<string>();
}
