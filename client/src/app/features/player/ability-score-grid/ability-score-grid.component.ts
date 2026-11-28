import { Component, EventEmitter, Input, Output } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import type { CharacterSchema } from '../../../core/models/character.model';
import {
  abilityCheckModifier,
  formatModifier,
  hasConditionDisadvantage,
  hasExhaustionDisadvantage,
  isAutoFailSave,
  isSaveProficient,
  savingThrowModifier,
} from '../../../core/rules';
import { ForgeBadgeComponent, ForgeInputDirective } from '../../../shared/ui';

@Component({
  selector: 'app-ability-score-grid',
  standalone: true,
  imports: [CommonModule, FormsModule, ForgeBadgeComponent, ForgeInputDirective],
  templateUrl: './ability-score-grid.component.html',
})
export class AbilityScoreGridComponent {
  @Input({ required: true }) char!: CharacterSchema;
  @Input() entries: { key: string; value: number }[] = [];
  @Input() editMode = false;
  @Input() getModifierString!: (val: number) => string;

  @Output() abilityCheck = new EventEmitter<string>();
  @Output() savingThrow = new EventEmitter<string>();

  isProficient(ability: string): boolean {
    return isSaveProficient(this.char, ability);
  }

  /** Same number the Check button rolls: ability mod minus 2024 exhaustion + DM Check mod. */
  checkModifier(ability: string): string {
    return formatModifier(abilityCheckModifier(this.char, ability));
  }

  /** Same number the Save button rolls: modifier plus proficiency when trained, minus exhaustion + DM Save mod. */
  saveModifier(ability: string): string {
    return formatModifier(savingThrowModifier(this.char, ability));
  }

  get hasCheckDisadvantage(): boolean {
    return hasExhaustionDisadvantage(this.char, 'check') || hasConditionDisadvantage(this.char, 'check');
  }

  get hasSaveDisadvantage(): boolean {
    return hasExhaustionDisadvantage(this.char, 'save');
  }

  hasSaveDisadvantageFor(ability: string): boolean {
    return hasExhaustionDisadvantage(this.char, 'save') || hasConditionDisadvantage(this.char, 'save', ability);
  }

  isSaveAutoFail(ability: string): boolean {
    return isAutoFailSave(this.char, ability);
  }
}
