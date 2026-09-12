import { ChangeDetectionStrategy, Component, inject, OnInit, signal } from '@angular/core';
import { Router } from '@angular/router';
import { CommonModule } from '@angular/common';
import { HttpClient } from '@angular/common/http';
import { ForgeAuthShellComponent, ForgeCardComponent, ForgeEmptyStateComponent, ForgeListRowComponent, ForgeBadgeComponent } from '../../shared/ui';
import { environment } from '../../../environments/environment';
import { AuthService } from '../../core/services/auth.service';
import { Campaign } from '../../core/models/campaign.model';
import { JoinCampaignModalComponent } from '../player/modals/join-campaign-modal/join-campaign-modal.component';
import { ForgeButtonDirective } from '../../shared/ui';

@Component({
  selector: 'app-campaign-picker',
  standalone: true,
  imports: [
    CommonModule,
    ForgeAuthShellComponent,
    ForgeCardComponent,
    ForgeEmptyStateComponent,
    ForgeListRowComponent,
    ForgeBadgeComponent,
    JoinCampaignModalComponent,
    ForgeButtonDirective
  ],
  templateUrl: './campaign-picker.component.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class CampaignPickerComponent implements OnInit {
  private http = inject(HttpClient);
  private router = inject(Router);
  private auth = inject(AuthService);

  campaigns = signal<Campaign[]>([]);
  loading = signal(true);
  showJoinModal = signal(false);

  ngOnInit() {
    this.fetchCampaigns();
  }

  fetchCampaigns() {
    this.loading.set(true);
    this.http.get<Campaign[]>(`${environment.apiBaseUrl}/campaigns/`).subscribe({
      next: (camps) => {
        this.campaigns.set(camps);
        this.loading.set(false);
      },
      error: () => {
        this.campaigns.set([]);
        this.loading.set(false);
      }
    });
  }

  onCampaignClick(camp: Campaign) {
    if (camp.role === 'dm') {
      this.router.navigate(['/dm'], { queryParams: { c: camp.campaign_name } });
    } else {
      this.router.navigate(['/player']);
    }
  }

  onCampaignJoined() {
    this.showJoinModal.set(false);
    this.fetchCampaigns();
  }

  logout() {
    this.auth.logout();
  }
}
