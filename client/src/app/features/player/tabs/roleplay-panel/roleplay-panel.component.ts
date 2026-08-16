import { ChangeDetectionStrategy, Component, EventEmitter, Input, Output } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { CharacterSchema } from '../../../../core/models/character.model';
import { ForgeBadgeComponent, ForgeButtonDirective, ForgeTextareaDirective } from '../../../../shared/ui';

type RoleplayTraitKey = 'personality_traits' | 'ideals' | 'bonds' | 'flaws';

interface RoleplayTraitField {
  key: RoleplayTraitKey;
  label: string;
}

// Longer backstories get clamped so the tab stays scannable mid-session.
const BACKSTORY_CLAMP_THRESHOLD = 420;

@Component({
  selector: 'app-roleplay-panel',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    ForgeBadgeComponent,
    ForgeButtonDirective,
    ForgeTextareaDirective,
  ],
  templateUrl: './roleplay-panel.component.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
  host: {
    class: 'block',
  },
})
export class RoleplayPanelComponent {
  @Input({ required: true }) char!: CharacterSchema;
  @Input() editMode = false;

  @Output() save = new EventEmitter<void>();

  readonly traitFields: RoleplayTraitField[] = [
    { key: 'personality_traits', label: 'Personality Traits' },
    { key: 'ideals', label: 'Ideals' },
    { key: 'bonds', label: 'Bonds' },
    { key: 'flaws', label: 'Flaws' },
  ];

  backstoryExpanded = false;

  get languages(): string[] {
    return this.char.languages ?? [];
  }

  get toolProficiencies(): string[] {
    return this.char.tool_proficiencies ?? [];
  }

  get hasProficiencies(): boolean {
    return this.languages.length > 0 || this.toolProficiencies.length > 0;
  }

  get isBackstoryClampable(): boolean {
    return (this.char.backstory?.length ?? 0) > BACKSTORY_CLAMP_THRESHOLD;
  }

  toggleBackstory(): void {
    this.backstoryExpanded = !this.backstoryExpanded;
  }
}
