import { ChangeDetectionStrategy, Component, EventEmitter, Input, Output, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { CharacterSchema, FeatureTrait } from '../../../../core/models/character.model';
import { ForgeBadgeComponent, ForgeButtonDirective, ForgeListRowComponent } from '../../../../shared/ui';
import { SpellDetailModalComponent } from '../../modals/spell-detail-modal/spell-detail-modal.component';

@Component({
  selector: 'app-spells-panel',
  standalone: true,
  imports: [CommonModule, ForgeBadgeComponent, ForgeButtonDirective, ForgeListRowComponent, SpellDetailModalComponent],
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

  readonly spellLevels = [1, 2, 3, 4, 5, 6, 7, 8, 9];
  selectedSpell = signal<string | null>(null);

  private readonly expandedFeatures = new Set<number>();

  // Only levels the character actually has slots for. A level 1 cleric should
  // not have to scan past eight empty "0 / 0" tiles to find its one slot row.
  get activeSpellLevels(): number[] {
    return this.spellLevels.filter((level) => this.getSpellSlotMax(level) > 0);
  }

  get features(): FeatureTrait[] {
    return this.char.features_traits ?? [];
  }

  get allFeaturesExpanded(): boolean {
    return this.features.length > 0 && this.expandedFeatures.size === this.features.length;
  }

  trackByLevel(_index: number, level: number): number {
    return level;
  }

  // The tracker counts down like a real slot pool: "2 of 2 left" becomes "1 of 2"
  // after casting, so the − button always lowers the number on screen.
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

  get spellGroups(): { label: string; level: number; spells: string[] }[] {
    const groups: { label: string; level: number; spells: string[] }[] = [];
    const spells = this.char.spells;
    if (!spells) return groups;

    if (spells.cantrips && spells.cantrips.length > 0) {
      groups.push({ label: 'Cantrips', level: 0, spells: spells.cantrips });
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

  isPrepared(spellName: string): boolean {
    if (!this.char.prepared_spells) return false;
    return this.char.prepared_spells.includes(spellName);
  }

  addSpell(levelLabel: string) {
    const spellName = prompt(`Enter spell name for ${levelLabel}:`);
    if (spellName && spellName.trim()) {
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
        spellsObj[key].push(spellName.trim());
        this.save.emit();
      }
    }
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

  addFeature() {
    const featName = prompt('Enter Feature name:');
    if (featName && featName.trim()) {
      if (!this.char.features_traits) this.char.features_traits = [];
      this.char.features_traits.push({ name: featName.trim(), description: 'Manually added trait', source: 'Custom' });
      this.save.emit();
    }
  }

  deleteFeature(index: number, event: Event) {
    event.stopPropagation();
    if (this.char.features_traits) {
      this.char.features_traits.splice(index, 1);
      this.save.emit();
    }
  }
}
