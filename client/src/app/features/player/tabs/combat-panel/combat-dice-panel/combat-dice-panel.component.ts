import { ChangeDetectionStrategy, Component, EventEmitter, Input, Output } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RollMode } from '../../../../../core/services/dice.service';
import { ClassCombatAction } from '../../../../../core/services/class-combat.service';
import { CombatActionKind } from '../../../../../core/data/class-combat.data';
import { ForgeBadgeComponent, ForgeButtonDirective } from '../../../../../shared/ui';
import { DiceRollerComponent } from '../../../../../shared/components/dice-roller/dice-roller.component';

type BadgeTone = 'accent' | 'muted' | 'gold' | 'danger' | 'success';

const KIND_LABEL: Record<CombatActionKind, string> = {
  rider: 'Rider',
  attack: 'Attack',
  heal: 'Healing',
  defense: 'Defense',
  utility: 'Utility',
};

const KIND_TONE: Record<CombatActionKind, BadgeTone> = {
  rider: 'gold',
  attack: 'accent',
  heal: 'success',
  defense: 'accent',
  utility: 'muted',
};

/**
 * The dice half of the combat tab: what this character rolls because of their
 * class and level, and a plain tray for everything else.
 */
@Component({
  selector: 'app-combat-dice-panel',
  standalone: true,
  imports: [CommonModule, ForgeBadgeComponent, ForgeButtonDirective, DiceRollerComponent],
  templateUrl: './combat-dice-panel.component.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
  host: {
    class: 'block',
  },
})
export class CombatDicePanelComponent {
  @Input() actions: ClassCombatAction[] = [];
  @Input() charClass = '';
  @Input() charLevel = 1;
  @Input() subclass?: string;
  @Input() rollMode: RollMode = 'normal';

  @Output() rollAction = new EventEmitter<ClassCombatAction>();

  get rollable(): ClassCombatAction[] {
    return this.actions.filter((action) => action.rollable);
  }

  /** Features whose number matters but which are not a roll of their own. */
  get reference(): ClassCombatAction[] {
    return this.actions.filter((action) => !action.rollable);
  }

  kindLabel(kind: CombatActionKind): string {
    return KIND_LABEL[kind];
  }

  kindTone(kind: CombatActionKind): BadgeTone {
    return KIND_TONE[kind];
  }
}
