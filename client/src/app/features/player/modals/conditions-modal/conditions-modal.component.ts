import { Component, EventEmitter, Input, Output } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ForgeModalComponent } from '../../../../shared/ui/forge-modal/forge-modal.component';
import { ForgeButtonDirective } from '../../../../shared/ui/forge-button/forge-button.directive';
import { ForgeInputDirective } from '../../../../shared/ui/forge-form-field/forge-input.directive';
import { ForgeBadgeComponent } from '../../../../shared/ui/forge-badge/forge-badge.component';

const DND_CONDITIONS = [
  'Blinded', 'Charmed', 'Deafened', 'Frightened', 'Grappled',
  'Incapacitated', 'Invisible', 'Paralyzed', 'Petrified',
  'Poisoned', 'Prone', 'Restrained', 'Stunned', 'Unconscious',
  'Exhaustion'
];

@Component({
  selector: 'app-conditions-modal',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    ForgeModalComponent,
    ForgeButtonDirective,
    ForgeInputDirective,
    ForgeBadgeComponent
  ],
  templateUrl: './conditions-modal.component.html'
})
export class ConditionsModalComponent {
  @Input() open = false;
  @Input() set initialConditions(val: string[] | undefined) {
    this.selectedConditions = new Set(val || []);
  }
  @Input() set initialConcentration(val: string | undefined) {
    this.concentratingOn = val || '';
  }

  @Output() closed = new EventEmitter<void>();
  @Output() save = new EventEmitter<{ conditions: string[], concentratingOn: string }>();

  selectedConditions = new Set<string>();
  concentratingOn = '';

  availableConditions = DND_CONDITIONS;

  toggleCondition(cond: string) {
    if (this.selectedConditions.has(cond)) {
      this.selectedConditions.delete(cond);
    } else {
      this.selectedConditions.add(cond);
    }
  }

  clearAll() {
    this.selectedConditions.clear();
    this.concentratingOn = '';
  }

  saveAndClose() {
    this.save.emit({
      conditions: Array.from(this.selectedConditions),
      concentratingOn: this.concentratingOn.trim()
    });
    this.closed.emit();
  }
}
