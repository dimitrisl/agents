import { ChangeDetectionStrategy, Component, EventEmitter, Input, Output } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import {
  ForgeButtonDirective,
  ForgeInputDirective,
  ForgeSelectDirective,
  ForgeTextareaDirective,
  ForgeToggleComponent,
} from '../../../shared/ui';

@Component({
  selector: 'app-ai-form',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    ForgeButtonDirective,
    ForgeInputDirective,
    ForgeSelectDirective,
    ForgeTextareaDirective,
    ForgeToggleComponent,
  ],
  templateUrl: './ai-form.component.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class AiFormComponent {
  @Input() is2024 = false;
  @Input() raceOptions: string[] = [];
  @Input() classOptions: string[] = [];
  @Input() bgOptions: string[] = [];
  @Input() alignments: string[] = [];
  @Input() subclassOptions: string[] = [];
  @Input() subclassLocked = true;
  @Input() subclassLockHint = 'Subclasses unlock at level 3';
  @Input() loading = false;

  @Input() aiRace = 'AI Choice';
  @Input() aiClass = 'AI Choice';
  @Input() aiBackground = 'AI Choice';
  @Input() aiLevel = 1;
  @Input() aiGender = 'AI Choice';
  @Input() aiSubclass = 'AI Choice';
  @Input() aiConcept = '';
  @Input() aiName = '';
  @Input() aiAlignment = 'AI Choice';
  @Input() aiUseRolled = false;

  @Output() aiRaceChange = new EventEmitter<string>();
  @Output() aiClassChange = new EventEmitter<string>();
  @Output() aiBackgroundChange = new EventEmitter<string>();
  @Output() aiLevelChange = new EventEmitter<number>();
  @Output() aiGenderChange = new EventEmitter<string>();
  @Output() aiSubclassChange = new EventEmitter<string>();
  @Output() aiConceptChange = new EventEmitter<string>();
  @Output() aiNameChange = new EventEmitter<string>();
  @Output() aiAlignmentChange = new EventEmitter<string>();
  @Output() aiUseRolledChange = new EventEmitter<boolean>();

  @Output() updateSubclasses = new EventEmitter<void>();
  @Output() generate = new EventEmitter<void>();
}
