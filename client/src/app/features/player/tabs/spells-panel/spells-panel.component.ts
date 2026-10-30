import { ChangeDetectionStrategy, Component, EventEmitter, inject, Input, Output, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { CharacterSchema, ClassResource, FeatureTrait } from '../../../../core/models/character.model';
import { HapticsService } from '../../../../core/services/haptics.service';
import { RollToastService } from '../../../../core/services/roll-toast.service';
import {
  MetamagicOption,
  SLOT_CREATION_COST,
  canCreateSlot,
  knownMetamagic,
  metamagicCost,
  metamagicEdition,
  metamagicKnownLimit,
  metamagicOptions,
  toggleMetamagicFeature,
  createdSlots,
  pointsFromSlot,
  sorceryPointsPool,
} from '../../../../core/rules';
import {
  ForgeBadgeComponent,
  ForgeButtonDirective,
  ForgeEmptyStateComponent,
  ForgeIconComponent,
  ForgeInputDirective,
  ForgeListRowComponent,
  ForgeModalComponent,
  ForgeSelectDirective,
} from '../../../../shared/ui';
import { SpellDetailModalComponent } from '../../modals/spell-detail-modal/spell-detail-modal.component';

@Component({
  selector: 'app-spells-panel',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    ForgeBadgeComponent,
    ForgeButtonDirective,
    ForgeEmptyStateComponent,
    ForgeIconComponent,
    ForgeInputDirective,
    ForgeListRowComponent,
    ForgeModalComponent,
    ForgeSelectDirective,
    SpellDetailModalComponent
  ],
  templateUrl: './spells-panel.component.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
  host: {
    class: 'block',
  },
})
export class SpellsPanelComponent {
  @Input({ required: true }) char!: CharacterSchema;
  @Input() getSpellSlotUsed!: (lvl: number) => number;
  @Input() getSpellSlotMax!: (lvl: number) => number;
  @Input() editMode = false;
  /** Dice a spell rolls at a slot level ("9d6"), or null when unknown. */
  @Input() castPreview: (spellName: string, slotLevel: number) => string | null = () => null;

  @Output() useSpellSlot = new EventEmitter<number>();
  @Output() restoreSpellSlot = new EventEmitter<number>();
  @Output() save = new EventEmitter<void>();
  /** `metamagic`: ids of the options applied to this cast; the container pays for them. */
  @Output() castSpell = new EventEmitter<{ spellName: string; level: number; isRitual: boolean; metamagic?: string[] }>();
  /** Sorcerer Flexible Casting: 'create' buys a slot with points, 'points' turns a slot into points. */
  @Output() flexibleCasting = new EventEmitter<{ direction: 'create' | 'points'; level: number }>();
  /** Spends sorcery points on a Metamagic option; `spellLevel` only matters for 2014 Twinned. */
  @Output() metamagic = new EventEmitter<{ optionId: string; spellLevel: number }>();

  private readonly haptics = inject(HapticsService);
  private readonly toast = inject(RollToastService);

  readonly spellLevels = [1, 2, 3, 4, 5, 6, 7, 8, 9];
  selectedSpell = signal<string | null>(null);
  addingSpellGroup = signal<string | null>(null);
  newSpellName = '';
  addingFeature = signal<boolean>(false);
  newFeatureName = '';

  // Search & Filter Pills (#173)
  searchQuery = signal<string>('');
  selectedFilter = signal<'all' | 'prepared' | 'cantrips'>('all');

  // Upcast Dialog State (#173)
  upcastTarget = signal<{ spellName: string; baseLevel: number } | null>(null);

  // Class Resources Modal State (#173)
  showAddResourceModal = signal<boolean>(false);
  newResourceName = '';
  newResourceMax = 3;
  newResourceRecharge: 'short' | 'long' = 'long';
  newResourceCurrent = 0;
  /** Adjustment on a rules pool's max (item, feat, house rule); may be negative. */
  newResourceBonus = 0;
  /** The pool the modal edits; null while it adds a new one. */
  editingResource: ClassResource | null = null;

