import { ChangeDetectionStrategy, Component, EventEmitter, Input, Output } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { CharacterSchema } from '../../../core/models/character.model';
import {
  ForgeBadgeComponent,
  ForgeButtonDirective,
  ForgeCardComponent,
  ForgeInputDirective,
} from '../../../shared/ui';

@Component({
  selector: 'app-vitals-header',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    ForgeBadgeComponent,
    ForgeButtonDirective,
    ForgeCardComponent,
    ForgeInputDirective,
  ],
  templateUrl: './vitals-header.component.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class VitalsHeaderComponent {
  @Input({ required: true }) char!: CharacterSchema;
  @Input() editMode = false;
  @Input() edition = '';
  @Input() portraitUrl = '';
  @Input() availableHitDice = 0;
  @Input() classHitDieSize = 8;
  @Input() passivePerception = 10;

  @Output() portrait = new EventEmitter<void>();
  @Output() hpDown = new EventEmitter<void>();
  @Output() hpUp = new EventEmitter<void>();
}
