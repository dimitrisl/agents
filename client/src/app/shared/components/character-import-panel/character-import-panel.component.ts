import { ChangeDetectionStrategy, Component, EventEmitter, Input, Output } from '@angular/core';
import { FormsModule } from '@angular/forms';
import type { ImportSource } from '../../../core/services/character-import.service';
import {
  ForgeButtonDirective,
  ForgeInputDirective,
  ForgeTab,
  ForgeTabsComponent,
} from '../../ui';

/**
 * The three ways to bring in an existing hero (5e PDF, D&D Beyond, Foundry VTT).
 * Presentational: the host runs the import and passes back busy / error / warnings.
 * Used by the Player Dashboard's import dialog and the Forge's Import tab.
 */
@Component({
  selector: 'app-character-import-panel',
  standalone: true,
  imports: [FormsModule, ForgeButtonDirective, ForgeInputDirective, ForgeTabsComponent],
  templateUrl: './character-import-panel.component.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
  host: { class: 'block' },
})
export class CharacterImportPanelComponent {
  @Input() busy = false;
  @Input() error: string | null = null;
  @Input() warnings: string[] = [];
  /** Label of the button shown under warnings (e.g. "Open hero" or "Dismiss"). */
  @Input() warningsActionLabel = 'Dismiss';

  @Output() pdfSelected = new EventEmitter<File>();
  @Output() dndBeyondSubmitted = new EventEmitter<string>();
  @Output() foundrySelected = new EventEmitter<File>();
  @Output() warningsAcknowledged = new EventEmitter<void>();

  source: ImportSource = 'pdf';
  dndBeyondUrl = '';

  readonly tabs: ForgeTab[] = [
    { id: 'pdf', label: '📄 5e PDF Sheet' },
    { id: 'dndbeyond', label: '⚡ D&D Beyond' },
    { id: 'foundry', label: '🎲 Foundry VTT' },
  ];

  setSource(id: string): void {
    this.source = id as ImportSource;
  }

  onFile(event: Event, kind: 'pdf' | 'foundry'): void {
    const input = event.target as HTMLInputElement;
    const file = input.files?.[0];
    // Reset so picking the same file again still fires a change.
    input.value = '';
    if (!file) return;
    if (kind === 'pdf') this.pdfSelected.emit(file);
    else this.foundrySelected.emit(file);
  }

  submitDndBeyond(): void {
    const url = this.dndBeyondUrl.trim();
    if (!url || this.busy) return;
    this.dndBeyondSubmitted.emit(url);
  }
}
