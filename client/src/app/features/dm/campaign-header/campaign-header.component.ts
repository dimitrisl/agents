import { ChangeDetectionStrategy, Component, EventEmitter, Input, Output } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import {
  ForgeBadgeComponent,
  ForgeButtonDirective,
  ForgeSelectDirective,
} from '../../../shared/ui';

@Component({
  selector: 'app-campaign-header',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    ForgeBadgeComponent,
    ForgeButtonDirective,
    ForgeSelectDirective,
  ],
  templateUrl: './campaign-header.component.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class CampaignHeaderComponent {
  @Input({ required: true }) campaignName!: string;
  @Input() userCampaigns: Array<{ campaign_name: string }> = [];
  @Input() inviteCode = '';
  /** `2014` / `2024` — the ruleset the DM tools are resolving against. */
  @Input() editionShort = '';

  @Output() campaignNameChange = new EventEmitter<string>();
  @Output() campaignSelected = new EventEmitter<void>();
  @Output() createCampaign = new EventEmitter<void>();
  @Output() generateInvite = new EventEmitter<void>();
  @Output() sendWhisper = new EventEmitter<void>();
}
