import { ChangeDetectionStrategy, Component, EventEmitter, Input, Output } from '@angular/core';
import type { CharacterSchema } from '../../../core/models/character.model';
import { ForgeSwitcherComponent, ForgeSwitcherOption } from '../../../shared/ui';

/** Active-hero picker for the dashboard header: heroes mapped onto <forge-switcher>. */
@Component({
  selector: 'app-hero-switcher',
  standalone: true,
  imports: [ForgeSwitcherComponent],
  template: `
    <forge-switcher
      noun="hero"
      listLabel="Your heroes"
      emptyTitle="No hero selected"
      [options]="options"
      [value]="activeCharacterId"
      (valueChange)="selectCharacter.emit($event)"
    />
  `,
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class HeroSwitcherComponent {
  @Input() characters: CharacterSchema[] = [];
  @Input() activeCharacter?: CharacterSchema | null;
  @Input() activeCharacterId?: string | null;
  /** Portrait of the active hero (the dashboard resolves its fallback art). */
  @Input() portraitUrl = '';

  @Output() selectCharacter = new EventEmitter<string>();

  get options(): ForgeSwitcherOption[] {
    return this.characters.map((char) => ({
      id: char.char_id!,
      title: char.char_name,
      subtitle: `Lvl ${char.char_level} ${char.char_class}`,
      imageUrl: char.char_id === this.activeCharacterId && this.portraitUrl ? this.portraitUrl : this.portraitOf(char),
    }));
  }

  /** A hero's own uploaded/generated portrait; null when they only have the default art. */
  private portraitOf(char: CharacterSchema): string | null {
    const url = char.char_portrait;
    return url && !url.includes('anvil.png') ? url : null;
  }
}
