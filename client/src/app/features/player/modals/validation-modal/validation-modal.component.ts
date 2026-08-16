import { ChangeDetectionStrategy, Component, EventEmitter, Input, Output } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ForgeButtonDirective, ForgeModalComponent } from '../../../../shared/ui';

@Component({
  selector: 'app-validation-modal',
  standalone: true,
  imports: [CommonModule, ForgeButtonDirective, ForgeModalComponent],
  templateUrl: './validation-modal.component.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ValidationModalComponent {
  @Input() open = false;
  @Input() characterName?: string;
  @Input() isValidating = false;
  @Input() validationResult: any = null;
  @Input() isAutoFixing = false;

  @Output() openChange = new EventEmitter<boolean>();
  @Output() applyAutoFix = new EventEmitter<void>();
}
