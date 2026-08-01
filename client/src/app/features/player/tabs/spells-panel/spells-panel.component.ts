import { ChangeDetectionStrategy, Component, EventEmitter, Input, Output } from '@angular/core';
import { CommonModule } from '@angular/common';
import { CharacterSchema } from '../../../../core/models/character.model';
import { ForgeButtonDirective, ForgeSectionComponent } from '../../../../shared/ui';

@Component({
  selector: 'app-spells-panel',
  standalone: true,
  imports: [CommonModule, ForgeButtonDirective, ForgeSectionComponent],
  templateUrl: './spells-panel.component.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class SpellsPanelComponent {
  @Input({ required: true }) char!: CharacterSchema;
  @Input() getSpellSlotUsed!: (lvl: number) => number;
  @Input() getSpellSlotMax!: (lvl: number) => number;

  @Output() useSpellSlot = new EventEmitter<number>();
  @Output() restoreSpellSlot = new EventEmitter<number>();

  readonly spellLevels = [1, 2, 3, 4, 5, 6, 7, 8, 9];
}