  private readonly expandedFeatures = new Set<number>();

  get activeSpellLevels(): number[] {
    return this.spellLevels.filter((level) => this.getSpellSlotMax(level) > 0);
  }

  featuresSectionCollapsed = signal<boolean>(false);

  toggleFeaturesSection(): void {
    this.featuresSectionCollapsed.update((v) => !v);
  }

  get features(): FeatureTrait[] {
    const raw = this.char.features_traits ?? [];
    return raw.filter((f) => {
      const name = (f.name || '').trim().toLowerCase();
      const desc = (f.description || '').trim().toLowerCase();
      if (name === 'roll' || name === 'average' || name === 'manual') return false;
      if (desc.includes('selected for level_up_class') || desc.includes('selected for hp_method')) return false;
      return true;
    });
  }

  get classResources(): ClassResource[] {
    return this.char.class_resources ?? [];
  }

  /** Indexes of features that have text to open; a name alone has nothing to expand. */
  private get expandableFeatureIndexes(): number[] {
    return this.features.map((f, i) => (this.hasDetails(f) ? i : -1)).filter((i) => i >= 0);
  }

  hasDetails(feature: FeatureTrait): boolean {
    return !!(feature.description || '').trim();
  }

  get allFeaturesExpanded(): boolean {
    const expandable = this.expandableFeatureIndexes;
    return expandable.length > 0 && expandable.every((i) => this.expandedFeatures.has(i));
  }

  trackByLevel(_index: number, level: number): number {
    return level;
  }

  slotsRemaining(level: number): number {
    return this.getSpellSlotMax(level) - this.getSpellSlotUsed(level);
  }

  slotPercentage(level: number): number {
    const max = this.getSpellSlotMax(level);
    if (!max) return 0;
    return Math.min(100, (this.slotsRemaining(level) / max) * 100);
  }

  // --- Flexible Casting (Sorcerer) ---
  get sorceryPool(): ClassResource | null {
    return sorceryPointsPool(this.char);
  }

  /** Levels a slot can be bought at: 1st–5th, and only levels the sheet has. */
  get creatableLevels(): number[] {
    return this.activeSpellLevels.filter((lvl) => lvl in SLOT_CREATION_COST);
  }

  slotCost(level: number): number {
    return SLOT_CREATION_COST[level];
  }

  canCreate(level: number): boolean {
    return canCreateSlot(this.char, level);
  }

  pointsFrom(level: number): number {
    return pointsFromSlot(this.char, level);
  }

  createdSlotCount(level: number): number {
    return createdSlots(this.char, level);
  }

  // --- Metamagic (Sorcerer) ---
  choosingMetamagic = signal<boolean>(false);
  /** The option whose spell-level picker is open (2014 Twinned). */
  twinPicking = signal<string | null>(null);

  get metamagicOptionList(): MetamagicOption[] {
    return metamagicOptions(metamagicEdition(this.char.dnd_edition));
  }

  get metamagicLimit(): number {
    return metamagicKnownLimit(this.char, metamagicEdition(this.char.dnd_edition));
  }

  get knownMetamagicOptions(): MetamagicOption[] {
    const options = this.metamagicOptionList;
    const known = knownMetamagic(this.char, options);
    return options.filter((o) => known.has(o.id));
  }

  isMetamagicKnown(option: MetamagicOption): boolean {
    return this.knownMetamagicOptions.some((o) => o.id === option.id);
  }

  toggleMetamagic(option: MetamagicOption): void {
    this.char.features_traits = toggleMetamagicFeature(this.char.features_traits, option);
    this.save.emit();
  }

  metamagicMinCost(option: MetamagicOption): number {
    return metamagicCost(option, 0);
  }

  /** Cantrip plus every level the sheet has slots for. */
  get twinLevels(): number[] {
    return [0, ...this.activeSpellLevels];
  }

  twinCost(option: MetamagicOption, spellLevel: number): number {
    return metamagicCost(option, spellLevel);
  }

