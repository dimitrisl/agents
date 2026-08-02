import { ChangeDetectionStrategy, Component, EventEmitter, Input, Output } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import {
  ForgeButtonDirective,
  ForgeInputDirective,
} from '../../../../shared/ui';
import type { InitiativeCombatant } from '../../dm.component';

@Component({
  selector: 'app-initiative-panel',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    ForgeButtonDirective,
    ForgeInputDirective,
  ],
  templateUrl: './initiative-panel.component.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class InitiativePanelComponent {
  @Input() combatants: InitiativeCombatant[] = [];
  @Input() activeTurnIndex = 0;
  @Input() newCombatantName = '';
  @Input() newCombatantInit = 10;
  @Input() newCombatantHp = 20;

  @Output() newCombatantNameChange = new EventEmitter<string>();
  @Output() newCombatantInitChange = new EventEmitter<number>();
  @Output() newCombatantHpChange = new EventEmitter<number>();
  @Output() importParty = new EventEmitter<void>();
  @Output() rollAll = new EventEmitter<void>();
  @Output() advanceTurn = new EventEmitter<void>();
  @Output() addCombatant = new EventEmitter<void>();
  @Output() openStatblock = new EventEmitter<InitiativeCombatant>();
  @Output() removeCombatant = new EventEmitter<number>();

  trackCombatant(_index: number, combatant: InitiativeCombatant): string {
    return combatant.id || combatant.name;
  }
}
