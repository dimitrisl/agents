import { Component, Input } from '@angular/core';
import { CommonModule } from '@angular/common';

@Component({
  selector: 'app-combat-stat-grid',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './combat-stat-grid.component.html',
})
export class CombatStatGridComponent {
  @Input() armorClass = 0;
  @Input() proficiencyBonus = 0;
  @Input() speed = 0;
  @Input() passivePerception = 10;
  @Input() initiativeModifier?: number;

  formatSigned(value: number): string {
    return value >= 0 ? `+${value}` : `${value}`;
  }
}