  useMetamagic(option: MetamagicOption, spellLevel?: number): void {
    if (option.costBySpellLevel && spellLevel === undefined) {
      this.twinPicking.update((open) => (open === option.id ? null : option.id));
      return;
    }
    this.twinPicking.set(null);
    this.haptics.lightTap();
    this.metamagic.emit({ optionId: option.id, spellLevel: spellLevel ?? 1 });
  }

  isFeatureExpanded(index: number): boolean {
    return this.expandedFeatures.has(index);
  }

  toggleFeature(index: number): void {
    if (this.expandedFeatures.has(index)) {
      this.expandedFeatures.delete(index);
      return;
    }
    this.expandedFeatures.add(index);
  }

  toggleAllFeatures(): void {
    if (this.allFeaturesExpanded) {
      this.expandedFeatures.clear();
      return;
    }
    this.expandableFeatureIndexes.forEach((index) => this.expandedFeatures.add(index));
  }

  get rawSpellGroups(): { label: string; level: number; spells: string[] }[] {
    const groups: { label: string; level: number; spells: string[] }[] = [];
    const spells = this.char.spells;
    if (!spells) return groups;

    if (spells.cantrips && spells.cantrips.length > 0) {
      groups.push({ label: 'Cantrips', level: 0, spells: spells.cantrips });
    } else if (this.editMode) {
      groups.push({ label: 'Cantrips', level: 0, spells: [] });
    }

    const levelKeys: (keyof typeof spells)[] = [
      'level_1', 'level_2', 'level_3', 'level_4', 'level_5',
      'level_6', 'level_7', 'level_8', 'level_9'
    ];

    levelKeys.forEach((key, index) => {
      const levelSpells = spells[key];
      if (Array.isArray(levelSpells) && levelSpells.length > 0) {
        groups.push({ label: `Level ${index + 1}`, level: index + 1, spells: levelSpells });
      } else if (this.editMode) {
        groups.push({ label: `Level ${index + 1}`, level: index + 1, spells: [] });
      }
    });

    return groups;
  }

  get filteredSpellGroups(): { label: string; level: number; spells: string[] }[] {
    const query = this.searchQuery().trim().toLowerCase();
    const filter = this.selectedFilter();

    return this.rawSpellGroups
      .map(group => {
        if (filter === 'cantrips' && group.level !== 0) {
          return { ...group, spells: [] };
        }

        const matchingSpells = group.spells.filter(spell => {
          if (filter === 'prepared' && !this.isPrepared(spell) && group.level > 0) {
            return false;
          }
          if (query && !spell.toLowerCase().includes(query)) {
            return false;
          }
          return true;
        });

        return { ...group, spells: matchingSpells };
      })
      .filter(group => group.spells.length > 0 || (this.editMode && !query && filter === 'all'));
  }

  isPrepared(spellName: string): boolean {
    if (!this.char.prepared_spells) return false;
    return this.char.prepared_spells.includes(spellName);
  }

  // --- Spell Casting (#173) ---
  /** Lowest slot level >= the spell's that still has a slot, or null. */
  lowestOpenSlot(baseLevel: number): number | null {
    if (baseLevel === 0) return 0;
    return this.spellLevels.find((lvl) => lvl >= baseLevel && this.slotsRemaining(lvl) > 0) ?? null;
  }

  /**
   * One click: cantrips cast for free; leveled spells spend the lowest open slot
   * (the base level when there is one). The ▾ next to Cast is for upcasting.
   */
  castNow(spellName: string, baseLevel: number, event: Event) {
    event.stopPropagation();
    this.haptics.lightTap();

    const slot = this.lowestOpenSlot(baseLevel);
    if (slot === null) {
      this.toast.showMessage('⚠️ NO SPELL SLOTS', `No spell slots of level ${baseLevel} or higher left for ${spellName}.`);
      return;
    }
    if (slot > 0) this.useSpellSlot.emit(slot);
    this.castSpell.emit({ spellName, level: slot, isRitual: false });
  }

  openCastOptions(spellName: string, baseLevel: number, event: Event) {
    event.stopPropagation();
    this.castMetamagic.set([]);
    this.upcastTarget.set({ spellName, baseLevel });
  }

