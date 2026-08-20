import { ChangeDetectionStrategy, Component, EventEmitter, Input, Output } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import {
  ForgeButtonDirective,
  ForgeInputDirective,
} from '../../../../shared/ui';
import { EncounterResponse } from '../../../../core/models/dm-tools.model';

@Component({
  selector: 'app-generators-panel',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    ForgeButtonDirective,
    ForgeInputDirective,
  ],
  templateUrl: './generators-panel.component.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class GeneratorsPanelComponent {
  @Input() avgLevel = 5;
  @Input() location = '';
  @Input() encounterResult: EncounterResponse | null = null;
  @Input() npcConcept = '';
  @Input() npcResult = '';

  @Output() avgLevelChange = new EventEmitter<number>();
  @Output() locationChange = new EventEmitter<string>();
  @Output() npcConceptChange = new EventEmitter<string>();
  @Output() generateEncounter = new EventEmitter<void>();
  @Output() addEncounterMonsters = new EventEmitter<void>();
  @Output() generateNpc = new EventEmitter<void>();
}
