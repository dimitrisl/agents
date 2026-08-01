import { ChangeDetectionStrategy, Component, EventEmitter, Input, Output } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { CharacterSchema, EquipmentItem, Weapon } from '../../../../core/models/character.model';
import {
  ForgeBadgeComponent,
  ForgeButtonDirective,
  ForgeInputDirective,
  ForgeSectionComponent,
} from '../../../../shared/ui';
import { DiceRollerComponent } from '../../../../shared/components/dice-roller/dice-roller.component';

@Component({
  selector: 'app-combat-panel',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    ForgeBadgeComponent,
    ForgeButtonDirective,
    ForgeInputDirective,
    ForgeSectionComponent,
    DiceRollerComponent,
  ],
  templateUrl: './combat-panel.component.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class CombatPanelComponent {
  @Input({ required: true }) char!: CharacterSchema;
  @Input() editMode = false;

  @Output() addWeapon = new EventEmitter<void>();
  @Output() deleteWeapon = new EventEmitter<number>();
  @Output() rollWeaponAttack = new EventEmitter<Weapon>();
  @Output() toggleEquipped = new EventEmitter<EquipmentItem>();
  @Output() addEquipment = new EventEmitter<void>();
  @Output() deleteEquipment = new EventEmitter<number>();
  @Output() save = new EventEmitter<void>();
}
