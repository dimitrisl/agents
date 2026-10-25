import { CommonModule } from '@angular/common';
import { Component, EventEmitter, inject, Input, Output, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { DiceService, RollMode } from '../../../core/services/dice.service';
import { HapticsService } from '../../../core/services/haptics.service';
import { RollToastService } from '../../../core/services/roll-toast.service';
import { ForgeButtonDirective, ForgeModalComponent } from '../../../shared/ui';

@Component({
  selector: 'app-quick-dice-drawer',
  standalone: true,
  imports: [CommonModule, FormsModule, ForgeButtonDirective, ForgeModalComponent],
  templateUrl: './quick-dice-drawer.component.html',
})
export class QuickDiceDrawerComponent {
  @Input() open = false;
  @Input() rollMode: RollMode = 'normal';
  @Input() activeCampaign?: string;

  @Output() openChange = new EventEmitter<boolean>();
  @Output() rollModeChange = new EventEmitter<RollMode>();
  @Output() customRoll = new EventEmitter<{
    expression: string;
    total: number;
    rolls: number[];
    modifier: number;
    title: string;
    broadcast: boolean;
  }>();

  private dice = inject(DiceService);
  private haptics = inject(HapticsService);
  private toast = inject(RollToastService);

  readonly availableDice = [4, 6, 8, 10, 12, 20, 100];
  dicePool = signal<{ [key: number]: number }>({
    4: 0,
    6: 0,
    8: 0,
    10: 0,
    12: 0,
    20: 0,
    100: 0,
  });
  modifier = signal<number>(0);
  broadcastToTable = signal<boolean>(true);
  autoResetRollMode = signal<boolean>(true);

  lastRoll = signal<{
    expression: string;
    total: number;
    rolls: number[];
    modifier: number;
    isCritSuccess?: boolean;
    isCritFail?: boolean;
  } | null>(null);

  get totalDiceCount(): number {
    const pool = this.dicePool();
    return Object.values(pool).reduce((sum, count) => sum + count, 0);
  }

  get diceFormula(): string {
    const parts: string[] = [];
    const pool = this.dicePool();
    for (const d of this.availableDice) {
      const count = pool[d] || 0;
      if (count > 0) {
        parts.push(`${count}d${d}`);
      }
    }
    const mod = this.modifier();
    if (parts.length === 0) {
      return mod !== 0 ? (mod > 0 ? `+${mod}` : `${mod}`) : 'Pick dice...';
    }
    const diceStr = parts.join(' + ');
    if (mod > 0) return `${diceStr} + ${mod}`;
    if (mod < 0) return `${diceStr} - ${Math.abs(mod)}`;
    return diceStr;
  }

  addDie(sides: number) {
    this.haptics.lightTap();
    const pool = { ...this.dicePool() };
    pool[sides] = (pool[sides] || 0) + 1;
    this.dicePool.set(pool);
  }

  removeDie(sides: number, event: Event) {
    event.stopPropagation();
    this.haptics.lightTap();
    const pool = { ...this.dicePool() };
    if ((pool[sides] || 0) > 0) {
      pool[sides] -= 1;
      this.dicePool.set(pool);
    }
  }

  clearPool() {
    this.haptics.lightTap();
    this.dicePool.set({ 4: 0, 6: 0, 8: 0, 10: 0, 12: 0, 20: 0, 100: 0 });
    this.modifier.set(0);
  }

  adjustModifier(delta: number) {
    this.haptics.lightTap();
    this.modifier.set(this.modifier() + delta);
  }

  setRollMode(mode: RollMode) {
    this.haptics.lightTap();
    this.rollMode = mode;
    this.rollModeChange.emit(mode);
  }

  executeRoll() {
    const pool = this.dicePool();
    const count = this.totalDiceCount;
    if (count === 0 && this.modifier() === 0) {
      return;
    }

    // Special case: Single d20 roll with active rollMode
    if (count === 1 && pool[20] === 1) {
      const roll = this.dice.rollD20(this.modifier(), this.rollMode);
      const isCrit = roll.raw === 20;
      const isFail = roll.raw === 1;

      if (isCrit) this.haptics.critSuccess();
      else if (isFail) this.haptics.critFail();
      else this.haptics.lightTap();

      this.lastRoll.set({
        expression: roll.expression,
        total: roll.total,
        rolls: roll.rolls,
        modifier: roll.modifier,
        isCritSuccess: isCrit,
        isCritFail: isFail,
      });

      this.toast.showRoll({
        title: `🎲 QUICK D20 ROLL${this.dice.modeLabel(roll.mode)}`,
        expression: roll.expression,
        raw: roll.raw,
        rolls: roll.rolls,
        sides: 20,
        modifier: roll.modifier,
        total: roll.total,
        mode: roll.mode,
      });

      this.customRoll.emit({
        title: `🎲 Quick d20${this.dice.modeLabel(roll.mode)}`,
        expression: roll.expression,
        total: roll.total,
        rolls: roll.rolls,
        modifier: roll.modifier,
        broadcast: this.broadcastToTable(),
      });

      if (this.autoResetRollMode() && this.rollMode !== 'normal') {
        this.setRollMode('normal');
      }
      return;
    }

    // Multi-dice or other dice pool roll
    let total = 0;
    const allRolls: number[] = [];
    const formulaParts: string[] = [];
    let isCritSuccess = false;
    let isCritFail = false;

    for (const d of this.availableDice) {
      const c = pool[d] || 0;
      if (c > 0) {
        if (d === 20 && c === 1 && this.rollMode !== 'normal') {
          const d20Roll = this.dice.rollD20(0, this.rollMode);
          total += d20Roll.total;
          allRolls.push(...d20Roll.rolls);
          formulaParts.push(`1d20${this.dice.modeLabel(d20Roll.mode)}`);
          isCritSuccess = d20Roll.raw === 20;
          isCritFail = d20Roll.raw === 1;
        } else {
          const subRoll = this.dice.roll({ numDice: c, sides: d, modifier: 0 });
          total += subRoll.total;
          allRolls.push(...subRoll.rolls);
          formulaParts.push(`${c}d${d}`);
        }
      }
    }

    total += this.modifier();
    if (isCritSuccess) this.haptics.critSuccess();
    else if (isCritFail) this.haptics.critFail();
    else this.haptics.lightTap();

    const expr = `${formulaParts.join('+')}${this.modifier() !== 0 ? (this.modifier() > 0 ? '+' + this.modifier() : this.modifier()) : ''}`;

    this.lastRoll.set({
      expression: expr,
      total,
      rolls: allRolls,
      modifier: this.modifier(),
      isCritSuccess,
      isCritFail,
    });

    this.toast.showMessage('🎲 CUSTOM ROLL', `${expr} ➡️ **${total}** (${allRolls.join(', ')})`);

    this.customRoll.emit({
      title: `🎲 ${expr}`,
      expression: expr,
      total,
      rolls: allRolls,
      modifier: this.modifier(),
      broadcast: this.broadcastToTable(),
    });

    if (pool[20] === 1 && this.autoResetRollMode() && this.rollMode !== 'normal') {
      this.setRollMode('normal');
    }
  }

  close() {
    this.open = false;
    this.openChange.emit(false);
  }
}
