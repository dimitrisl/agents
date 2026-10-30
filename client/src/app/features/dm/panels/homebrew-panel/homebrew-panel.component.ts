import { Component, EventEmitter, Input, OnInit, Output, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { HomebrewService, HomebrewItem } from '../../../../core/services/homebrew.service';
import { RollToastService } from '../../../../core/services/roll-toast.service';
import { isReportedGlobally } from '../../../../core/interceptors/error.interceptor';
import { ForgeConfirmService } from '../../../../shared/ui';
import { HomebrewForgeModalComponent } from '../../modals/homebrew-forge-modal/homebrew-forge-modal.component';

@Component({
  selector: 'app-homebrew-panel',
  standalone: true,
  imports: [CommonModule, HomebrewForgeModalComponent],
  templateUrl: './homebrew-panel.component.html',
  styleUrl: './homebrew-panel.component.css'
})
export class HomebrewPanelComponent implements OnInit {
  @Input() campaignName: string | null = null;
  @Output() addMonsterToTracker = new EventEmitter<HomebrewItem>();
  homebrewService = inject(HomebrewService);
  private rollToast = inject(RollToastService);
  private readonly confirmDialog = inject(ForgeConfirmService);

  items$ = this.homebrewService.items$;
  showForgeModal = false;

  ngOnInit() {
    if (this.campaignName) {
      this.homebrewService.loadHomebrew(this.campaignName).subscribe();
    }
  }

  async deleteItem(id: string) {
    if (!this.campaignName) return;
    const confirmed = await this.confirmDialog.ask({
      title: 'Delete homebrew item?',
      message: "It will be removed from this campaign's homebrew. This cannot be undone.",
      confirmLabel: 'Delete item',
      tone: 'danger',
    });
    if (confirmed) {
      this.homebrewService.deleteHomebrew(this.campaignName, id).subscribe({
        error: (err) => {
          if (!isReportedGlobally(err)) {
            this.rollToast.showMessage('⚠️ DELETE FAILED', err?.error?.detail || 'Could not delete the homebrew item.');
          }
        },
      });
    }
  }
}
