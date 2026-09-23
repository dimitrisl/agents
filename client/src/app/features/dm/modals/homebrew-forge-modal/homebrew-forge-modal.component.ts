import { Component, Input, Output, EventEmitter, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { HomebrewService, HomebrewItem } from '../../../../core/services/homebrew.service';
import { RollToastService } from '../../../../core/services/roll-toast.service';

@Component({
  selector: 'app-homebrew-forge-modal',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './homebrew-forge-modal.component.html',
  styleUrl: './homebrew-forge-modal.component.css'
})
export class HomebrewForgeModalComponent {
  @Input() campaignName: string | null = null;
  @Output() closeModal = new EventEmitter<void>();

  homebrewService = inject(HomebrewService);
  rollToast = inject(RollToastService);

  step = 1;
  selectedType: 'weapon' | 'spell' | 'feat' = 'weapon';

  // AI Form state
  aiPrompt = '';
  isForging = false;

  // Manual Form State
  formData: Partial<HomebrewItem> = {
    name: '',
    description: '',
    damage_dice: '',
    damage_type: '',
    attack_bonus: '+0',
    level: 1,
    school: ''
  };

  nextStep() {
    this.step = 2;
  }

  forgeWithAI() {
    if (!this.aiPrompt || !this.campaignName) return;
    this.isForging = true;
    this.homebrewService.forgeWithAI(this.campaignName, this.aiPrompt, this.selectedType).subscribe({
      next: (result) => {
        // Auto-fill form
        this.formData = { ...this.formData, ...result };
        this.isForging = false;
      },
      error: () => {
        this.isForging = false;
        this.rollToast.showMessage('❌ FORGE FAILED', 'Failed to forge item. Check prompt or try again.');
      }
    });
  }

  save() {
    if (!this.campaignName) return;
    const finalData = { ...this.formData, homebrew_type: this.selectedType };
    this.homebrewService.saveHomebrew(this.campaignName, finalData).subscribe({
      next: () => {
        this.rollToast.showMessage('✅ ITEM SAVED', 'Homebrew item saved successfully.');
        this.closeModal.emit();
      },
      error: () => this.rollToast.showMessage('❌ SAVE FAILED', 'Failed to save homebrew item.')
    });
  }
}
