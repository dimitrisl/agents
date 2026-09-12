import { ChangeDetectionStrategy, Component, EventEmitter, Input, OnInit, Output, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { HttpClient } from '@angular/common/http';
import { environment } from '../../../../../environments/environment';
import { CharacterStateService } from '../../../../core/services/character-state.service';
import { DiceService } from '../../../../core/services/dice.service';
import { RollToastService } from '../../../../core/services/roll-toast.service';
import { ForgeBadgeComponent, ForgeButtonDirective, ForgeModalComponent } from '../../../../shared/ui';

@Component({
  selector: 'app-spell-detail-modal',
  standalone: true,
  imports: [CommonModule, ForgeModalComponent, ForgeButtonDirective, ForgeBadgeComponent],
  templateUrl: './spell-detail-modal.component.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class SpellDetailModalComponent implements OnInit {
  @Input({ required: true }) spellName!: string;
  @Input() isPrepared = false;

  @Output() close = new EventEmitter<void>();

  isLoading = signal(true);
  error = signal<string | null>(null);
  spellData = signal<any | null>(null);

  damageDiceFound = signal<string[]>([]);
  hasSpellAttack = signal(false);

  constructor(
    private http: HttpClient,
    private charState: CharacterStateService,
    private dice: DiceService,
    private toast: RollToastService
  ) {}

  ngOnInit(): void {
    this.fetchSpellDetails();
  }

  closeModal(): void {
    this.close.emit();
  }

  private fetchSpellDetails(): void {
    this.isLoading.set(true);
    this.error.set(null);
    const edition = this.charState.dndEdition();

    // We use exact search or just grab the first result
    this.http.get<any[]>(`${environment.apiBaseUrl}/rules/spells`, {
      params: { search: this.spellName, edition }
    }).subscribe({
      next: (results) => {
        if (results && results.length > 0) {
          // Find exact match if possible, otherwise first
          const exact = results.find(s => s.name.toLowerCase() === this.spellName.toLowerCase());
          const data = exact || results[0];
          this.spellData.set(data);
          this.parseRolls(data.description || '');
        } else {
          this.error.set('Spell details not found in the rules database.');
        }
        this.isLoading.set(false);
      },
      error: () => {
        this.error.set('Failed to connect to the rules API.');
        this.isLoading.set(false);
      }
    });
  }

  private parseRolls(description: string): void {
    const text = description.toLowerCase();

    // Find spell attacks
    if (text.includes('spell attack')) {
      this.hasSpellAttack.set(true);
    }

    // Find damage/healing dice like 8d6, 1d4, 2d8
    const regex = /\b(\d+)d(\d+)\b/g;
    const found = new Set<string>();

    let match;
    while ((match = regex.exec(text)) !== null) {
      found.add(match[0]);
    }

    // Convert set to array and set signal
    this.damageDiceFound.set(Array.from(found));
  }

  rollAttack(): void {
    const char = this.charState.activeCharacter();
    if (!char) return;

    const modifierStr = char.spell_attack_bonus || '+0';
    const modifier = parseInt(modifierStr.replace('+', ''), 10) || 0;

    const result = this.dice.rollD20(modifier, 'normal');

    this.toast.showRoll({
      title: `${this.spellName} Attack`,
      ...result
    });
  }

  rollDice(notation: string): void {
    const char = this.charState.activeCharacter();
    if (!char) return;

    const result = this.dice.rollNotation(notation, 'normal');

    this.toast.showRoll({
      title: `${this.spellName} (${notation})`,
      ...result
    });
  }
}
