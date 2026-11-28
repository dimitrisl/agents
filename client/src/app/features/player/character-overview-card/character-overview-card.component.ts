import { Component, EventEmitter, Input, OnChanges, Output, SimpleChanges } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import type { CharacterSchema } from '../../../core/models/character.model';
import { getSubclassUnlockLevel } from '../../../core/rules/recommendations';
import {
  DamageMitigationMode,
  describeDmModifiers,
  effectiveSpeed,
  exhaustionD20Penalty,
  formatClassSummary,
  formatSubclassSummary,
  hasConditionAdvantage,
  hasInitiativeAdvantage,
  is2024Edition,
  isDeceasedByExhaustion,
  speedLockReason,
} from '../../../core/rules';
import {
  ForgeBadgeComponent,
  ForgeIconComponent,
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
    ForgeIconComponent,
    ForgeCardComponent,
    ForgeInputDirective,
    HitPointsControlComponent,
    CombatStatGridComponent,
    AbilityScoreGridComponent,
  ],
  templateUrl: './character-overview-card.component.html',
})
export class CharacterOverviewCardComponent implements OnChanges {
  @Input({ required: true }) char!: CharacterSchema;
  @Input() editMode = false;
  @Input() edition = '';
  @Input() portraitUrl = '';
  @Input() availableHitDice = 0;
  @Input() classHitDieSize = 8;
  @Input() passivePerception = 10;
  @Input() abilityEntries: { key: string; value: number }[] = [];
  @Input() getModifierString!: (val: number) => string;

  imageLoadError = false;

  get initiativeAdvantage(): boolean {
    return hasInitiativeAdvantage(this.char) || hasConditionAdvantage(this.char, 'initiative');
  }

  get derivedSpeed(): number {
    return effectiveSpeed(this.char);
  }

  get derivedSpeedLockReason(): string | null {
    return speedLockReason(this.char);
  }

  get deceasedByExhaustion(): boolean {
    return isDeceasedByExhaustion(this.char);
  }

  get dmModifiersParts(): string[] {
    return describeDmModifiers(this.char?.dm_modifiers);
  }

  get dmModifiersTooltip(): string {
    const parts = this.dmModifiersParts;
    const note = (this.char?.dm_modifiers?.note || '').trim();
    const body = parts.length ? parts.join(', ') : '';
    if (body && note) return `${body} — DM Note: ${note}`;
    if (note) return `DM Note: ${note}`;
    return body || 'DM Custom Modifiers active';
  }

  get exhaustionTooltip(): string {
    const lvl = this.char?.exhaustion_level ?? 0;
    if (this.char?.exhaustion_bypass) {
      return `Exhaustion ${lvl}/6 (Consequences waived by DM Bypass)`;
    }
    if (is2024Edition(this.char)) {
      const d20 = exhaustionD20Penalty(this.char);
      return `Exhaustion ${lvl}/6: -${d20} to D20 Tests, -${lvl * 5} ft Speed`;
    }
    const effects: string[] = [];
    if (lvl >= 1) effects.push('Disadvantage on Ability Checks (-5 Passive Perception)');
    if (lvl >= 2) effects.push('Speed halved');
    if (lvl >= 3) effects.push('Disadvantage on Attacks & Saving Throws');
    if (lvl >= 4) effects.push('HP Maximum halved');
    if (lvl >= 5) effects.push('Speed reduced to 0');
    if (lvl >= 6) effects.push('Death');
    return `Exhaustion ${lvl}/6: ${effects.join(' · ')}`;
  }

  onBaseSpeedChange(val: number): void {
    if (!this.char) return;
    const numeric = Math.max(0, Math.round(Number(val) || 0));
    this.char.base_speed = numeric;
    this.char.speed = effectiveSpeed({ ...this.char, base_speed: numeric, speed: undefined });
  }

  @Output() portrait = new EventEmitter<void>();
  @Output() hpChange = new EventEmitter<number>();
  @Output() tempChange = new EventEmitter<number>();
  @Output() deathSaveChange = new EventEmitter<{ type: 'successes' | 'failures'; value: number }>();
  @Output() rollDeathSave = new EventEmitter<void>();
  @Output() applyDamage = new EventEmitter<number>();
  @Output() damageImmuneApplied = new EventEmitter<{
    raw: number;
    label?: string | null;
    mode?: DamageMitigationMode;
  }>();
  @Output() applyHeal = new EventEmitter<number>();
  @Output() setTempHp = new EventEmitter<number>();
  @Output() manageConditions = new EventEmitter<void>();
  @Output() removeCondition = new EventEmitter<string>();
  @Output() endConcentration = new EventEmitter<void>();
  @Output() abilityCheck = new EventEmitter<string>();
  @Output() savingThrow = new EventEmitter<string>();
  @Output() rollInitiative = new EventEmitter<void>();

  ngOnChanges(changes: SimpleChanges): void {
    if (changes['portraitUrl']) {
      this.imageLoadError = false;
    }
  }

  get subclassUnlockLevel(): number {
    const is2024 = (this.char?.dnd_edition || this.edition || '').includes('2024');
    return getSubclassUnlockLevel(this.char?.char_class || '', is2024);
  }

  get classSummary(): string {
    return formatClassSummary(this.char, 'long');
  }

  get subclassSummary(): string {
    return formatSubclassSummary(this.char);
  }

  get canEditSubclass(): boolean {
    return Number(this.char?.char_level || 1) >= this.subclassUnlockLevel;
  }
}
