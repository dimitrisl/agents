import { ChangeDetectionStrategy, Component, EventEmitter, Input, Output } from '@angular/core';
import { CommonModule } from '@angular/common';
import { CharacterSchema, FeatureTrait } from '../../../../core/models/character.model';
import { ForgeBadgeComponent, ForgeButtonDirective, ForgeListRowComponent } from '../../../../shared/ui';

@Component({
  selector: 'app-spells-panel',
  standalone: true,
  imports: [CommonModule, ForgeBadgeComponent, ForgeButtonDirective, ForgeListRowComponent],
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

  @Output() useSpellSlot = new EventEmitter<number>();
  @Output() restoreSpellSlot = new EventEmitter<number>();

  readonly spellLevels = [1, 2, 3, 4, 5, 6, 7, 8, 9];

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
      }
    });

    return groups;
  }

  isPrepared(spellName: string): boolean {
    if (!this.char.prepared_spells) return false;
    return this.char.prepared_spells.includes(spellName);
  }
}
