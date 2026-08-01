import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { RollToastService } from '../../../core/services/roll-toast.service';
import { ForgeButtonDirective, ForgeInputDirective } from '../../ui';

@Component({
  selector: 'app-dice-roller',
  standalone: true,
  imports: [CommonModule, FormsModule, ForgeButtonDirective, ForgeInputDirective],
  templateUrl: './dice-roller.component.html',
  host: {
    class: 'block',
  },
})
export class DiceRollerComponent {
  modifier = 0;
  lastRoll: any = null;
  rollHistory: any[] = [];

  constructor(private rollToast: RollToastService) {}

  roll(sides: number) {
    const raw = Math.floor(Math.random() * sides) + 1;
    const total = raw + this.modifier;
    const expression = `1d${sides} (${raw}) ${this.modifier >= 0 ? '+' + this.modifier : this.modifier}`;

    const rollData = {
      sides,
      rolls: [raw],
      modifier: this.modifier,
      total,
      expression,
    };

    this.lastRoll = rollData;
    this.rollHistory.unshift(rollData);

    this.rollToast.showRoll({
      title: `🎲 QUICK ROLL: D${sides}`,
      expression,
      raw,
      rolls: [raw],
      sides,
      modifier: this.modifier,
      total
    });
  }
}
