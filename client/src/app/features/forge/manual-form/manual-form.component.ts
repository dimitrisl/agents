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
  getMaxCantrips,
  getMaxGeneralFeats,
  getMaxOriginFeats,
  getMaxPreparedSpells,
  getMaxCastableSpellLevel,
  getRecommendedFeats,
  getRecommendedSpells,
  isSpellcasterClass,
  ORIGIN_SUGGESTED_FEATS,
  getBackgroundSkills,
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
  @Input() is2024 = true;
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

  get backgroundSkills(): string[] {
    return getBackgroundSkills(this.manualBackground);
  }

  isBackgroundSkill(name: string): boolean {
    return this.backgroundSkills.some((s) => s.toLowerCase() === (name || '').toLowerCase());
  }

  loadSkillSuggestions(): void {
    const bgSkills = this.backgroundSkills.map((s) => s.toLowerCase());
    // Filter out skills already granted by background so choices aren't duplicated
    const nonBgRecs = this.skillRules.recommended.filter((s) => !bgSkills.includes(s.toLowerCase()));
    const needed = this.skillRules.count;
    const finalSkills = [...nonBgRecs];
    if (finalSkills.length < needed) {
      const remainingAllowed = this.skillRules.allowed.filter(
        (s) => !bgSkills.includes(s.toLowerCase()) && !finalSkills.includes(s)
      );
      finalSkills.push(...remainingAllowed.slice(0, needed - finalSkills.length));
    }
    this.manualSkills = finalSkills.slice(0, needed);
    this.manualSkillsChange.emit(this.manualSkills);
  }

  // --- Feats Section & Limits ---
  featTab: 'origin' | 'general' | 'all' = 'origin';
  featSearch = '';
  featLimitWarning: string | null = null;

  isOriginFeat(feat: any): boolean {
    const name = typeof feat === 'string' ? feat : feat?.name || '';
    const category = (feat?.category || '').toLowerCase();
    if (category.includes('origin')) return true;
    if (ORIGIN_SUGGESTED_FEATS.some((of) => of.toLowerCase() === name.toLowerCase())) return true;
    return this.is2024 && feat?.prerequisites?.min_level === 0;
  }

  canAddFeat(feat: any): boolean {
    const isOrigin = this.isOriginFeat(feat);
    if (isOrigin) {
      return this.originFeatsCount < this.maxOriginFeats || this.generalFeatsCount < this.maxGeneralFeats;
    }
    return this.generalFeatsCount < this.maxGeneralFeats;
  }

  get maxOriginFeats(): number {
    return getMaxOriginFeats(this.manualRace, this.is2024 ? '2024' : '2014');
  }

  get maxGeneralFeats(): number {
    return getMaxGeneralFeats(this.manualClass, this.manualLevel);
  }

  private get rawOriginFeatsSelected(): number {
    return (this.manualFeats || []).filter((name) => {
      const f = (this.availableFeats || []).find((feat) => feat.name === name) || { name };
      return f && this.isOriginFeat(f);
    }).length;
  }

  get originFeatsCount(): number {
    return Math.min(this.rawOriginFeatsSelected, this.maxOriginFeats);
  }

  get generalFeatsCount(): number {
    const total = (this.manualFeats || []).length;
    const nonOrigin = total - this.rawOriginFeatsSelected;
    const overflowOrigin = Math.max(0, this.rawOriginFeatsSelected - this.maxOriginFeats);
    return nonOrigin + overflowOrigin;
  }

  get filteredFeats(): any[] {
    const search = (this.featSearch || '').toLowerCase().trim();
    return (this.availableFeats || []).filter((f) => {
      const name = (f.name || '').toLowerCase();
      const desc = (f.description || '').toLowerCase();
      const isOrigin = this.isOriginFeat(f);

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
    this.featLimitWarning = null;
    const list = [...(this.manualFeats || [])];
    const idx = list.indexOf(name);

    if (idx >= 0) {
      list.splice(idx, 1);
    } else {
      const f = (this.availableFeats || []).find((feat) => feat.name === name) || { name };
      const isOrigin = this.isOriginFeat(f);

      if (isOrigin) {
        if (this.originFeatsCount >= this.maxOriginFeats && this.generalFeatsCount >= this.maxGeneralFeats) {
          if (this.maxOriginFeats === 0 && !this.is2024) {
            this.featLimitWarning = `In 2014 rules, only Variant Human receives a bonus feat at Level 1. Switch species to Variant Human or level up to 4.`;
          } else if (this.maxGeneralFeats === 0) {
            this.featLimitWarning = `Origin Feat limit reached (${this.maxOriginFeats}). General feats unlock at Level 4. Deselect an Origin Feat first.`;
          } else {
            this.featLimitWarning = `Feat capacity reached (${this.maxOriginFeats} Origin + ${this.maxGeneralFeats} General allowed for Level ${this.manualLevel} ${this.manualClass}). Deselect one first.`;
          }
          return;
        }
      } else {
        if (this.generalFeatsCount >= this.maxGeneralFeats) {
          if (this.maxGeneralFeats === 0) {
            this.featLimitWarning = `General Feats unlock at Level 4 (ASI milestones). You cannot select General Feats at Level ${this.manualLevel}.`;
          } else {
            this.featLimitWarning = `General Feat limit reached (${this.maxGeneralFeats} allowed for Level ${this.manualLevel} ${this.manualClass}). Deselect one first.`;
          }
          return;
        }
      }
      list.push(name);
    }
    this.manualFeats = list;
    this.manualFeatsChange.emit(this.manualFeats);
  }

  loadFeatSuggestions(): void {
    this.featLimitWarning = null;
    const recs = getRecommendedFeats(this.manualClass, this.manualLevel, this.is2024);
    const chosen: string[] = [];

    // Fill origin feats up to maxOriginFeats
    const originRecs = recs.filter((name) => {
      const f = (this.availableFeats || []).find((feat) => feat.name === name) || { name };
      return f && this.isOriginFeat(f);
    });
    chosen.push(...originRecs.slice(0, this.maxOriginFeats));

    // Fill general feats up to maxGeneralFeats
    const generalRecs = recs.filter((name) => !chosen.includes(name));
    chosen.push(...generalRecs.slice(0, this.maxGeneralFeats));

    this.manualFeats = Array.from(new Set(chosen));
    this.manualFeatsChange.emit(this.manualFeats);
  }

  // --- Spells Section & Limits ---
  spellSearch = '';
  spellSchoolFilter = 'All';
  spellLevelTab: number | 'all' = 0;
  spellLimitWarning: string | null = null;

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

  get spellAbilityKey(): string {
    const c = (this.manualClass || '').toLowerCase();
    if (['cleric', 'druid', 'ranger'].includes(c)) return 'WIS';
    if (['bard', 'paladin', 'sorcerer', 'warlock'].includes(c)) return 'CHA';
    return 'INT';
  }

  get spellAbilityMod(): number {
    const score = this.getFinalStat ? this.getFinalStat(this.spellAbilityKey) : 10;
    return Math.floor((score - 10) / 2);
  }

  get maxCantrips(): number {
    return getMaxCantrips(this.manualClass, this.manualLevel, this.manualSubclass);
  }

  get maxPreparedSpells(): number {
    return getMaxPreparedSpells(this.manualClass, this.manualLevel, this.spellAbilityMod, this.is2024, this.manualSubclass);
  }

  get cantripsCount(): number {
    return this.getSelectedSpellsCountByLevel(0);
  }

  get leveledSpellsCount(): number {
    return (this.manualSpells || []).filter((name) => {
      const s = (this.availableSpells || []).find((sp) => sp.name === name);
      if (s) return s.level > 0;
      return true;
    }).length;
  }

  get maxCastableLevel(): number {
    return getMaxCastableSpellLevel(this.manualClass, this.manualLevel, this.is2024, this.manualSubclass);
  }

  get unlockedSpellLevels(): number[] {
    const maxLvl = this.maxCastableLevel;
    const lvls = new Set<number>();
    lvls.add(0); // Always include Cantrips for casters
    for (let i = 1; i <= maxLvl; i++) {
      lvls.add(i);
    }
    // Also include any levels present in availableSpells that do not exceed maxLvl
    (this.availableSpells || []).forEach((s) => {
      if (typeof s.level === 'number' && s.level <= maxLvl) {
        lvls.add(s.level);
      }
    });
    return Array.from(lvls).sort((a, b) => a - b);
  }

  get filteredSpells(): any[] {
    const search = (this.spellSearch || '').toLowerCase().trim();
    const school = (this.spellSchoolFilter || 'All').toLowerCase();
    const maxLvl = this.maxCastableLevel;

    return (this.availableSpells || []).filter((s) => {
      if (typeof s.level === 'number' && s.level > maxLvl) return false;
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

  canAddSpell(spell: any): boolean {
    const isCantrip = spell && spell.level === 0;
    return isCantrip ? this.cantripsCount < this.maxCantrips : this.leveledSpellsCount < this.maxPreparedSpells;
  }

  isSpellSelected(name: string): boolean {
    return (this.manualSpells || []).includes(name);
  }

  isSpellRecommended(name: string): boolean {
    return getRecommendedSpells(this.manualClass, this.manualSubclass).includes(name);
  }

  toggleSpell(name: string): void {
    this.spellLimitWarning = null;
    const list = [...(this.manualSpells || [])];
    const idx = list.indexOf(name);

    if (idx >= 0) {
      list.splice(idx, 1);
    } else {
      const s = (this.availableSpells || []).find((sp) => sp.name === name) || { name, level: 1 };
      const isCantrip = s && s.level === 0;

      if (isCantrip && this.cantripsCount >= this.maxCantrips) {
        this.spellLimitWarning = `Cantrip limit reached (${this.maxCantrips} allowed for Level ${this.manualLevel} ${this.manualClass}). Deselect one first.`;
        return;
      }
      if (!isCantrip && this.leveledSpellsCount >= this.maxPreparedSpells) {
        this.spellLimitWarning = `Prepared spell limit reached (${this.maxPreparedSpells} allowed for Level ${this.manualLevel} ${this.manualClass}). Deselect one first.`;
        return;
      }
      list.push(name);
    }
    this.manualSpells = list;
    this.manualSpellsChange.emit(this.manualSpells);
  }

  loadSpellSuggestions(): void {
    this.spellLimitWarning = null;
    const recs = getRecommendedSpells(this.manualClass, this.manualSubclass);
    const chosen: string[] = [];

    // Pick cantrips up to maxCantrips
    const cantripRecs = (this.availableSpells || [])
      .filter((s) => s.level === 0 && recs.includes(s.name))
      .map((s) => s.name);
    chosen.push(...cantripRecs.slice(0, this.maxCantrips));

    // Pick leveled spells up to maxPreparedSpells
    const leveledRecs = (this.availableSpells || [])
      .filter((s) => s.level > 0 && recs.includes(s.name))
      .map((s) => s.name);
    chosen.push(...leveledRecs.slice(0, this.maxPreparedSpells));

    this.manualSpells = Array.from(new Set(chosen));
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
