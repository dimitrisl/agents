import { ChangeDetectionStrategy, Component, EventEmitter, Input, Output } from '@angular/core';
import { CommonModule } from '@angular/common';
import {
  ForgeBadgeComponent,
  ForgeButtonDirective,
  ForgeSwitcherComponent,
  ForgeSwitcherOption,
} from '../../../shared/ui';

@Component({
  selector: 'app-campaign-header',
  standalone: true,
  imports: [
    CommonModule,
    ForgeBadgeComponent,
    ForgeButtonDirective,
    ForgeSwitcherComponent,
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
  @Output() deleteCampaign = new EventEmitter<void>();

  get campaignOptions(): ForgeSwitcherOption[] {
    const names = this.userCampaigns.length
      ? this.userCampaigns.map((campaign) => campaign.campaign_name)
      : [this.campaignName];
    return names.map((name) => ({
      id: name,
      title: name,
      badge: '🏰',
      // Only the open campaign's code is known here.
      subtitle:
        name === this.campaignName
          ? this.inviteCode
            ? `Invite code · ${this.inviteCode}`
            : 'No invite code yet'
          : undefined,
    }));
  }

  /** Same order as the old <select>: update the name, then tell the parent to load it. */
  onCampaignPicked(name: string): void {
    this.campaignNameChange.emit(name);
    this.campaignSelected.emit();
  }
}
