import { ChangeDetectionStrategy, Component, EventEmitter, Input, Output } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import {
  ForgeButtonDirective,
  ForgeTextareaDirective,
} from '../../../../shared/ui';

@Component({
  selector: 'app-prep-panel',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    ForgeButtonDirective,
    ForgeTextareaDirective,
  ],
  templateUrl: './prep-panel.component.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class PrepPanelComponent {
  @Input() prepNotes = '';
  @Input() prepResult = '';

  @Output() prepNotesChange = new EventEmitter<string>();
  @Output() generatePrep = new EventEmitter<void>();
}
