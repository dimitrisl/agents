import { Component, EventEmitter, Input, Output } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import type { CharacterSchema } from '../../../core/models/character.model';
import {
  ForgeBadgeComponent,
  ForgeCardComponent,
  ForgeInputDirective,
} from '../../../shared/ui';
import { HitPointsControlComponent } from '../hit-points-control/hit-points-control.component';
import { CombatStatGridComponent } from '../combat-stat-grid/combat-stat-grid.component';
import { AbilityScoreGridComponent } from '../ability-score-grid/ability-score-grid.component';

@Component({
  selector: 'app-character-overview-card',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    ForgeBadgeComponent,
    ForgeCardComponent,
    ForgeInputDirective,
    HitPointsControlComponent,
    CombatStatGridComponent,
    AbilityScoreGridComponent,
  ],
  templateUrl: './character-overview-card.component.html',
})
export class CharacterOverviewCardComponent {
  @Input({ required: true }) char!: CharacterSchema;
  @Input() editMode = false;
  @Input() edition = '';
  @Input() portraitUrl = '';
  @Input() availableHitDice = 0;
  @Input() classHitDieSize = 8;
  @Input() passivePerception = 10;
  @Input() abilityEntries: { key: string; value: number }[] = [];
  @Input() getModifierString!: (val: number) => string;

  @Output() portrait = new EventEmitter<void>();
  @Output() hpDown = new EventEmitter<void>();
  @Output() hpUp = new EventEmitter<void>();
  @Output() abilityCheck = new EventEmitter<string>();
  @Output() savingThrow = new EventEmitter<string>();
}
