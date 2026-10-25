import { ChangeDetectionStrategy, Component, EventEmitter, inject, Input, Output, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { CharacterSchema, ClassResource, FeatureTrait } from '../../../../core/models/character.model';
import { HapticsService } from '../../../../core/services/haptics.service';
import { RollToastService } from '../../../../core/services/roll-toast.service';
import { ForgeBadgeComponent, ForgeButtonDirective, ForgeInputDirective, ForgeListRowComponent, ForgeModalComponent } from '../../../../shared/ui';
import { SpellDetailModalComponent } from '../../modals/spell-detail-modal/spell-detail-modal.component';

@Component({
  selector: 'app-spells-panel',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    ForgeBadgeComponent,
    ForgeButtonDirective,
    ForgeInputDirective,
    ForgeListRowComponent,
    ForgeModalComponent,
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

  @Output() useSpellSlot = new EventEmitter<number>();
  @Output() restoreSpellSlot = new EventEmitter<number>();
  @Output() save = new EventEmitter<void>();
  @Output() castSpell = new EventEmitter<{ spellName: string; level: number; isRitual: boolean }>();

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

  get allFeaturesExpanded(): boolean {
    return this.features.length > 0 && this.expandedFeatures.size === this.features.length;
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
    return (this.slotsRemaining(level) / max) * 100;
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
    this.features.forEach((_feature, index) => this.expandedFeatures.add(index));
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

  // --- 1-Tap Spell Casting Flow (#173) ---
  initiateCast(spellName: string, baseLevel: number, event: Event) {
    event.stopPropagation();
    this.haptics.lightTap();

    if (baseLevel === 0) {
      // Cantrip: cast for free!
      this.castSpell.emit({ spellName, level: 0, isRitual: false });
      return;
    }

    // Check available slot levels >= baseLevel
    const availableSlotLevels = this.spellLevels.filter(lvl => lvl >= baseLevel && this.slotsRemaining(lvl) > 0);

    if (availableSlotLevels.length === 0) {
      this.toast.showMessage('⚠️ NO SPELL SLOTS', `No available spell slots to cast ${spellName} (Level ${baseLevel}+).`);
      return;
    }

    if (availableSlotLevels.length === 1 && availableSlotLevels[0] === baseLevel) {
      // Exactly base level slot available: cast directly!
      this.useSpellSlot.emit(baseLevel);
      this.castSpell.emit({ spellName, level: baseLevel, isRitual: false });
      return;
    }

    // Multiple slots or upcasting possible: open upcast selector
    this.upcastTarget.set({ spellName, baseLevel });
  }

  confirmUpcast(slotLevel: number, isRitual = false) {
    const target = this.upcastTarget();
    if (!target) return;

    this.haptics.lightTap();
    if (!isRitual) {
      this.useSpellSlot.emit(slotLevel);
    }
    this.castSpell.emit({ spellName: target.spellName, level: slotLevel, isRitual });
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

  openAddResourceModal() {
    this.newResourceName = '';
    this.newResourceMax = 3;
    this.newResourceRecharge = 'long';
    this.showAddResourceModal.set(true);
  }

  closeAddResourceModal() {
    this.showAddResourceModal.set(false);
  }

  confirmAddResource() {
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
