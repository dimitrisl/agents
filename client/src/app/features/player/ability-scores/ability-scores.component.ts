import { ChangeDetectionStrategy, Component, EventEmitter, Input, Output } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { CharacterSchema } from '../../../core/models/character.model';
import {
  ForgeButtonDirective,
  ForgeInputDirective,
  ForgeStatBoxComponent,
} from '../../../shared/ui';

@Component({
  selector: 'app-ability-scores',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    ForgeButtonDirective,
    ForgeInputDirective,
    ForgeStatBoxComponent,
  ],
  templateUrl: './ability-scores.component.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class AbilityScoresComponent {
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
