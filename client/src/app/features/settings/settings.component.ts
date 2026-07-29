import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { CharacterStateService } from '../../core/services/character-state.service';
import { RollToastService } from '../../core/services/roll-toast.service';

@Component({
  selector: 'app-settings',
  standalone: true,
  imports: [CommonModule, FormsModule],
  template: `
    <div class="settings-container">
      <div class="phyrexian-card">
        <h2>⚙️ Phyrexian Forge Settings</h2>
        <p class="subtitle">Configure AI model parameters, edition defaults, and system options.</p>

        <div class="form-group">
          <label>Default D&D Edition:</label>
          <select class="phyrexian-select" [ngModel]="charState.dndEdition()" (ngModelChange)="onEditionChange($event)">
            <option value="2014 Edition">2014 Legacy Edition (5e)</option>
            <option value="2024 Revision (5.5e)">2024 Revision (5.5e)</option>
          </select>
        </div>

        <div class="form-group">
          <label>AI Temperature (Creativity: {{ aiTemperature }}):</label>
          <input type="range" min="0.0" max="1.0" step="0.1" [(ngModel)]="aiTemperature" class="range-input" />
        </div>

        <div class="form-group">
          <label>Preferred Gemini Model:</label>
          <select class="phyrexian-select" [(ngModel)]="preferredModel">
            <option value="gemini-2.5-flash">Gemini 2.5 Flash (Fast)</option>
            <option value="gemini-2.5-pro">Gemini 2.5 Pro (Deep Reasoning)</option>
          </select>
        </div>

        <button class="phyrexian-btn" (click)="saveSettings()">💾 Save Preferences</button>
      </div>
    </div>
  `,
  styles: [`
    .settings-container { max-width: 600px; margin: 0 auto; }
    .subtitle { color: var(--text-muted); margin-bottom: 1.5rem; }
    .form-group { margin-bottom: 1.25rem; }
    .form-group label { display: block; margin-bottom: 0.4rem; font-weight: 600; font-size: 0.9rem; }
    .range-input { width: 100%; accent-color: var(--theme-accent); }
  `]
})
export class SettingsComponent {
  aiTemperature = 0.7;
  preferredModel = 'gemini-2.5-flash';

  constructor(
    public charState: CharacterStateService,
    private rollToast: RollToastService
  ) {}

  onEditionChange(newEdition: string) {
    if (newEdition !== this.charState.dndEdition()) {
      this.charState.toggleEdition();
    }
  }

  saveSettings() {
    this.rollToast.showMessage('⚙️ PREFERENCES SAVED', 'Forge settings updated successfully.');
  }
}
