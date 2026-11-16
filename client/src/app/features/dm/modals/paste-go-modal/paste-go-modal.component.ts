import { Component, EventEmitter, Input, Output } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ForgeButtonDirective, ForgeModalComponent, ForgeTextareaDirective } from '../../../../shared/ui';
import { CampaignEntityService } from '../../../../core/services/campaign-entity.service';
import { CampaignEntity } from '../../../../core/models/campaign-entity.model';

@Component({
  selector: 'app-paste-go-modal',
  standalone: true,
  imports: [CommonModule, FormsModule, ForgeButtonDirective, ForgeModalComponent, ForgeTextareaDirective],
  templateUrl: './paste-go-modal.component.html',
})
export class PasteGoModalComponent {
  @Input() open = false;
  @Input() campaignName!: string;
  @Output() openChange = new EventEmitter<boolean>();
  @Output() entityExtracted = new EventEmitter<CampaignEntity>();

  rawText = '';
  isExtracting = false;
  error = '';

  constructor(private entityService: CampaignEntityService) {}

  extract(): void {
    if (!this.rawText.trim()) return;

    this.isExtracting = true;
    this.error = '';

    this.entityService.extractEntity(this.campaignName, this.rawText).subscribe({
      next: (entity) => {
        this.isExtracting = false;
        this.rawText = '';
        this.entityExtracted.emit(entity);
      },
      error: (err) => {
        console.error('Extraction failed', err);
        this.error = 'Failed to extract entity from text. Please try again or create manually.';
        this.isExtracting = false;
      }
    });
  }

  close(): void {
    this.openChange.emit(false);
    this.rawText = '';
    this.error = '';
  }
}
