import { ChangeDetectionStrategy, Component, EventEmitter, Input, Output } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import {
  ForgeBadgeComponent,
  ForgeButtonDirective,
  ForgeInputDirective,
  ForgeSelectDirective,
  ForgeTextareaDirective,
} from '../../../shared/ui';
import {
  ALL_DND_SKILLS,
  ClassSkillRules,
  getClassSkillRules,
  getRecommendedFeats,
  getRecommendedSpells,
  isSpellcasterClass,
} from '../../../core/rules/recommendations';

@Component({
  selector: 'app-manual-form',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    ForgeBadgeComponent,
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

  // Manual explicit choices
  @Input() manualSkills: string[] = [];
  @Input() manualFeats: string[] = [];
  @Input() manualSpells: string[] = [];
  @Input() availableFeats: any[] = [];
  @Input() availableSpells: any[] = [];

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

  @Output() manualSkillsChange = new EventEmitter<string[]>();
  @Output() manualFeatsChange = new EventEmitter<string[]>();
  @Output() manualSpellsChange = new EventEmitter<string[]>();

  @Output() updateManualSubclasses = new EventEmitter<void>();
  @Output() rollStats = new EventEmitter<void>();
  @Output() create = new EventEmitter<void>();

  // --- Skills Section ---
  readonly allSkills = ALL_DND_SKILLS;

  get skillRules(): ClassSkillRules {
    return getClassSkillRules(this.manualClass);
  }

  isSkillSelected(name: string): boolean {
    return (this.manualSkills || []).includes(name);
  }

  isSkillRecommended(name: string): boolean {
    return this.skillRules.recommended.includes(name);
  }

  isSkillAllowed(name: string): boolean {
    return this.skillRules.allowed.includes(name);
  }

  toggleSkill(name: string): void {
    const list = [...(this.manualSkills || [])];
    const idx = list.indexOf(name);
    if (idx >= 0) {
      list.splice(idx, 1);
    } else {
      list.push(name);
    }
    this.manualSkills = list;
    this.manualSkillsChange.emit(this.manualSkills);
  }

  loadSkillSuggestions(): void {
    this.manualSkills = [...this.skillRules.recommended];
    this.manualSkillsChange.emit(this.manualSkills);
  }

  // --- Feats Section ---
  featTab: 'origin' | 'general' | 'all' = 'origin';
  featSearch = '';

  get filteredFeats(): any[] {
    const search = (this.featSearch || '').toLowerCase().trim();
    return (this.availableFeats || []).filter((f) => {
      const name = (f.name || '').toLowerCase();
      const desc = (f.description || '').toLowerCase();
      const category = (f.category || '').toLowerCase();
      const isOrigin = category.includes('origin') || f.prerequisites?.min_level === 0;

      if (this.featTab === 'origin' && !isOrigin) return false;
      if (this.featTab === 'general' && isOrigin) return false;

      if (search && !name.includes(search) && !desc.includes(search)) return false;
      return true;
    });
  }

  isFeatSelected(name: string): boolean {
    return (this.manualFeats || []).includes(name);
  }

  isFeatRecommended(name: string): boolean {
    return getRecommendedFeats(this.manualClass, this.manualLevel, this.is2024).includes(name);
  }

  toggleFeat(name: string): void {
    const list = [...(this.manualFeats || [])];
    const idx = list.indexOf(name);
    if (idx >= 0) {
      list.splice(idx, 1);
    } else {
      list.push(name);
    }
    this.manualFeats = list;
    this.manualFeatsChange.emit(this.manualFeats);
  }

  loadFeatSuggestions(): void {
    const recs = getRecommendedFeats(this.manualClass, this.manualLevel, this.is2024);
    const count = this.is2024 ? (this.manualLevel >= 4 ? 2 : 1) : this.manualLevel >= 4 ? 1 : 1;
    const toPick = recs.slice(0, count);
    this.manualFeats = Array.from(new Set([...(this.manualFeats || []), ...toPick]));
    this.manualFeatsChange.emit(this.manualFeats);
  }

  // --- Spells Section ---
  spellSearch = '';
  spellSchoolFilter = 'All';
  spellLevelTab: number | 'all' = 0;

  readonly spellSchools = [
    'All',
    'Abjuration',
    'Conjuration',
    'Divination',
    'Enchantment',
    'Evocation',
    'Illusion',
    'Necromancy',
    'Transmutation',
  ];

  get isSpellcaster(): boolean {
    return isSpellcasterClass(this.manualClass, this.manualSubclass, this.manualLevel, this.is2024);
  }

  get unlockedSpellLevels(): number[] {
    const lvls = new Set<number>();
    (this.availableSpells || []).forEach((s) => {
      if (typeof s.level === 'number') lvls.add(s.level);
    });
    if (lvls.size === 0) return [0, 1];
    return Array.from(lvls).sort((a, b) => a - b);
  }

  get filteredSpells(): any[] {
    const search = (this.spellSearch || '').toLowerCase().trim();
    const school = (this.spellSchoolFilter || 'All').toLowerCase();

    return (this.availableSpells || []).filter((s) => {
      if (this.spellLevelTab !== 'all' && s.level !== this.spellLevelTab) return false;
      if (school !== 'all' && (s.school || '').toLowerCase() !== school) return false;
      if (
        search &&
        !(s.name || '').toLowerCase().includes(search) &&
        !(s.description || '').toLowerCase().includes(search)
      ) {
        return false;
      }
      return true;
    });
  }

  isSpellSelected(name: string): boolean {
    return (this.manualSpells || []).includes(name);
  }

  isSpellRecommended(name: string): boolean {
    return getRecommendedSpells(this.manualClass).includes(name);
  }

  toggleSpell(name: string): void {
    const list = [...(this.manualSpells || [])];
    const idx = list.indexOf(name);
    if (idx >= 0) {
      list.splice(idx, 1);
    } else {
      list.push(name);
    }
    this.manualSpells = list;
    this.manualSpellsChange.emit(this.manualSpells);
  }

  loadSpellSuggestions(): void {
    const recs = getRecommendedSpells(this.manualClass);
    const validRecs = (this.availableSpells || [])
      .filter((s) => recs.includes(s.name))
      .map((s) => s.name);
    this.manualSpells = Array.from(new Set([...(this.manualSpells || []), ...validRecs]));
    this.manualSpellsChange.emit(this.manualSpells);
  }

  getSelectedSpellsCountByLevel(lvl: number): number {
    return (this.availableSpells || []).filter((s) => s.level === lvl && this.isSpellSelected(s.name)).length;
  }

  // --- Ability Scores Logic ---
  isValueSelected(val: number, currentStat: string): boolean {
    if (this.manualStatMethod !== 'standard') return false;
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

    this.statKeys.forEach((key) => {
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

    if (newCost <= currentCost || this.getRemainingPoints() >= newCost - currentCost) {
      this.manualStats = { ...this.manualStats, [stat]: score };
      this.manualStatsChange.emit(this.manualStats);
    } else {
      this.manualStatsChange.emit({ ...this.manualStats });
    }
  }
}
