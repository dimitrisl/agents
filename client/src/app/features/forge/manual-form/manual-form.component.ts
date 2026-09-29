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
  @Input() subclassLocked = true;
  @Input() subclassLockHint = 'Subclasses unlock at level 3';
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

  isValueSelected(val: number, currentStat: string): boolean {
    if (this.manualStatMethod !== 'standard') return false;
    // Check if any OTHER stat has this value selected
    for (const key of this.statKeys) {
      if (key !== currentStat && Number(this.manualStats[key]) === val) {
        return true;
      }
    }
    return false;
  }

  optimizeStats() {
    if (this.manualStatMethod !== 'standard') return;
    const array = [...this.standardArrayValues].sort((a, b) => b - a);
    if (array.length < 6) return;

    // Default assignment mapping highest to lowest based on primary attributes
    let primary: string[] = [];
    switch (this.manualClass.toLowerCase()) {
      case 'barbarian': primary = ['STR', 'CON', 'DEX', 'WIS', 'CHA', 'INT']; break;
      case 'bard': primary = ['CHA', 'DEX', 'CON', 'WIS', 'INT', 'STR']; break;
      case 'cleric': primary = ['WIS', 'CON', 'STR', 'DEX', 'INT', 'CHA']; break;
      case 'druid': primary = ['WIS', 'CON', 'DEX', 'INT', 'CHA', 'STR']; break;
      case 'fighter': primary = ['STR', 'CON', 'DEX', 'WIS', 'INT', 'CHA']; break;
      case 'monk': primary = ['DEX', 'WIS', 'CON', 'STR', 'INT', 'CHA']; break;
      case 'paladin': primary = ['STR', 'CHA', 'CON', 'WIS', 'DEX', 'INT']; break;
      case 'ranger': primary = ['DEX', 'WIS', 'CON', 'STR', 'INT', 'CHA']; break;
      case 'rogue': primary = ['DEX', 'INT', 'CON', 'WIS', 'CHA', 'STR']; break;
      case 'sorcerer': primary = ['CHA', 'CON', 'DEX', 'WIS', 'INT', 'STR']; break;
      case 'warlock': primary = ['CHA', 'CON', 'DEX', 'WIS', 'INT', 'STR']; break;
      case 'wizard': primary = ['INT', 'CON', 'DEX', 'WIS', 'CHA', 'STR']; break;
      default: primary = ['STR', 'DEX', 'CON', 'INT', 'WIS', 'CHA']; break;
    }

    const newStats: Record<string, number> = {};
    primary.forEach((stat, index) => {
      newStats[stat] = array[index];
    });

    // Merge in case some are missing
    this.statKeys.forEach(key => {
      if (!newStats[key]) newStats[key] = array[5];
    });

    this.manualStatsChange.emit(newStats);
  }

  getPointBuyCost(score: number): number {
    const costs: Record<number, number> = { 8: 0, 9: 1, 10: 2, 11: 3, 12: 4, 13: 5, 14: 7, 15: 9 };
    return costs[score] || 0;
  }

  getRemainingPoints(): number {
    let spent = 0;
    for (const key of this.statKeys) {
      spent += this.getPointBuyCost(Number(this.manualStats[key]) || 8);
    }
    return 27 - spent;
  }

  onPointBuyChange(stat: string, score: number) {
    if (this.manualStatMethod !== 'pointbuy') return;
    const currentScore = Number(this.manualStats[stat]) || 8;
    const currentCost = this.getPointBuyCost(currentScore);
    const newCost = this.getPointBuyCost(score);

    // Allow decreasing, or increasing if we have enough points
    if (newCost <= currentCost || (this.getRemainingPoints() >= (newCost - currentCost))) {
      this.manualStats = { ...this.manualStats, [stat]: score };
      this.manualStatsChange.emit(this.manualStats);
    } else {
      // Re-emit old value to reset select element in UI
      this.manualStatsChange.emit({ ...this.manualStats });
    }
  }
}
