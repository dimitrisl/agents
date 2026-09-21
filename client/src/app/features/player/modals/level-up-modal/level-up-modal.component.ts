import { ChangeDetectionStrategy, Component, EventEmitter, Input, Output } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ForgeButtonDirective, ForgeModalComponent, ForgeSelectDirective } from '../../../../shared/ui';
import { LevelUpAnalysis, CharacterSchema } from '../../../../core/models/character.model';
import { DiceService } from '../../../../core/services/dice.service';
import { abilityModifier } from '../../../../core/rules';

@Component({
  selector: 'app-level-up-modal',
  standalone: true,
  imports: [CommonModule, FormsModule, ForgeButtonDirective, ForgeModalComponent, ForgeSelectDirective],
  templateUrl: './level-up-modal.component.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class LevelUpModalComponent {
  constructor(private dice: DiceService) {}

  @Input() open = false;
  @Input() character: CharacterSchema | null = null;
  @Input() nextLevel = 1;
  @Input() levelUpAnalysis: LevelUpAnalysis | null = null;
  @Input() userChoices: Record<string, any> = {};

  @Output() openChange = new EventEmitter<boolean>();
  @Output() applyLevelUp = new EventEmitter<void>();
  @Output() userChoicesChange = new EventEmitter<Record<string, any>>();

  onChoiceChange(choiceKey: string, val: string) {
    this.userChoices = { ...this.userChoices, [choiceKey]: val };
    this.userChoicesChange.emit(this.userChoices);
  }

  selectHpAverage() {
    if (!this.levelUpAnalysis) return;
    this.onChoiceChange('hp_method', 'average');
    this.onChoiceChange('custom_hp_increase', this.levelUpAnalysis.hp_increase.toString());
  }

  rollHp() {
    if (this.userChoices['hp_method'] === 'roll') return; // locked after first roll
    if (!this.character || !this.character.hit_dice) return;

    // Extract die size (e.g. '5d8' -> 8)
    const match = this.character.hit_dice.match(/d(\d+)/);
    if (!match) return;
    const dieSize = parseInt(match[1], 10);
    const conBonus = abilityModifier(this.character.stats?.CON || 10);

    const roll = this.dice.roll({ numDice: 1, sides: dieSize, modifier: conBonus });
    // D&D HP gain minimum is 1
    const finalHpGain = Math.max(1, roll.total);

    this.onChoiceChange('hp_method', 'roll');
    this.onChoiceChange('custom_hp_increase', finalHpGain.toString());
  }
}
