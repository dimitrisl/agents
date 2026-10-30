import { ChangeDetectionStrategy, Component, EventEmitter, Input, Output } from '@angular/core';
import { CommonModule } from '@angular/common';
import type { CharacterSchema } from '../../../core/models/character.model';
import { ForgeButtonDirective } from '../../../shared/ui';
import { HeroSwitcherComponent } from '../hero-switcher/hero-switcher.component';

@Component({
  selector: 'app-player-dashboard-header',
  standalone: true,
  imports: [CommonModule, ForgeButtonDirective, HeroSwitcherComponent],
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
  @Output() deleteHero = new EventEmitter<void>();
}
