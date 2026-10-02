import { Component, Input, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ForgeButtonDirective } from '../../../../shared/ui';
import { CampaignEntity } from '../../../../core/models/campaign-entity.model';
import { CampaignEntityService } from '../../../../core/services/campaign-entity.service';
import { AssetService } from '../../../../core/services/asset.service';
import { PasteGoModalComponent } from '../../modals/paste-go-modal/paste-go-modal.component';

@Component({
  selector: 'app-entities-panel',
  standalone: true,
  imports: [CommonModule, FormsModule, ForgeButtonDirective, PasteGoModalComponent],
  templateUrl: './entities-panel.component.html',
})
export class EntitiesPanelComponent implements OnInit {
  @Input() campaignName!: string;

  entities: CampaignEntity[] = [];
  selectedEntity: CampaignEntity | null = null;
  isEditing = false;
  isPasteModalOpen = false;

  // Image Upload
  selectedImage: File | null = null;
  isUploadingImage = false;

  // New entity template
  newEntity: CampaignEntity = {
    campaign_name: '',
    name: 'New Entity',
    type: 'lore',
    content: '',
    tags: []
  };

  constructor(private entityService: CampaignEntityService, private assetService: AssetService) {}

  ngOnInit(): void {
    if (this.campaignName) {
      this.loadEntities();
    }
  }

  loadEntities(): void {
    this.entityService.getEntities(this.campaignName).subscribe({
      next: (res) => (this.entities = res),
      error: (err) => console.error('Failed to load entities', err)
    });
  }

  getLocations(): CampaignEntity[] {
    return this.entities.filter(e => e.type === 'location');
  }

  selectEntity(entity: CampaignEntity): void {
    this.selectedEntity = { ...entity };
    this.isEditing = true;
    this.selectedImage = null;
  }

  createNew(): void {
    this.selectedEntity = { ...this.newEntity, campaign_name: this.campaignName };
    this.isEditing = true;
    this.selectedImage = null;
  }

  onImageSelected(event: any): void {
    const file: File = event.target.files[0];
    if (file) {
      this.selectedImage = file;
    }
  }

  uploadImage(): void {
    if (!this.selectedImage || !this.selectedEntity) return;
    this.isUploadingImage = true;
    this.assetService.uploadAsset(this.campaignName, this.selectedImage).subscribe({
      next: (res) => {
        this.selectedEntity!.image_url = res.url;
        this.selectedImage = null;
        this.isUploadingImage = false;
      },
      error: (err) => {
        console.error('Failed to upload image', err);
        this.isUploadingImage = false;
      }
    });
  }

  saveEntity(): void {
    if (!this.selectedEntity) return;

    if (this.selectedEntity.id) {
      this.entityService.updateEntity(this.campaignName, this.selectedEntity.id, this.selectedEntity).subscribe({
        next: (res) => {
          this.loadEntities();
          this.selectedEntity = res;
        }
      });
    } else {
      this.entityService.createEntity(this.campaignName, this.selectedEntity).subscribe({
        next: (res) => {
          this.loadEntities();
          this.selectedEntity = res;
        }
      });
    }
  }

  deleteEntity(id: string | undefined): void {
    if (!id) return;
    this.entityService.deleteEntity(this.campaignName, id).subscribe({
      next: () => {
        this.selectedEntity = null;
        this.isEditing = false;
        this.loadEntities();
      }
    });
  }

  openPasteModal(): void {
    this.isPasteModalOpen = true;
  }

  onEntityExtracted(entity: CampaignEntity): void {
    this.isPasteModalOpen = false;
    this.selectedEntity = entity;
    this.isEditing = true;
  }
}
