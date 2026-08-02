import { Component, Input } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { DiceRoll, DiceService, RollMode } from '../../../core/services/dice.service';
import { RollToastService } from '../../../core/services/roll-toast.service';
import { ForgeButtonDirective, ForgeInputDirective } from '../../ui';

const MAX_DICE = 20;

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
  /** Follows the sheet's advantage toggle so the tray can't disagree with it. */
  @Input() rollMode: RollMode = 'normal';

  numDice = 1;
  modifier = 0;
  lastRoll: DiceRoll | null = null;
  rollHistory: DiceRoll[] = [];

  readonly diceSides = [4, 6, 8, 10, 12, 20, 100];

  constructor(
    private dice: DiceService,
    private rollToast: RollToastService
  ) {}

  roll(sides: number) {
    const roll = this.dice.roll({
      sides,
      numDice: this.diceCount,
      modifier: this.modifier,
      mode: this.rollMode,
    });

    this.lastRoll = roll;
    this.rollHistory.unshift(roll);

    this.rollToast.showRoll({
      title: `🎲 QUICK ROLL: ${this.diceCount}D${sides}${this.dice.modeLabel(roll.mode)}`,
      expression: roll.expression,
      raw: roll.raw,
      rolls: roll.rolls,
      sides: roll.sides,
      modifier: roll.modifier,
      total: roll.total,
      mode: roll.mode,
    });
  }

  /**
   * The typed count, clamped. Advantage needs no special case here: `DiceService`
   * already drops it for anything that isn't a single d20.
   */
  get diceCount(): number {
    return Math.min(MAX_DICE, Math.max(1, Math.floor(this.numDice) || 1));
  }
}
