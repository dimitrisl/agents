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
import { FormsModule } from '@angular/forms';
import type { CharacterSchema } from '../../../core/models/character.model';
import { getSubclassUnlockLevel } from '../../../core/rules/recommendations';
import {
  abilityCheckModifier,
  describeDmModifiers,
  exhaustionD20Penalty,
  formatClassSummary,
  formatModifier,
  formatSubclassSummary,
  hasExhaustionDisadvantage,
  is2024Edition,
  isDeceasedByExhaustion,
  isSaveProficient,
  savingThrowModifier,
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
    FormsModule,
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
  @Output() save = new EventEmitter<void>();

  imageLoadError = false;
  private lastHeroKey?: string;

  ngOnChanges(changes: SimpleChanges): void {
    const heroKey = this.char ? (this.char.char_id || this.char.char_name) : '';
    if (changes['portraitUrl'] || (changes['char'] && heroKey !== this.lastHeroKey)) {
      this.imageLoadError = false;
    }
    this.lastHeroKey = heroKey;
  }

  onInlineFieldChange(): void {
    if (!this.char) return;
    if (this.char.stats) {
      for (const key of Object.keys(this.char.stats)) {
        const val = Number(this.char.stats[key]);
        if (Number.isFinite(val)) {
          this.char.stats[key] = Math.max(1, Math.min(30, Math.round(val)));
        }
      }
    }
    if (!this.char.active_campaign && this.char.char_level !== undefined) {
      const lvl = Number(this.char.char_level);
      if (Number.isFinite(lvl)) {
        this.char.char_level = Math.max(1, Math.min(20, Math.round(lvl)));
      }
    }
    if (this.char.speed !== undefined) {
      const spd = Number(this.char.speed);
      if (Number.isFinite(spd)) {
        this.char.speed = Math.max(0, Math.min(300, Math.round(spd)));
      }
    }
    this.save.emit();
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
    return hasExhaustionDisadvantage(this.char, 'check');
  }

  get hasSaveDisadvantage(): boolean {
    return hasExhaustionDisadvantage(this.char, 'save');
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
