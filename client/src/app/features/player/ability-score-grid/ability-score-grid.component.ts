import { Component, EventEmitter, Input, Output } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import type { CharacterSchema } from '../../../core/models/character.model';
import { ForgeInputDirective } from '../../../shared/ui';

@Component({
  selector: 'app-ability-score-grid',
  standalone: true,
  imports: [CommonModule, FormsModule, ForgeInputDirective],
  templateUrl: './ability-score-grid.component.html',
})
export class AbilityScoreGridComponent {
  @Input({ required: true }) char!: CharacterSchema;
  @Input() entries: { key: string; value: number }[] = [];
  @Input() editMode = false;
  @Input() getModifierString!: (val: number) => string;

  @Output() abilityCheck = new EventEmitter<string>();
  @Output() savingThrow = new EventEmitter<string>();

  trackByStatKey(index: number, entry: { key: string; value: number }): string {
    return entry.key;
  }
}