  /** Metamagic picked in the cast window, paid when the slot is chosen. */
  castMetamagic = signal<string[]>([]);

  isCastMetamagic(option: MetamagicOption): boolean {
    return this.castMetamagic().includes(option.id);
  }

  toggleCastMetamagic(option: MetamagicOption): void {
    this.castMetamagic.update((ids) =>
      ids.includes(option.id) ? ids.filter((id) => id !== option.id) : [...ids, option.id]
    );
  }

  /** What the picked options cost when cast with a slot of `slotLevel` (2014 Twinned pays the level). */
  castMetamagicCost(slotLevel: number): number {
    return this.knownMetamagicOptions
      .filter((o) => this.isCastMetamagic(o))
      .reduce((sum, o) => sum + metamagicCost(o, slotLevel), 0);
  }

  canPayCastMetamagic(slotLevel: number): boolean {
    return this.castMetamagicCost(slotLevel) <= (this.sorceryPool?.current ?? 0);
  }

  canAddCastMetamagic(option: MetamagicOption, baseLevel: number): boolean {
    return this.castMetamagicCost(baseLevel) + metamagicCost(option, baseLevel) <= (this.sorceryPool?.current ?? 0);
  }

  confirmUpcast(slotLevel: number, isRitual = false) {
    const target = this.upcastTarget();
    if (!target) return;

    this.haptics.lightTap();
    if (!isRitual) {
      this.useSpellSlot.emit(slotLevel);
    }
    const metamagic = this.castMetamagic();
    this.castSpell.emit({
      spellName: target.spellName,
      level: slotLevel,
      isRitual,
      ...(metamagic.length ? { metamagic } : {}),
    });
    this.castMetamagic.set([]);
    this.upcastTarget.set(null);
  }

  closeUpcast() {
    this.upcastTarget.set(null);
  }

  getAvailableUpcastLevels(baseLevel: number): number[] {
    return this.spellLevels.filter(lvl => lvl >= baseLevel && this.slotsRemaining(lvl) > 0);
  }

  // --- Class Resources (#173) ---
  incrementResource(res: ClassResource, event: Event) {
    event.stopPropagation();
    this.haptics.lightTap();
    if (res.current < res.max) {
      res.current += 1;
      this.save.emit();
    }
  }

  decrementResource(res: ClassResource, event: Event) {
    event.stopPropagation();
    this.haptics.lightTap();
    if (res.current > 0) {
      res.current -= 1;
      this.save.emit();
    }
  }

  openEditResource(index: number, event: Event) {
    event.stopPropagation();
    const res = this.classResources[index];
    if (!res) return;
    this.editingResource = res;
    this.newResourceName = res.name;
    this.newResourceMax = res.max;
    this.newResourceCurrent = res.current;
    this.newResourceBonus = res.bonus ?? 0;
    this.newResourceRecharge = res.recharge;
    this.showAddResourceModal.set(true);
  }

  /** What the class rules alone give a rules pool. */
  get resourceRulesMax(): number {
    const res = this.editingResource;
    return res ? res.max - (res.bonus ?? 0) : 0;
  }

  get resourceEditedMax(): number {
    if (this.editingResource?.auto) {
      return Math.max(1, this.resourceRulesMax + (Number(this.newResourceBonus) || 0));
    }
    return Math.max(1, Number(this.newResourceMax) || 1);
  }

  openAddResourceModal() {
    this.editingResource = null;
    this.newResourceName = '';
    this.newResourceMax = 3;
    this.newResourceRecharge = 'long';
    this.showAddResourceModal.set(true);
  }

  closeAddResourceModal() {
    this.editingResource = null;
    this.showAddResourceModal.set(false);
  }

