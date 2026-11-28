import { ChangeDetectionStrategy, Component, EventEmitter, Input, OnChanges, Output, SimpleChanges } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { CharacterSchema } from '../../../../core/models/character.model';
import { getSubclassUnlockLevel } from '../../../../core/rules/recommendations';
import { effectiveSpeed, speedLockReason } from '../../../../core/rules';
import { ForgeButtonDirective, ForgeInputDirective, ForgeModalComponent, ForgeTextareaDirective } from '../../../../shared/ui';

@Component({
  selector: 'app-edit-sheet-modal',
  standalone: true,
  imports: [CommonModule, FormsModule, ForgeButtonDirective, ForgeInputDirective, ForgeModalComponent, ForgeTextareaDirective],
  templateUrl: './edit-sheet-modal.component.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class EditSheetModalComponent implements OnChanges {
  @Input() open = false;
  @Input() editChar: CharacterSchema | null = null;

  @Output() openChange = new EventEmitter<boolean>();
  @Output() saveEditModal = new EventEmitter<void>();

  resistancesText = '';
  immunitiesText = '';
  vulnerabilitiesText = '';

  ngOnChanges(changes: SimpleChanges): void {
    if (changes['editChar'] || changes['open']) {
      this.resistancesText = (this.editChar?.damage_resistances || []).join(', ');
      this.immunitiesText = (this.editChar?.damage_immunities || []).join(', ');
      this.vulnerabilitiesText = (this.editChar?.damage_vulnerabilities || []).join(', ');
    }
  }

  onDefenseChange(
    field: 'damage_resistances' | 'damage_immunities' | 'damage_vulnerabilities',
    raw: string
  ): void {
    const parsed = String(raw || '')
      .split(',')
      .map((s) => s.trim())
      .filter(Boolean);
    if (field === 'damage_resistances') this.resistancesText = raw;
    else if (field === 'damage_immunities') this.immunitiesText = raw;
    else this.vulnerabilitiesText = raw;
    if (this.editChar) {
      this.editChar[field] = parsed;
    }
  }

  get activeSpeedLock(): string | null {
    return speedLockReason(this.editChar);
  }

  get editableSpeed(): number {
    if (!this.editChar) return 30;
    const lockedZero = !!speedLockReason(this.editChar) && (this.editChar.speed ?? 0) === 0;
    return this.editChar.base_speed ?? (lockedZero ? 30 : this.editChar.speed) ?? 30;
  }

  set editableSpeed(val: number) {
    if (!this.editChar) return;
    const numeric = Math.max(0, Math.round(Number(val) || 0));
    this.editChar.base_speed = numeric;
    this.editChar.speed = effectiveSpeed({ ...this.editChar, base_speed: numeric, speed: undefined });
  }

  get subclassUnlockLevel(): number {
    const is2024 = (this.editChar?.dnd_edition || '').includes('2024');
    return getSubclassUnlockLevel(this.editChar?.char_class || '', is2024);
  }

  get canEditSubclass(): boolean {
    return Number(this.editChar?.char_level || 1) >= this.subclassUnlockLevel;
  }
}
