import { ChangeDetectionStrategy, Component, EventEmitter, Input, Output } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import {
  ForgeButtonDirective,
  ForgeInputDirective,
  ForgeSelectDirective,
  ForgeTextareaDirective,
} from '../../../shared/ui';

@Component({
  selector: 'app-manual-form',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    ForgeButtonDirective,
    ForgeInputDirective,
    ForgeSelectDirective,
    ForgeTextareaDirective,
  ],
  templateUrl: './manual-form.component.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ManualFormComponent {
  @Input() is2024 = false;
  @Input() raceOptions: string[] = [];
  @Input() classOptions: string[] = [];
  @Input() bgOptions: string[] = [];
  @Input() alignments: string[] = [];
  @Input() statKeys: string[] = [];
  @Input() standardArrayValues: number[] = [];
  @Input() manualSubclassOptions: string[] = [];
  @Input() rolledScores: number[] = [];
  @Input() loading = false;
  @Input() getFinalStat!: (key: string) => number;
  @Input() getModifierString!: (val: number) => string;

  @Input() manualName = 'New Hero';
  @Input() manualLevel = 1;
  @Input() manualGender = 'Male';
  @Input() manualRace = 'Human';
  @Input() manualClass = 'Paladin';
  @Input() manualBackground = 'Soldier';
  @Input() manualAlignment = 'Lawful Good';
  @Input() manualSubclass = 'None';
  @Input() manualConcept = '';
  @Input() manualStatMethod = 'standard';
  @Input() manualStats: Record<string, number> = {};
  @Input() adjPlus2 = 'None';
  @Input() adjPlus1 = 'None';
  @Input() adjPlus1Alt = 'None';

  @Output() manualNameChange = new EventEmitter<string>();
  @Output() manualLevelChange = new EventEmitter<number>();
  @Output() manualGenderChange = new EventEmitter<string>();
  @Output() manualRaceChange = new EventEmitter<string>();
  @Output() manualClassChange = new EventEmitter<string>();
  @Output() manualBackgroundChange = new EventEmitter<string>();
  @Output() manualAlignmentChange = new EventEmitter<string>();
  @Output() manualSubclassChange = new EventEmitter<string>();
  @Output() manualConceptChange = new EventEmitter<string>();
  @Output() manualStatMethodChange = new EventEmitter<string>();
  @Output() manualStatsChange = new EventEmitter<Record<string, number>>();
  @Output() adjPlus2Change = new EventEmitter<string>();
  @Output() adjPlus1Change = new EventEmitter<string>();
  @Output() adjPlus1AltChange = new EventEmitter<string>();

  @Output() updateManualSubclasses = new EventEmitter<void>();
  @Output() rollStats = new EventEmitter<void>();
  @Output() create = new EventEmitter<void>();
}
