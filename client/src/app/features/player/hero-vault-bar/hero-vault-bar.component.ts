import { ChangeDetectionStrategy, Component, EventEmitter, Input, Output } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { CharacterSchema } from '../../../core/models/character.model';
import {
  ForgeButtonDirective,
  ForgeSelectDirective,
  ForgeToolbarComponent,
} from '../../../shared/ui';

@Component({
  selector: 'app-hero-vault-bar',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    ForgeButtonDirective,
    ForgeSelectDirective,
    ForgeToolbarComponent,
  ],
  templateUrl: './hero-vault-bar.component.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class HeroVaultBarComponent {
  @Input() edition = '';
  @Input() activeCharacterId?: string | null;
  @Input() characters: CharacterSchema[] = [];
  @Input() editMode = false;

  @Output() selectCharacter = new EventEmitter<string>();
  @Output() newHero = new EventEmitter<void>();
  @Output() editSheet = new EventEmitter<void>();
  @Output() quickEdit = new EventEmitter<void>();
  @Output() joinCampaign = new EventEmitter<void>();
}
