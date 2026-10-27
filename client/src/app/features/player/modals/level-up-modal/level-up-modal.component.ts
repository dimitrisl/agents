import { ChangeDetectionStrategy, ChangeDetectorRef, Component, EventEmitter, Input, Output } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { HttpClient } from '@angular/common/http';
import { ForgeButtonDirective, ForgeModalComponent, ForgeSelectDirective } from '../../../../shared/ui';
import {
  LevelUpAnalysis,
  LevelUpBuildRecommendation,
  LevelUpRecommendationsResponse,
  CharacterSchema,
} from '../../../../core/models/character.model';
import { DiceService } from '../../../../core/services/dice.service';
import { abilityModifier } from '../../../../core/rules';
import { environment } from '../../../../../environments/environment';

@Component({
  selector: 'app-level-up-modal',
  standalone: true,
  imports: [CommonModule, FormsModule, ForgeButtonDirective, ForgeModalComponent, ForgeSelectDirective],
  templateUrl: './level-up-modal.component.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class LevelUpModalComponent {
  constructor(
    private dice: DiceService,
    private http: HttpClient,
    private cdr: ChangeDetectorRef
  ) {}

  @Input() open = false;
  @Input() character: CharacterSchema | null = null;
  @Input() nextLevel = 1;
  @Input() levelUpAnalysis: LevelUpAnalysis | null = null;
  @Input() userChoices: Record<string, any> = {};

  @Output() openChange = new EventEmitter<boolean>();
  @Output() applyLevelUp = new EventEmitter<void>();
  @Output() userChoicesChange = new EventEmitter<Record<string, any>>();

  buildRecommendations: LevelUpBuildRecommendation[] = [];
  isLoadingRecommendations = false;
  recommendationsError: string | null = null;
  showRecommendations = false;
  planningLevel: number | null = null;

  get characterClasses() {
    if (this.character?.classes && this.character.classes.length > 0) {
      return this.character.classes;
    }
    return [
      {
        class_name: this.character?.char_class || 'Fighter',
        level: this.character?.char_level || 1,
        subclass: this.character?.subclass,
      },
    ];
  }

  get availableClasses() {
    const all = [
      "Artificer",
      "Barbarian",
      "Bard",
      "Cleric",
      "Druid",
      "Fighter",
      "Monk",
      "Paladin",
      "Ranger",
      "Rogue",
      "Sorcerer",
      "Warlock",
      "Wizard",
    ];
    const current = this.characterClasses.map((c) => (c.class_name || '').toLowerCase());
    return all.filter((c) => !current.includes(c.toLowerCase()));
  }

  get levelUpClass() {
    return (
      this.userChoices['level_up_class'] ||
      this.characterClasses[0]?.class_name ||
      this.character?.char_class ||
      'Fighter'
    );
  }

  get targetClassLevel() {
    const cls = this.characterClasses.find(
      (c) => (c.class_name || '').toLowerCase() === this.levelUpClass.toLowerCase()
    );
    return cls ? cls.level + 1 : 1;
  }

  get planningClassLevel(): number {
    return this.planningLevel ?? this.targetClassLevel;
  }

  get upcomingLevelOptions(): number[] {
    const start = this.targetClassLevel;
    const opts: number[] = [];
    for (let l = start; l <= Math.min(20, start + 5); l++) {
      opts.push(l);
    }
    return opts;
  }

  selectPlanningLevel(lvl: number) {
    if (this.planningLevel === lvl) return;
    this.planningLevel = lvl;
    this.fetchRecommendations();
  }

  toggleRecommendations() {
    this.showRecommendations = !this.showRecommendations;
    if (this.showRecommendations && this.buildRecommendations.length === 0 && !this.isLoadingRecommendations) {
      this.fetchRecommendations();
    }
  }

  fetchRecommendations() {
    if (!this.character) return;
    this.isLoadingRecommendations = true;
    this.recommendationsError = null;
    this.showRecommendations = true;

    this.http.post<LevelUpRecommendationsResponse>(`${environment.apiBaseUrl}/forge/level-up-recommendations`, {
      character: this.character,
      target_class: this.levelUpClass,
      target_level: this.planningClassLevel,
    }).subscribe({
      next: (res) => {
        this.buildRecommendations = res?.builds || [];
        this.isLoadingRecommendations = false;
        this.cdr.markForCheck();
      },
      error: () => {
        this.recommendationsError = 'Could not load build recommendations at this time. You can still proceed with manual choices.';
        this.isLoadingRecommendations = false;
        this.cdr.markForCheck();
      }
    });
  }

  onClassChange(val: string) {
    // When changing class, reset other choices like hp_method to avoid mismatched hp increases
    this.planningLevel = null;
    this.userChoices = { 'level_up_class': val };
    this.userChoicesChange.emit(this.userChoices);
    if (this.showRecommendations) {
      this.fetchRecommendations();
    } else {
      this.buildRecommendations = [];
    }
  }

  onChoiceChange(choiceKey: string, val: string) {
    this.userChoices = { ...this.userChoices, [choiceKey]: val };
    this.userChoicesChange.emit(this.userChoices);
  }

  selectHpAverage() {
    if (!this.levelUpAnalysis) return;
    this.onChoiceChange('hp_method', 'average');
    this.onChoiceChange('custom_hp_increase', this.levelUpAnalysis.hp_increase.toString());
  }

  rollHp() {
    if (this.userChoices['hp_method'] === 'roll') return; // locked after first roll
    if (!this.character || !this.character.hit_dice) return;

    // Extract die size (e.g. '5d8' -> 8)
    const match = this.character.hit_dice.match(/d(\d+)/);
    if (!match) return;
    const dieSize = parseInt(match[1], 10);
    const conBonus = abilityModifier(this.character.stats?.CON || 10);

    const roll = this.dice.roll({ numDice: 1, sides: dieSize, modifier: conBonus });
    // D&D HP gain minimum is 1
    const finalHpGain = Math.max(1, roll.total);

    this.onChoiceChange('hp_method', 'roll');
    this.onChoiceChange('custom_hp_increase', finalHpGain.toString());
  }
}
