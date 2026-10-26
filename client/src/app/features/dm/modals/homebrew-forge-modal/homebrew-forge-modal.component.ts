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
        this.isForging = false;
        if (!result || typeof result !== 'object') {
          this.rollToast.showMessage('❌ FORGE FAILED', 'AI returned an empty or invalid response. Please try again.');
          return;
        }
        // Auto-fill form
        this.formData = { ...this.formData, ...result };
        if (result.actions && Array.isArray(result.actions)) {
          this.formData['actions_text'] = result.actions
            .map((a: any) => typeof a === 'string' ? a : `${a.name}: ${a.description ?? a.desc ?? ''}`)
            .join('\n');
        }
        if (result.traits && Array.isArray(result.traits)) {
          this.formData['traits_text'] = result.traits
            .map((t: any) => typeof t === 'string' ? t : `${t.name}: ${t.description ?? t.desc ?? ''}`)
            .join('\n');
        }
      },
      error: () => {
        this.isForging = false;
        this.rollToast.showMessage('❌ FORGE FAILED', 'Failed to forge item. Check prompt or try again.');
      }
    });
  }

  private parseMonsterEntries(rawText: string | undefined, defaultLabel: string): Array<{ name: string; description: string }> {
    if (!rawText || !rawText.trim()) {
      return [];
    }
    return rawText
      .split('\n')
      .filter((l: string) => l.trim())
      .map((l: string) => {
        const colonIdx = l.indexOf(':');
        if (colonIdx > 0) {
          return { name: l.substring(0, colonIdx).trim(), description: l.substring(colonIdx + 1).trim() };
        }
        return { name: defaultLabel, description: l.trim() };
      });
  }

  save() {
    if (!this.campaignName) return;
    const finalData: Record<string, any> = {
      name: this.formData.name || '',
      description: this.formData['description'] || '',
      homebrew_type: this.selectedType
    };

    if (this.selectedType === 'weapon') {
      finalData['damage_dice'] = this.formData['damage_dice'] || '';
      finalData['attack_bonus'] = this.formData['attack_bonus'] || '+0';
      if (this.formData['damage_type']) finalData['damage_type'] = this.formData['damage_type'];
      if (this.formData['damage_bonus']) finalData['damage_bonus'] = this.formData['damage_bonus'];
      if (this.formData['range']) finalData['range'] = this.formData['range'];
      if (this.formData['properties']) finalData['properties'] = this.formData['properties'];
      if (this.formData['magic_bonus'] !== undefined) finalData['magic_bonus'] = this.formData['magic_bonus'];
    } else if (this.selectedType === 'spell') {
      finalData['level'] = Number(this.formData['level'] ?? 1);
      finalData['school'] = this.formData['school'] || 'Evocation';
      if (this.formData['casting_time']) finalData['casting_time'] = this.formData['casting_time'];
      if (this.formData['range']) finalData['range'] = this.formData['range'];
      if (this.formData['components']) finalData['components'] = this.formData['components'];
      if (this.formData['duration']) finalData['duration'] = this.formData['duration'];
    } else if (this.selectedType === 'feat') {
      if (this.formData['prerequisite']) finalData['prerequisite'] = this.formData['prerequisite'];
    } else if (this.selectedType === 'monster') {
      finalData['size'] = this.formData['size'] || 'Medium';
      finalData['type'] = this.formData['type'] || 'humanoid';
      finalData['alignment'] = this.formData['alignment'] || 'unaligned';
      finalData['cr'] = this.formData['cr'] ?? '1';
      finalData['ac'] = Number(this.formData['ac']) || 10;
      finalData['hp'] = Number(this.formData['hp']) || 10;
      finalData['speed'] = this.formData['speed'] || '30 ft.';
      finalData['stats'] = this.formData['stats'] || { str: 10, dex: 10, con: 10, int: 10, wis: 10, cha: 10 };
      finalData['senses'] = this.formData['senses'] || '';
      finalData['languages'] = this.formData['languages'] || '';
      finalData['actions'] = this.parseMonsterEntries(this.formData['actions_text'], 'Action');
      finalData['traits'] = this.parseMonsterEntries(this.formData['traits_text'], 'Trait');
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
