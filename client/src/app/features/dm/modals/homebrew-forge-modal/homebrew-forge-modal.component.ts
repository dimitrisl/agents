import { Component, Input, Output, EventEmitter, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { HomebrewService } from '../../../../core/services/homebrew.service';

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

  step = 1;
  selectedType: 'weapon' | 'spell' | 'feat' = 'weapon';

  // AI Form state
  aiPrompt = '';
  isForging = false;

  // Manual Form State
  formData: any = {
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
        alert('Failed to forge item. Check prompt or try again.');
      }
    });
  }

  save() {
    if (!this.campaignName) return;
    const finalData = { ...this.formData, homebrew_type: this.selectedType };
    this.homebrewService.saveHomebrew(this.campaignName, finalData).subscribe({
      next: () => this.closeModal.emit(),
      error: () => alert('Failed to save homebrew item.')
    });
  }
}
