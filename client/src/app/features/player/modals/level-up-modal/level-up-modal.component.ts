import { ChangeDetectionStrategy, ChangeDetectorRef, Component, DestroyRef, EventEmitter, Input, Output, inject } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { HttpClient } from '@angular/common/http';
import { EMPTY, Subject, catchError, switchMap } from 'rxjs';
import { ForgeButtonDirective, ForgeModalComponent, ForgeSelectDirective, ForgeSpinnerComponent } from '../../../../shared/ui';
import {
  LevelUpAnalysis,
  LevelUpBuildRecommendation,
  LevelUpChoice,
  LevelUpFeatMetadata,
  LevelUpRecommendationsResponse,
  CharacterSchema,
} from '../../../../core/models/character.model';
import { DiceService } from '../../../../core/services/dice.service';
import { abilityModifier } from '../../../../core/rules';
import { hitDieSidesFor } from '../../../../core/data/class-combat.data';
import { environment } from '../../../../../environments/environment';

@Component({
  selector: 'app-level-up-modal',
  standalone: true,
  imports: [CommonModule, FormsModule, ForgeButtonDirective, ForgeModalComponent, ForgeSelectDirective, ForgeSpinnerComponent],
  templateUrl: './level-up-modal.component.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class LevelUpModalComponent {
  private readonly destroyRef = inject(DestroyRef);
  private readonly recommendationsTrigger$ = new Subject<void>();

  constructor(
    private dice: DiceService,
    private http: HttpClient,
    private cdr: ChangeDetectorRef
  ) {
    this.recommendationsTrigger$
      .pipe(
        switchMap(() => {
          if (!this.character) return EMPTY;
          return this.http
            .post<LevelUpRecommendationsResponse>(`${environment.apiBaseUrl}/forge/level-up-recommendations`, {
              character: this.character,
              target_class: this.levelUpClass,
              target_level: this.planningClassLevel,
            })
            .pipe(
              catchError(() => {
                this.recommendationsError =
                  'Could not load build recommendations at this time. You can still proceed with manual choices.';
                this.isLoadingRecommendations = false;
                this.cdr.markForCheck();
                return EMPTY;
              })
            );
        }),
        takeUntilDestroyed(this.destroyRef)
      )
      .subscribe((res) => {
        this.buildRecommendations = res?.builds || [];
        this.isLoadingRecommendations = false;
        this.cdr.markForCheck();
      });
  }

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

  readonly abilityStatOptions = [
    { code: 'STR', label: 'Strength (STR)' },
    { code: 'DEX', label: 'Dexterity (DEX)' },
    { code: 'CON', label: 'Constitution (CON)' },
    { code: 'INT', label: 'Intelligence (INT)' },
    { code: 'WIS', label: 'Wisdom (WIS)' },
    { code: 'CHA', label: 'Charisma (CHA)' },
  ];

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

  get levelUpHitDie(): number {
    return hitDieSidesFor(this.levelUpClass);
  }

  get conModifier(): number {
    return abilityModifier(this.character?.stats?.CON || 10);
  }

  get perLevelHpBonus(): number {
    if (typeof this.levelUpAnalysis?.hp_bonus_per_level === 'number') {
      return Math.max(0, this.levelUpAnalysis.hp_bonus_per_level);
    }
    if (!this.levelUpAnalysis) return 0;
    const avgBaseGain = Math.floor(this.levelUpHitDie / 2) + 1 + this.conModifier;
    if (avgBaseGain < 1) return 0;
    return Math.max(0, this.levelUpAnalysis.hp_increase - avgBaseGain);
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
    this.recommendationsTrigger$.next();
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
    const nextChoices: Record<string, any> = { ...this.userChoices, [choiceKey]: val };
    const topMatch = /^(feat)_(\d+)$/.exec(choiceKey);
    if (topMatch) {
      const [, baseType, idx] = topMatch;
      delete nextChoices[`${baseType}_stat1_${idx}`];
      delete nextChoices[`${baseType}_stat2_${idx}`];
    }
    const stat1Match = /^([a-zA-Z0-9]+)_stat1_(\d+)$/.exec(choiceKey);
    if (stat1Match) {
      const [, baseType, idx] = stat1Match;
      if (nextChoices[`${baseType}_stat2_${idx}`] === val) {
        delete nextChoices[`${baseType}_stat2_${idx}`];
      }
    }
    this.userChoices = nextChoices;
    this.userChoicesChange.emit(this.userChoices);
  }

  selectedFeatMeta(choice: LevelUpChoice, choiceVal: string | undefined): LevelUpFeatMetadata | null {
    if (!choiceVal || !choice.feat_metadata) return null;
    return choice.feat_metadata[choiceVal] ?? null;
  }

  showsSingleStatPicker(choice: LevelUpChoice, choiceVal: string | undefined): boolean {
    if (!choiceVal) return false;
    if (choiceVal === '+2 to one Stat') return true;
    if (choice.type !== 'feat' || choiceVal === '+1 to two Stats') return false;
    if (choice.feat_metadata !== undefined) {
      return Boolean(choice.feat_metadata[choiceVal]?.has_stat_choice);
    }
    return false;
  }

  allowedSingleStatsForChoice(choice: LevelUpChoice, choiceVal: string | undefined): { code: string; label: string }[] {
    if (choiceVal === '+2 to one Stat') return this.abilityStatOptions;
    const opts = this.selectedFeatMeta(choice, choiceVal)?.stat_choice_options ?? [];
    if (!opts.length) return this.abilityStatOptions;
    const allowed = new Set(opts.map((o) => o.toUpperCase()));
    return this.abilityStatOptions.filter((s) => allowed.has(s.code));
  }

  secondStatsForChoice(firstStat: string | undefined): { code: string; label: string }[] {
    if (!firstStat) return this.abilityStatOptions;
    return this.abilityStatOptions.filter((s) => s.code !== firstStat);
  }

  private get pendingHpChoiceDeltas(): { conModDelta: number; addedFeatHpPerLvl: number } {
    const choices = this.levelUpAnalysis?.choices_required ?? [];
    const baseCon = Number(this.character?.stats?.CON ?? 10);
    const is2024 = String(this.character?.dnd_edition ?? '').includes('2024');
    const statCap = is2024 && this.nextLevel >= 19 ? 30 : 20;

    let conBump = 0;
    let addedFeatHpPerLvl = 0;

    choices.forEach((choice, i) => {
      if (choice.type !== 'feat') return;
      const val = this.userChoices[`${choice.type}_${i}`];
      if (!val) return;
      const s1 = String(this.userChoices[`${choice.type}_stat1_${i}`] ?? '').toUpperCase();
      const s2 = String(this.userChoices[`${choice.type}_stat2_${i}`] ?? '').toUpperCase();

      if (val === '+2 to one Stat') {
        if (s1 === 'CON') conBump += 2;
      } else if (val === '+1 to two Stats') {
        if (s1 === 'CON') conBump += 1;
        if (s2 === 'CON' && s2 !== s1) conBump += 1;
      } else {
        const meta = this.selectedFeatMeta(choice, val);
        if (meta) {
          conBump += Number(meta.stat_bonus?.['CON'] ?? 0);
          if (meta.has_stat_choice && s1 === 'CON') {
            const opts = meta.stat_choice_options ?? [];
            if (!opts.length || opts.map((o) => o.toUpperCase()).includes('CON')) {
              conBump += 1;
            }
          }
          addedFeatHpPerLvl += Number(meta.hp_bonus_per_level ?? 0);
        }
      }
    });

    const newCon = Math.min(statCap, baseCon + conBump);
    const conModDelta = abilityModifier(newCon) - this.conModifier;
    return { conModDelta, addedFeatHpPerLvl };
  }

  get previewPendingHpAdjustment(): number {
    if (!this.levelUpAnalysis) return 0;
    const { conModDelta, addedFeatHpPerLvl } = this.pendingHpChoiceDeltas;
    return (conModDelta + addedFeatHpPerLvl) * Math.max(1, this.nextLevel);
  }

  get previewNewTotalHp(): number {
    if (!this.levelUpAnalysis) return 0;
    const priorHpBase = this.levelUpAnalysis.new_total_hp - this.levelUpAnalysis.hp_increase;
    const customRaw = this.userChoices['custom_hp_increase'];
    const baseLevelGain =
      this.userChoices['hp_method'] === 'roll' && customRaw !== undefined && Number.isFinite(Number(customRaw))
        ? Number(customRaw)
        : this.levelUpAnalysis.hp_increase;
    return Math.max(1, priorHpBase + baseLevelGain + this.previewPendingHpAdjustment);
  }

  get hasIncompleteStatChoices(): boolean {
    const choices = this.levelUpAnalysis?.choices_required ?? [];
    return choices.some((choice, i) => {
      if (choice.type !== 'feat') return false;
      const val = this.userChoices[`${choice.type}_${i}`];
      if (!val) return false;
      const s1 = String(this.userChoices[`${choice.type}_stat1_${i}`] ?? '').trim().toUpperCase();
      const s2 = String(this.userChoices[`${choice.type}_stat2_${i}`] ?? '').trim().toUpperCase();
      if (val === '+2 to one Stat') {
        return !s1;
      }
      if (val === '+1 to two Stats') {
        return !s1 || !s2 || s1 === s2;
      }
      if (this.showsSingleStatPicker(choice, val)) {
        if (!s1) return true;
        const allowed = this.allowedSingleStatsForChoice(choice, val).map((s) => s.code);
        return !allowed.includes(s1);
      }
      return false;
    });
  }

  selectHpAverage() {
    if (!this.levelUpAnalysis) return;
    this.onChoiceChange('hp_method', 'average');
    this.onChoiceChange('custom_hp_increase', this.levelUpAnalysis.hp_increase.toString());
  }

  rollHp() {
    if (this.userChoices['hp_method'] === 'roll') return; // locked after first roll
    if (!this.character) return;

    const dieSize = this.levelUpHitDie;
    const bonusPerLvl = this.perLevelHpBonus;
    const bonus = this.conModifier + bonusPerLvl;

    const roll = this.dice.roll({ numDice: 1, sides: dieSize, modifier: bonus });
    // D&D HP gain minimum is 1
    const finalHpGain = Math.max(1, roll.total);

    this.onChoiceChange('hp_method', 'roll');
    this.onChoiceChange('hp_bonus_included', bonusPerLvl.toString());
    this.onChoiceChange('custom_hp_increase', finalHpGain.toString());
  }
}
