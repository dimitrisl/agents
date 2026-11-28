import { ChangeDetectionStrategy, Component, EventEmitter, Input, Output, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import {
  buildDamageDefensePills,
  computeAdjustedDamage,
  DamageDefensePill,
  DamageMitigationMode,
} from '../../../core/rules';
import { ForgeButtonDirective, ForgeIconComponent, ForgeModalComponent } from '../../../shared/ui';

@Component({
  selector: 'app-hit-points-control',
  standalone: true,
  imports: [CommonModule, FormsModule, ForgeButtonDirective, ForgeIconComponent, ForgeModalComponent],
  templateUrl: './hit-points-control.component.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class HitPointsControlComponent {
  @Input() current = 0;
  @Input() max = 0;
  @Input() temp = 0;
  @Input() deathSaves: { successes: number; failures: number } | undefined;
  @Input() isDeceasedByExhaustion = false;
  @Input() damageResistances: string[] = [];
  @Input() damageImmunities: string[] = [];
  @Input() damageVulnerabilities: string[] = [];
  @Input() activeConditions: string[] = [];

  @Output() hpChange = new EventEmitter<number>();
  @Output() tempChange = new EventEmitter<number>();
  @Output() deathSaveChange = new EventEmitter<{ type: 'successes' | 'failures'; value: number }>();
  @Output() rollDeathSave = new EventEmitter<void>();
  @Output() applyDamage = new EventEmitter<number>();
  @Output() damageImmuneApplied = new EventEmitter<{
    raw: number;
    label?: string | null;
    mode?: DamageMitigationMode;
  }>();
  @Output() applyHeal = new EventEmitter<number>();
  @Output() setTempHp = new EventEmitter<number>();

  modifierAmount: number | null = null;
  showQuickPad = signal(false);
  numpadValue = signal<string>('0');
  mitigationMode = signal<DamageMitigationMode>('raw');
  selectedDefenseKey = signal<string | null>(null);
  selectedDefenseLabel = signal<string | null>(null);

  readonly mitigationModes: ReadonlyArray<{ mode: DamageMitigationMode; label: string }> = [
    { mode: 'raw', label: 'Raw' },
    { mode: 'resist', label: '½ Resist' },
    { mode: 'vuln', label: '×2 Vuln' },
    { mode: 'immune', label: '0 Immune' },
  ];

  get percentage(): number {
    if (!this.max) return 0;
    return Math.max(0, Math.min(100, (this.current / this.max) * 100));
  }

  get deathSaveArray(): number[] {
    return [1, 2, 3];
  }

  get defensePills(): DamageDefensePill[] {
    const pills = buildDamageDefensePills(
      this.damageResistances,
      this.damageImmunities,
      this.damageVulnerabilities
    );
    const isPetrified = (this.activeConditions || []).some(
      (c) => String(c || '').trim().toLowerCase() === 'petrified'
    );
    if (isPetrified && !pills.some((p) => p.label.toLowerCase() === 'petrified (all)')) {
      pills.push({ label: 'Petrified (All)', mode: 'resist' });
    }
    return pills;
  }

  defensePillKey(pill: DamageDefensePill): string {
    return `${pill.mode}:${pill.label}`;
  }

  get rawNumpadAmount(): number {
    return Math.max(0, parseInt(this.numpadValue(), 10) || 0);
  }

  get adjustedDamageAmount(): number {
    return computeAdjustedDamage(this.rawNumpadAmount, this.mitigationMode());
  }

  openQuickPad(initial = 0) {
    this.numpadValue.set(initial > 0 ? String(initial) : '0');
    this.mitigationMode.set('raw');
    this.selectedDefenseKey.set(null);
    this.selectedDefenseLabel.set(null);
    this.showQuickPad.set(true);
  }

  closeQuickPad() {
    this.showQuickPad.set(false);
  }

  selectMitigationMode(mode: DamageMitigationMode) {
    this.mitigationMode.set(mode);
    this.selectedDefenseKey.set(null);
    this.selectedDefenseLabel.set(null);
  }

  toggleDefensePill(pill: DamageDefensePill) {
    const key = this.defensePillKey(pill);
    if (this.selectedDefenseKey() === key) {
      this.selectedDefenseKey.set(null);
      this.selectedDefenseLabel.set(null);
      this.mitigationMode.set('raw');
    } else {
      this.selectedDefenseKey.set(key);
      this.selectedDefenseLabel.set(pill.label);
      this.mitigationMode.set(pill.mode);
    }
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
    const raw = this.rawNumpadAmount;
    const adjusted = this.adjustedDamageAmount;
    if (raw > 0) {
      if (adjusted > 0) {
        this.applyDamage.emit(adjusted);
      } else {
        this.damageImmuneApplied.emit({
          raw,
          label: this.selectedDefenseLabel(),
          mode: this.mitigationMode(),
        });
      }
    }
    this.closeQuickPad();
  }

  executeHeal() {
    if (this.isDeceasedByExhaustion) return;
    const amt = parseInt(this.numpadValue(), 10) || 0;
    if (amt > 0) {
      this.applyHeal.emit(amt);
    }
    this.closeQuickPad();
  }

  executeSetTemp() {
    if (this.isDeceasedByExhaustion) return;
    const amt = parseInt(this.numpadValue(), 10) || 0;
    this.setTempHp.emit(amt);
    this.closeQuickPad();
  }

  applyHpChange(multiplier: number) {
    if (multiplier > 0 && this.isDeceasedByExhaustion) return;
    const amount = this.modifierAmount || 1;
    if (multiplier < 0) {
      this.applyDamage.emit(amount);
    } else {
      this.applyHeal.emit(amount);
    }
    this.modifierAmount = null;
  }

  applyTempHpChange(multiplier: number) {
    if (multiplier > 0 && this.isDeceasedByExhaustion) return;
    const amount = this.modifierAmount || 1;
    this.tempChange.emit(amount * multiplier);
    this.modifierAmount = null;
  }

  toggleDeathSave(type: 'successes' | 'failures', index: number) {
    if (this.isDeceasedByExhaustion) return;
    const currentCount = this.deathSaves ? this.deathSaves[type] : 0;
    const newValue = currentCount === index ? index - 1 : index;
    this.deathSaveChange.emit({ type, value: newValue });
  }

  triggerRollDeathSave() {
    if (this.isDeceasedByExhaustion) return;
    this.rollDeathSave.emit();
  }
}
