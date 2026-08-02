import { ChangeDetectionStrategy, Component, EventEmitter, Input, Output } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import type { CharacterSchema } from '../../../core/models/character.model';
import { ForgeButtonDirective, ForgeSelectDirective } from '../../../shared/ui';

@Component({
  selector: 'app-player-dashboard-header',
  standalone: true,
  imports: [CommonModule, FormsModule, ForgeButtonDirective, ForgeSelectDirective],
  templateUrl: './player-dashboard-header.component.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class PlayerDashboardHeaderComponent {
  @Input() activeCharacter?: CharacterSchema | null;
  @Input() activeCharacterId?: string | null;
  @Input() characters: CharacterSchema[] = [];
  @Input() editMode = false;
  @Input() portraitUrl = '';

  @Output() selectCharacter = new EventEmitter<string>();
  @Output() newHero = new EventEmitter<void>();
  @Output() editSheet = new EventEmitter<void>();
  @Output() quickEdit = new EventEmitter<void>();
  @Output() joinCampaign = new EventEmitter<void>();

  get levelClassLine(): string {
    const char = this.activeCharacter;
    if (!char) return 'No active hero';
    return `Lvl ${char.char_level} ${char.char_class}`;
  }
}
