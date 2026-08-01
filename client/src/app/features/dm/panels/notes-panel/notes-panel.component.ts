import { ChangeDetectionStrategy, Component, EventEmitter, Input, Output } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ForgeSectionComponent, ForgeTextareaDirective } from '../../../../shared/ui';

@Component({
  selector: 'app-notes-panel',
  standalone: true,
  imports: [FormsModule, ForgeSectionComponent, ForgeTextareaDirective],
  templateUrl: './notes-panel.component.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class NotesPanelComponent {
  @Input() campaignNotes = '';

  @Output() campaignNotesChange = new EventEmitter<string>();
  @Output() saveNotes = new EventEmitter<void>();
}
