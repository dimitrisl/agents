import { ChangeDetectionStrategy, Component, EventEmitter, Input, Output } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ForgeButtonDirective, ForgeInputDirective, ForgeModalComponent } from '../../../../shared/ui';

@Component({
  selector: 'app-join-campaign-modal',
  standalone: true,
  imports: [FormsModule, ForgeButtonDirective, ForgeInputDirective, ForgeModalComponent],
  templateUrl: './join-campaign-modal.component.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class JoinCampaignModalComponent {
  @Input() open = false;
  @Input() joinInviteCode = '';

  @Output() openChange = new EventEmitter<boolean>();
  @Output() joinInviteCodeChange = new EventEmitter<string>();
  @Output() joinCampaign = new EventEmitter<void>();
}
