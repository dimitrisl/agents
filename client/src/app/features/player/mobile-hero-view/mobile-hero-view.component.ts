import {
  ChangeDetectionStrategy,
  Component,
  EventEmitter,
  Input,
  OnChanges,
  Output,
  SimpleChanges,
} from '@angular/core';
import { CommonModule } from '@angular/common';
import type { CharacterSchema } from '../../../core/models/character.model';
import { getSubclassUnlockLevel } from '../../../core/rules/recommendations';
import {
  abilityCheckModifier,
  describeDmModifiers,
  effectiveSpeed,
  exhaustionD20Penalty,
  formatClassSummary,
  formatModifier,
  formatSubclassSummary,
  hasConditionDisadvantage,
  hasExhaustionDisadvantage,
  is2024Edition,
  isAutoFailSave,
  isDeceasedByExhaustion,
  isSaveProficient,
  savingThrowModifier,
  speedLockReason,
} from '../../../core/rules';
import {
  ForgeBadgeComponent,
  ForgeButtonDirective,
  ForgeCardComponent,
  ForgeIconComponent,
  ForgeInputDirective,
} from '../../../shared/ui';

const ABILITY_FULL_NAMES: Record<string, string> = {
  STR: 'Strength',
  DEX: 'Dexterity',
  CON: 'Constitution',
  INT: 'Intelligence',
  WIS: 'Wisdom',
  CHA: 'Charisma',
};

@Component({
  selector: 'app-mobile-hero-view',
  standalone: true,
  imports: [
    CommonModule,
    ForgeBadgeComponent,
    ForgeButtonDirective,
    ForgeCardComponent,
    ForgeIconComponent,
    ForgeInputDirective,
  ],
  templateUrl: './mobile-hero-view.component.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
  host: {
    class: 'block',
  },
})
export class MobileHeroViewComponent implements OnChanges {
  @Input({ required: true }) char!: CharacterSchema;
  @Input() editMode = false;
  @Input() edition = '';
  @Input() portraitUrl = '';
  @Input() availableHitDice = 0;
  @Input() classHitDieSize = 8;
  @Input() passivePerception = 10;
  @Input() passiveInvestigation = 10;
  @Input() passiveInsight = 10;
  @Input() abilityEntries: { key: string; value: number }[] = [];
  @Input() activeSubTab: 'abilities' | 'senses' = 'abilities';

  @Output() activeSubTabChange = new EventEmitter<'abilities' | 'senses'>();
  @Output() portrait = new EventEmitter<void>();
  @Output() abilityCheck = new EventEmitter<string>();
  @Output() savingThrow = new EventEmitter<string>();
  @Output() manageConditions = new EventEmitter<void>();
  @Output() removeCondition = new EventEmitter<string>();
  @Output() endConcentration = new EventEmitter<void>();
  @Output() browseHomebrew = new EventEmitter<void>();
  @Output() openAcSheet = new EventEmitter<void>();
  @Output() charPatch = new EventEmitter<Partial<CharacterSchema>>();

  imageLoadError = false;
  private lastHeroKey?: string;

  ngOnChanges(changes: SimpleChanges): void {
    const heroKey = this.char ? (this.char.char_id || this.char.char_name) : '';
    if (changes['portraitUrl'] || (changes['char'] && heroKey !== this.lastHeroKey)) {
      this.imageLoadError = false;
    }
    this.lastHeroKey = heroKey;
  }

  get isMulticlass(): boolean {
    return (this.char?.classes?.length ?? 0) > 1;
  }

  onTextCommit(
    field: 'char_name' | 'race' | 'background' | 'char_class' | 'subclass',
    rawValue: string
  ): void {
    if (!this.char) return;
    if (field === 'char_class' && this.isMulticlass) return;
    if (field === 'subclass' && !this.canEditSubclass) return;
    this.charPatch.emit({ [field]: rawValue });
  }

  onNumberCommit(
    field: 'char_level' | 'speed',
    rawValue: string,
    min: number,
    max: number,
    inputEl?: HTMLInputElement
  ): void {
    if (!this.char) return;
    if (field === 'char_level' && (!!this.char.active_campaign || this.isMulticlass)) return;
    const parsed = Number(rawValue);
    if (!Number.isFinite(parsed)) return;
    const clamped = Math.max(min, Math.min(max, Math.round(parsed)));
    if (inputEl && String(clamped) !== rawValue) {
      inputEl.value = String(clamped);
    }
    this.charPatch.emit({ [field]: clamped });
  }

  onStatCommit(statKey: string, rawValue: string, inputEl?: HTMLInputElement): void {
    if (!this.char?.stats) return;
    const parsed = Number(rawValue);
    if (!Number.isFinite(parsed)) return;
    const clamped = Math.max(1, Math.min(30, Math.round(parsed)));
    if (inputEl && String(clamped) !== rawValue) {
      inputEl.value = String(clamped);
    }
    this.charPatch.emit({
      stats: {
        ...this.char.stats,
        [statKey]: clamped,
      },
    });
  }

  selectSubTab(tab: 'abilities' | 'senses'): void {
    this.activeSubTabChange.emit(tab);
  }

  abilityFullName(code: string): string {
    return ABILITY_FULL_NAMES[code] || code;
  }

  checkModifier(ability: string): string {
    return formatModifier(abilityCheckModifier(this.char, ability));
  }

  saveModifier(ability: string): string {
    return formatModifier(savingThrowModifier(this.char, ability));
  }

  isProficientSave(ability: string): boolean {
    return isSaveProficient(this.char, ability);
  }

  formatSigned(value: number): string {
    return formatModifier(value);
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

  get displaySpeed(): number {
    return effectiveSpeed(this.char);
  }

  get speedLockText(): string | null {
    return speedLockReason(this.char);
  }

  get deceasedByExhaustion(): boolean {
    return isDeceasedByExhaustion(this.char);
  }

  get classSummary(): string {
    return formatClassSummary(this.char, 'long');
  }

  get subclassSummary(): string {
    return formatSubclassSummary(this.char);
  }

  get subclassUnlockLevel(): number {
    const is2024 = (this.char?.dnd_edition || this.edition || '').includes('2024');
    return getSubclassUnlockLevel(this.char?.char_class || '', is2024);
  }

  get canEditSubclass(): boolean {
    return Number(this.char?.char_level || 1) >= this.subclassUnlockLevel;
  }

  get dmModifiersParts(): string[] {
    return describeDmModifiers(this.char?.dm_modifiers);
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
    return `Exhaustion ${lvl}/6 (2014 PHB rules)`;
  }

  get hasActiveStatus(): boolean {
    return !!(
      this.char.concentrating_on ||
      this.deceasedByExhaustion ||
      (this.char.exhaustion_level ?? 0) > 0 ||
      this.char.magic_items_suppressed ||
      this.dmModifiersParts.length > 0 ||
      (this.char.dm_modifiers?.note || '').trim() ||
      (this.char.conditions?.length ?? 0) > 0
    );
  }
}
