import { ChangeDetectionStrategy, Component, EventEmitter, Input, Output } from '@angular/core';
import { FormsModule } from '@angular/forms';
import {
  ForgeButtonDirective,
  ForgeInputDirective,
  ForgeSelectDirective,
} from '../../../../shared/ui';
import {
  ENCOUNTER_DIFFICULTIES,
  EncounterDifficulty,
  EncounterResponse,
} from '../../../../core/models/dm-tools.model';

@Component({
  selector: 'app-generators-panel',
  standalone: true,
  imports: [
    FormsModule,
    ForgeButtonDirective,
    ForgeInputDirective,
    ForgeSelectDirective,
  ],
  templateUrl: './generators-panel.component.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class GeneratorsPanelComponent {
  /** The roster the encounter will be balanced for. 0 blocks generation. */
  @Input() partySize = 0;
  @Input() avgLevel = 1;
  @Input() difficulty: EncounterDifficulty = 'Medium';
  @Input() location = '';
  @Input() encounterResult: EncounterResponse | null = null;
  @Input() npcConcept = '';
  @Input() npcResult = '';

  @Output() avgLevelChange = new EventEmitter<number>();
  @Output() difficultyChange = new EventEmitter<EncounterDifficulty>();
  @Output() locationChange = new EventEmitter<string>();
  @Output() npcConceptChange = new EventEmitter<string>();
  @Output() generateEncounter = new EventEmitter<void>();
  @Output() addEncounterMonsters = new EventEmitter<void>();
  @Output() generateNpc = new EventEmitter<void>();

  readonly difficulties = ENCOUNTER_DIFFICULTIES;
}
