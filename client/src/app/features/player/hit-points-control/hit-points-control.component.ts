import { ChangeDetectionStrategy, Component, EventEmitter, Input, Output, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ForgeButtonDirective, ForgeModalComponent } from '../../../shared/ui';

@Component({
  selector: 'app-hit-points-control',
  standalone: true,
  imports: [CommonModule, FormsModule, ForgeButtonDirective, ForgeModalComponent],
  templateUrl: './hit-points-control.component.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class HitPointsControlComponent {
  @Input() current = 0;
  @Input() max = 0;
  @Input() temp = 0;
  @Input() deathSaves: { successes: number; failures: number } | undefined;

  @Output() hpChange = new EventEmitter<number>();
  @Output() tempChange = new EventEmitter<number>();
  @Output() deathSaveChange = new EventEmitter<{ type: 'successes' | 'failures'; value: number }>();
  @Output() rollDeathSave = new EventEmitter<void>();
  @Output() applyDamage = new EventEmitter<number>();
  @Output() applyHeal = new EventEmitter<number>();
  @Output() setTempHp = new EventEmitter<number>();

  modifierAmount: number | null = null;
  showQuickPad = signal(false);
  numpadValue = signal<string>('0');

  get percentage(): number {
    if (!this.max) return 0;
    return Math.max(0, Math.min(100, (this.current / this.max) * 100));
  }

  get deathSaveArray(): number[] {
    return [1, 2, 3];
  }

  openQuickPad(initial = 0) {
    this.numpadValue.set(initial > 0 ? String(initial) : '0');
    this.showQuickPad.set(true);
  }

  closeQuickPad() {
    this.showQuickPad.set(false);
  }

  appendDigit(digit: string) {
    const cur = this.numpadValue();
    if (cur === '0') {
      this.numpadValue.set(digit);
    } else if (cur.length < 5) {
      this.numpadValue.set(cur + digit);
    }
  }

  backspace() {
    const cur = this.numpadValue();
    if (cur.length <= 1) {
      this.numpadValue.set('0');
    } else {
      this.numpadValue.set(cur.slice(0, -1));
    }
  }

  clearNumpad() {
    this.numpadValue.set('0');
  }

  addPill(amount: number) {
    const cur = parseInt(this.numpadValue(), 10) || 0;
    this.numpadValue.set(String(cur + amount));
  }

  executeDamage() {
    const amt = parseInt(this.numpadValue(), 10) || 0;
    if (amt > 0) {
      this.applyDamage.emit(amt);
    }
    this.closeQuickPad();
  }

  executeHeal() {
    const amt = parseInt(this.numpadValue(), 10) || 0;
    if (amt > 0) {
      this.applyHeal.emit(amt);
    }
    this.closeQuickPad();
  }

  executeSetTemp() {
    const amt = parseInt(this.numpadValue(), 10) || 0;
    this.setTempHp.emit(amt);
    this.closeQuickPad();
  }

  applyHpChange(multiplier: number) {
    const amount = this.modifierAmount || 1;
    if (multiplier < 0) {
      this.applyDamage.emit(amount);
    } else {
      this.applyHeal.emit(amount);
    }
    this.modifierAmount = null;
  }

  applyTempHpChange(multiplier: number) {
    const amount = this.modifierAmount || 1;
    this.tempChange.emit(amount * multiplier);
    this.modifierAmount = null;
  }

  toggleDeathSave(type: 'successes' | 'failures', index: number) {
    const currentCount = this.deathSaves ? this.deathSaves[type] : 0;
    const newValue = currentCount === index ? index - 1 : index;
    this.deathSaveChange.emit({ type, value: newValue });
  }

  triggerRollDeathSave() {
    this.rollDeathSave.emit();
  }
}
