import { ChangeDetectionStrategy, Component, EventEmitter, Input, Output } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { CharacterSchema } from '../../../../core/models/character.model';
import { ForgeSectionComponent, ForgeTextareaDirective } from '../../../../shared/ui';

@Component({
  selector: 'app-roleplay-panel',
  standalone: true,
  imports: [CommonModule, FormsModule, ForgeSectionComponent, ForgeTextareaDirective],
  templateUrl: './roleplay-panel.component.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class RoleplayPanelComponent {
  @Input({ required: true }) char!: CharacterSchema;
  @Input() editMode = false;

  @Output() save = new EventEmitter<void>();
}