  confirmAddResource() {
    const editing = this.editingResource;
    if (editing) {
      const max = this.resourceEditedMax;
      const current = Math.min(max, Math.max(0, Math.floor(Number(this.newResourceCurrent) || 0)));
      // A rules pool keeps its name and recharge (the server sets them); the
      // adjustment rides on top of the rules max on every level up.
      const changes: Partial<ClassResource> = editing.auto
        ? { max, current, bonus: max - this.resourceRulesMax }
        : { name: this.newResourceName.trim() || editing.name, max, current, recharge: this.newResourceRecharge };
      this.char.class_resources = this.classResources.map((r) => (r === editing ? { ...r, ...changes } : r));
      this.save.emit();
      this.closeAddResourceModal();
      return;
    }

    const name = this.newResourceName.trim();
    if (!name) return;

    if (!this.char.class_resources) {
      this.char.class_resources = [];
    }
    const maxVal = Math.max(1, this.newResourceMax || 1);
    this.char.class_resources.push({
      name,
      current: maxVal,
      max: maxVal,
      recharge: this.newResourceRecharge,
    });
    this.save.emit();
    this.closeAddResourceModal();
  }

  deleteResource(index: number, event: Event) {
    event.stopPropagation();
    if (this.char.class_resources) {
      this.char.class_resources.splice(index, 1);
      this.save.emit();
    }
  }

  // --- Spell Management ---
  addSpell(levelLabel: string, explicitName?: string) {
    if (explicitName !== undefined) {
      this.newSpellName = explicitName;
      this.confirmAddSpell(levelLabel);
      return;
    }
    this.addingSpellGroup.set(levelLabel);
    this.newSpellName = '';
  }

  confirmAddSpell(levelLabel: string) {
    const spellName = this.newSpellName.trim();
    if (spellName) {
      if (!this.char.spells) {
        this.char.spells = { cantrips: [], level_1: [], level_2: [], level_3: [], level_4: [], level_5: [], level_6: [], level_7: [], level_8: [], level_9: [] };
      }
      const lvlMap: Record<string, string> = {
        'Cantrips': 'cantrips', 'Level 1': 'level_1', 'Level 2': 'level_2', 'Level 3': 'level_3', 'Level 4': 'level_4', 'Level 5': 'level_5', 'Level 6': 'level_6', 'Level 7': 'level_7', 'Level 8': 'level_8', 'Level 9': 'level_9'
      };
      const key = lvlMap[levelLabel];
      if (key) {
        const spellsObj = this.char.spells as any;
        if (!spellsObj[key]) spellsObj[key] = [];
        spellsObj[key].push(spellName);
        this.save.emit();
      }
    }
    this.addingSpellGroup.set(null);
    this.newSpellName = '';
  }

  cancelAddSpell() {
    this.addingSpellGroup.set(null);
    this.newSpellName = '';
  }

  deleteSpell(levelLabel: string, index: number, event: Event) {
    event.stopPropagation();
    const lvlMap: Record<string, string> = {
        'Cantrips': 'cantrips', 'Level 1': 'level_1', 'Level 2': 'level_2', 'Level 3': 'level_3', 'Level 4': 'level_4', 'Level 5': 'level_5', 'Level 6': 'level_6', 'Level 7': 'level_7', 'Level 8': 'level_8', 'Level 9': 'level_9'
    };
    const key = lvlMap[levelLabel];
    if (key) {
      (this.char.spells as any)[key].splice(index, 1);
      this.save.emit();
    }
  }

  addFeature(explicitName?: string) {
    if (explicitName !== undefined) {
      this.newFeatureName = explicitName;
      this.confirmAddFeature();
      return;
    }
    this.addingFeature.set(true);
    this.newFeatureName = '';
  }

  confirmAddFeature() {
    const featName = this.newFeatureName.trim();
    if (featName) {
      if (!this.char.features_traits) this.char.features_traits = [];
      this.char.features_traits.push({ name: featName, description: 'Manually added trait', source: 'Custom' });
      this.save.emit();
    }
    this.addingFeature.set(false);
    this.newFeatureName = '';
  }

  cancelAddFeature() {
    this.addingFeature.set(false);
    this.newFeatureName = '';
  }

  deleteFeature(index: number, event: Event) {
    event.stopPropagation();
    if (this.char.features_traits) {
      this.char.features_traits.splice(index, 1);
      this.save.emit();
    }
  }
}
