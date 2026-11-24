import { ChangeDetectionStrategy, Component, EventEmitter, Input, Output } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import {
  ForgeBadgeComponent,
  ForgeButtonDirective,
  ForgeIconComponent,
  ForgeInputDirective,
  ForgeModalComponent,
  ForgeSelectDirective,
} from '../../../../shared/ui';
import { CharacterSchema } from '../../../../core/models/character.model';
import { HitDieOption } from '../../../../core/rules/rest';

export type ShortRestRecoveryKind = 'arcane' | 'natural';

export interface RecoverySectionConfig {
  kind: ShortRestRecoveryKind;
  title: string;
  budget: number;
  spent: number;
}

@Component({
  selector: 'app-short-rest-modal',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    ForgeBadgeComponent,
    ForgeButtonDirective,
    ForgeIconComponent,
    ForgeInputDirective,
    ForgeModalComponent,
    ForgeSelectDirective,
  ],
  templateUrl: './short-rest-modal.component.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ShortRestModalComponent {
  readonly recoveryLevels = [1, 2, 3, 4, 5] as const;

  @Input() open = false;
  @Input() classHitDieSize = 8;
  @Input() conModifier = 0;
  @Input() availableHitDice = 0;
  @Input() hasPactSlots = false;
  @Input() characterLevel?: number;
  @Input() shortRestDiceToSpend = 1;
  @Input() hitDieOptions: HitDieOption[] = [];
  @Input() selectedDieSize = 8;
  @Input() manualHp: number | null = null;
  @Input() songOfRestDie: string | null = null;
  @Input() arcaneRecoveryBudget = 0;
  @Input() naturalRecoveryBudget = 0;
  @Input() harnessMaxSlotLevel = 0;
  @Input() spellSlots: CharacterSchema['spell_slots'] | Record<string, { max?: number; used?: number }> | null | undefined = null;
  @Input() arcaneRecoverySlots: Record<number, number> = {};
  @Input() naturalRecoverySlots: Record<number, number> = {};
  @Input() harnessDivinePowerSlot: number | null = null;

  @Output() openChange = new EventEmitter<boolean>();
  @Output() shortRestDiceToSpendChange = new EventEmitter<number>();
  @Output() selectedDieSizeChange = new EventEmitter<number>();
  @Output() manualHpChange = new EventEmitter<number | null>();
  @Output() arcaneRecoverySlotsChange = new EventEmitter<Record<number, number>>();
  @Output() naturalRecoverySlotsChange = new EventEmitter<Record<number, number>>();
  @Output() harnessDivinePowerSlotChange = new EventEmitter<number | null>();
  @Output() executeShortRest = new EventEmitter<void>();

  get selectedClassMaxDice(): number {
    if (this.hitDieOptions && this.hitDieOptions.length > 1) {
      const matchingLevels = this.hitDieOptions
        .filter((opt) => opt.dieSize === this.selectedDieSize)
        .reduce((sum, opt) => sum + (opt.level || 0), 0);
      if (matchingLevels > 0) {
        return Math.min(this.availableHitDice, matchingLevels);
      }
    }
    return this.availableHitDice;
  }

  get canRecoverWithoutDice(): boolean {
    return (
      this.hasPactSlots ||
      this.arcaneRecoveryBudget > 0 ||
      this.naturalRecoveryBudget > 0 ||
      this.harnessMaxSlotLevel > 0
    );
  }

  get arcaneRecoverySpent(): number {
    return this.sumRecoveryLevels(this.arcaneRecoverySlots);
  }

  get naturalRecoverySpent(): number {
    return this.sumRecoveryLevels(this.naturalRecoverySlots);
  }

  get recoverySections(): RecoverySectionConfig[] {
    const sections: RecoverySectionConfig[] = [];
    if (this.arcaneRecoveryBudget > 0) {
      sections.push({
        kind: 'arcane',
        title: '🔮 Arcane Recovery',
        budget: this.arcaneRecoveryBudget,
        spent: this.arcaneRecoverySpent,
      });
    }
    if (this.naturalRecoveryBudget > 0) {
      sections.push({
        kind: 'natural',
        title: '🌿 Natural Recovery',
        budget: this.naturalRecoveryBudget,
        spent: this.naturalRecoverySpent,
      });
    }
    return sections;
  }

  get harnessLevels(): number[] {
    const cap = Math.min(3, Math.max(0, Math.trunc(this.harnessMaxSlotLevel || 0)));
    return Array.from({ length: cap }, (_, i) => i + 1);
  }

  get recoveryBudgetInvalid(): boolean {
    if (this.arcaneRecoverySpent > this.arcaneRecoveryBudget) return true;
    if (this.naturalRecoverySpent > this.naturalRecoveryBudget) return true;
    if (
      this.harnessDivinePowerSlot != null &&
      (this.harnessDivinePowerSlot < 1 || this.harnessDivinePowerSlot > this.harnessMaxSlotLevel)
    ) {
      return true;
    }
    for (const lvl of this.recoveryLevels) {
      if (this.allocatedForLevel(lvl) > this.expendedCount(lvl)) {
        return true;
      }
    }
    return false;
  }

  get primaryActionLabel(): string {
    if (this.availableHitDice > 0 && this.shortRestDiceToSpend > 0) {
      return '⛺ Spend Hit Dice & Heal';
    }
    if (
      this.hasPactSlots &&
      this.arcaneRecoveryBudget === 0 &&
      this.naturalRecoveryBudget === 0 &&
      this.harnessMaxSlotLevel === 0
    ) {
      return '⛺ Take Short Rest (Recover Pact Slots)';
    }
    const maxCheckLevel = Math.max(
      this.arcaneRecoveryBudget > 0 || this.naturalRecoveryBudget > 0 ? 5 : 0,
      this.harnessMaxSlotLevel || 0
    );
    if (!this.hasPactSlots && !this.hasExpendedSlots(maxCheckLevel)) {
      return '⛺ Complete Short Rest';
    }
    return '⛺ Take Short Rest (Recover Spell Slots)';
  }

  expendedCount(level: number): number {
    const slots = this.spellSlots as
      | Record<string, { max?: number; used?: number; level?: number; pact_used?: number }>
      | null
      | undefined;
    const pool = slots?.[`level_${level}`] ?? slots?.[String(level)];
    const rawUsed = Math.max(0, Math.trunc(Number(pool?.used ?? 0) || 0));
    const pactUsed = Math.max(
      0,
      Math.trunc(
        Number(
          pool?.pact_used ??
            (Number(slots?.['pact']?.level) === level ? (slots?.['pact']?.used ?? 0) : 0)
        ) || 0
      )
    );
    return Math.max(0, rawUsed - pactUsed);
  }

  hasExpendedSlots(maxLevel: number): boolean {
    for (let lvl = 1; lvl <= maxLevel; lvl++) {
      if (this.expendedCount(lvl) > 0) return true;
    }
    return false;
  }

  recoveryCount(kind: ShortRestRecoveryKind, level: number): number {
    const map = kind === 'arcane' ? this.arcaneRecoverySlots : this.naturalRecoverySlots;
    return Math.max(0, Math.trunc(Number(map?.[level] ?? 0) || 0));
  }

  remainingExpended(level: number): number {
    return Math.max(0, this.expendedCount(level) - this.allocatedForLevel(level));
  }

  canIncrementRecovery(kind: ShortRestRecoveryKind, level: number): boolean {
    const budget = kind === 'arcane' ? this.arcaneRecoveryBudget : this.naturalRecoveryBudget;
    const spent = kind === 'arcane' ? this.arcaneRecoverySpent : this.naturalRecoverySpent;
    return level <= 5 && spent + level <= budget && this.remainingExpended(level) > 0;
  }

  adjustRecovery(kind: ShortRestRecoveryKind, level: number, delta: number): void {
    const currentMap = kind === 'arcane' ? this.arcaneRecoverySlots : this.naturalRecoverySlots;
    const current = this.recoveryCount(kind, level);
    const next = current + delta;
    if (next < 0) return;
    if (delta > 0 && !this.canIncrementRecovery(kind, level)) return;

    const updated: Record<number, number> = { ...(currentMap || {}) };
    if (next === 0) {
      delete updated[level];
    } else {
      updated[level] = next;
    }

    if (kind === 'arcane') {
      this.arcaneRecoverySlotsChange.emit(updated);
    } else {
      this.naturalRecoverySlotsChange.emit(updated);
    }
  }

  canSelectHarnessSlot(level: number): boolean {
    if (this.harnessDivinePowerSlot === level) return true;
    return level >= 1 && level <= this.harnessMaxSlotLevel && this.remainingExpended(level) > 0;
  }

  selectHarnessSlot(level: number | null): void {
    if (level === null || this.harnessDivinePowerSlot === level) {
      this.harnessDivinePowerSlotChange.emit(null);
      return;
    }
    if (!this.canSelectHarnessSlot(level)) return;
    this.harnessDivinePowerSlotChange.emit(level);
  }

  private allocatedForLevel(level: number): number {
    return (
      this.recoveryCount('arcane', level) +
      this.recoveryCount('natural', level) +
      (this.harnessDivinePowerSlot === level ? 1 : 0)
    );
  }

  private sumRecoveryLevels(map: Record<number, number> | null | undefined): number {
    let total = 0;
    for (const lvl of this.recoveryLevels) {
      const count = Math.max(0, Math.trunc(Number(map?.[lvl] ?? 0) || 0));
      total += lvl * count;
    }
    return total;
  }
}
