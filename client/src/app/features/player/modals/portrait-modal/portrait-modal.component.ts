import { ChangeDetectionStrategy, Component, EventEmitter, Input, Output } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ForgeButtonDirective, ForgeModalComponent, ForgeTextareaDirective } from '../../../../shared/ui';

@Component({
  selector: 'app-portrait-modal',
  standalone: true,
  imports: [FormsModule, ForgeButtonDirective, ForgeModalComponent, ForgeTextareaDirective],
  templateUrl: './portrait-modal.component.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class PortraitModalComponent {
  @Input() open = false;
  @Input() portraitPrompt = '';

  @Output() openChange = new EventEmitter<boolean>();
  @Output() portraitPromptChange = new EventEmitter<string>();
  @Output() generateAiPortrait = new EventEmitter<void>();
}
