import { ChangeDetectionStrategy, Component, EventEmitter, Input, Output } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { CharacterSchema } from '../../../../core/models/character.model';
import { ForgeButtonDirective, ForgeInputDirective, ForgeModalComponent, ForgeTextareaDirective } from '../../../../shared/ui';

@Component({
  selector: 'app-edit-sheet-modal',
  standalone: true,
  imports: [CommonModule, FormsModule, ForgeButtonDirective, ForgeInputDirective, ForgeModalComponent, ForgeTextareaDirective],
  templateUrl: './edit-sheet-modal.component.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class EditSheetModalComponent {
  @Input() open = false;
  @Input() editChar: CharacterSchema | null = null;

  @Output() openChange = new EventEmitter<boolean>();
  @Output() saveEditModal = new EventEmitter<void>();

  get canEditSubclass(): boolean {
    return Number(this.editChar?.char_level || 1) >= 3;
  }
}
