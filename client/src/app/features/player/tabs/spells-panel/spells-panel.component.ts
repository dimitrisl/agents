import { ChangeDetectionStrategy, Component, EventEmitter, Input, Output } from '@angular/core';
import { CommonModule } from '@angular/common';
import { CharacterSchema, FeatureTrait } from '../../../../core/models/character.model';
import { ForgeBadgeComponent, ForgeButtonDirective } from '../../../../shared/ui';

@Component({
  selector: 'app-spells-panel',
  standalone: true,
  imports: [CommonModule, ForgeBadgeComponent, ForgeButtonDirective],
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
}
