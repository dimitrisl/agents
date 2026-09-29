import { Component, Input, Output, EventEmitter } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ForgeInputDirective } from '../../../shared/ui/forge-form-field/forge-input.directive';

@Component({
  selector: 'app-combat-stat-grid',
  standalone: true,
  imports: [CommonModule, FormsModule, ForgeInputDirective],
  templateUrl: './combat-stat-grid.component.html',
})
export class CombatStatGridComponent {
  @Input() editMode = false;
  @Input() armorClass = 0;
  @Input() proficiencyBonus = 0;
  @Input() speed = 0;
  @Input() passivePerception = 10;
  @Input() initiativeModifier?: number;

  @Output() armorClassChange = new EventEmitter<number>();
  @Output() speedChange = new EventEmitter<number>();

  formatSigned(value: number): string {
    return value >= 0 ? `+${value}` : `${value}`;
  }
}
