import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { CharacterStateService } from '../../core/services/character-state.service';
import { RollToastService } from '../../core/services/roll-toast.service';
import {
  ForgeBadgeComponent,
  ForgeButtonDirective,
  ForgeCardComponent,
  ForgePageComponent,
  ForgeSelectDirective,
} from '../../shared/ui';

@Component({
  selector: 'app-settings',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    ForgeBadgeComponent,
    ForgeButtonDirective,
    ForgeCardComponent,
    ForgePageComponent,
    ForgeSelectDirective,
  ],
  templateUrl: './settings.component.html',
  styleUrl: './settings.component.css',
})
export class SettingsComponent {
  aiTemperature = 0.7;
  preferredModel = 'gemini-2.5-flash';

  constructor(
    public charState: CharacterStateService,
    private rollToast: RollToastService
  ) {}

  // --- Configuration summary (presentation only, derived from the form state) ---

  get editionShort(): string {
    return this.charState.dndEdition().includes('2024') ? '2024' : '2014';
  }

  get temperatureLabel(): string {
    if (this.aiTemperature <= 0.3) return 'Precise';
    if (this.aiTemperature <= 0.7) return 'Balanced';
    return 'Creative';
  }

  get preferredModelLabel(): string {
    return this.preferredModel === 'gemini-2.5-pro' ? 'Gemini 2.5 Pro' : 'Gemini 2.5 Flash';
  }

  onEditionChange(newEdition: string) {
    if (newEdition !== this.charState.dndEdition()) {
      this.charState.toggleEdition();
    }
  }

  saveSettings() {
    this.rollToast.showMessage('⚙️ PREFERENCES SAVED', 'Forge settings updated successfully.');
  }
}
