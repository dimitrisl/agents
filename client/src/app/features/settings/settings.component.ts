import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { CharacterStateService } from '../../core/services/character-state.service';
import { RollToastService } from '../../core/services/roll-toast.service';
import {
  ForgeButtonDirective,
  ForgePageComponent,
  ForgeSectionComponent,
  ForgeSelectDirective,
} from '../../shared/ui';

@Component({
  selector: 'app-settings',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    ForgeButtonDirective,
    ForgePageComponent,
    ForgeSectionComponent,
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

  onEditionChange(newEdition: string) {
    if (newEdition !== this.charState.dndEdition()) {
      this.charState.toggleEdition();
    }
  }

  saveSettings() {
    this.rollToast.showMessage('⚙️ PREFERENCES SAVED', 'Forge settings updated successfully.');
  }
}
