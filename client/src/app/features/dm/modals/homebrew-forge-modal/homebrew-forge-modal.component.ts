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
  selectedType: 'weapon' | 'spell' | 'feat' | 'monster' = 'weapon';

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
    school: '',
    size: 'Medium',
    type: 'humanoid',
    alignment: 'unaligned',
    cr: '1',
    ac: 10,
    hp: 10,
    speed: '30 ft.',
    stats: { str: 10, dex: 10, con: 10, int: 10, wis: 10, cha: 10 },
    senses: '',
    languages: '',
    actions_text: '',
    traits_text: ''
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
        if (result.actions && Array.isArray(result.actions)) {
          this.formData['actions_text'] = result.actions
            .map((a: any) => typeof a === 'string' ? a : `${a.name}: ${a.description}`)
            .join('\n');
        }
        if (result.traits && Array.isArray(result.traits)) {
          this.formData['traits_text'] = result.traits
            .map((t: any) => typeof t === 'string' ? t : `${t.name}: ${t.description}`)
            .join('\n');
        }
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
    const finalData: Record<string, any> = { ...this.formData, homebrew_type: this.selectedType };
    if (this.selectedType === 'monster') {
      finalData['ac'] = Number(finalData['ac']) || 10;
      finalData['hp'] = Number(finalData['hp']) || 10;
      if (!finalData['stats']) {
        finalData['stats'] = { str: 10, dex: 10, con: 10, int: 10, wis: 10, cha: 10 };
      }
      if (finalData['actions_text']) {
        finalData['actions'] = finalData['actions_text']
          .split('\n')
          .filter((l: string) => l.trim())
          .map((l: string) => {
            const colonIdx = l.indexOf(':');
            if (colonIdx > 0) {
              return { name: l.substring(0, colonIdx).trim(), description: l.substring(colonIdx + 1).trim() };
            }
            return { name: 'Action', description: l.trim() };
          });
      }
      if (finalData['traits_text']) {
        finalData['traits'] = finalData['traits_text']
          .split('\n')
          .filter((l: string) => l.trim())
          .map((l: string) => {
            const colonIdx = l.indexOf(':');
            if (colonIdx > 0) {
              return { name: l.substring(0, colonIdx).trim(), description: l.substring(colonIdx + 1).trim() };
            }
            return { name: 'Trait', description: l.trim() };
          });
      }
    }
    this.homebrewService.saveHomebrew(this.campaignName, finalData).subscribe({
      next: () => {
        this.rollToast.showMessage('✅ ITEM SAVED', 'Homebrew item saved successfully.');
        this.closeModal.emit();
      },
      error: () => this.rollToast.showMessage('❌ SAVE FAILED', 'Failed to save homebrew item.')
    });
  }
}
