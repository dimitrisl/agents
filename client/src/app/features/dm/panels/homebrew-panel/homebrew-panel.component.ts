import { Component, Input, OnInit, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { HomebrewService, HomebrewItem } from '../../../../core/services/homebrew.service';
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
  homebrewService = inject(HomebrewService);

  items$ = this.homebrewService.items$;
  showForgeModal = false;

  ngOnInit() {
    if (this.campaignName) {
      this.homebrewService.loadHomebrew(this.campaignName).subscribe();
    }
  }

  deleteItem(id: string) {
    if (!this.campaignName) return;
    if (confirm('Are you sure you want to delete this homebrew item?')) {
      this.homebrewService.deleteHomebrew(this.campaignName, id).subscribe();
    }
  }
}
