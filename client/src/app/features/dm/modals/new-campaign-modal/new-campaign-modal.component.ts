import { ChangeDetectionStrategy, Component, EventEmitter, Input, Output } from '@angular/core';
import { FormsModule } from '@angular/forms';
import {
  ForgeButtonDirective,
  ForgeInputDirective,
  ForgeModalComponent,
  ForgeTextareaDirective,
} from '../../../../shared/ui';

@Component({
  selector: 'app-new-campaign-modal',
  standalone: true,
  imports: [
    FormsModule,
    ForgeButtonDirective,
    ForgeInputDirective,
    ForgeModalComponent,
    ForgeTextareaDirective,
  ],
  templateUrl: './new-campaign-modal.component.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class NewCampaignModalComponent {
  @Input() open = false;
  @Input() newCampaignTitle = '';
  @Input() newCampaignNotes = '';

  @Output() openChange = new EventEmitter<boolean>();
  @Output() closed = new EventEmitter<void>();
  @Output() newCampaignTitleChange = new EventEmitter<string>();
  @Output() newCampaignNotesChange = new EventEmitter<string>();
  @Output() createCampaign = new EventEmitter<void>();
}
