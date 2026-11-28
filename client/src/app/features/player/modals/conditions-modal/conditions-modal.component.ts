import { ChangeDetectionStrategy, Component, EventEmitter, Input, OnChanges, Output, SimpleChanges } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import {
  ConditionCountermeasure,
  describeConditionImpact,
  detectConditionWarnings,
  getConditionCountermeasures,
  RuleSheetLike,
} from '../../../../core/rules';
import { ForgeModalComponent } from '../../../../shared/ui/forge-modal/forge-modal.component';
import { ForgeButtonDirective } from '../../../../shared/ui/forge-button/forge-button.directive';
import { ForgeInputDirective } from '../../../../shared/ui/forge-form-field/forge-input.directive';
import { ForgeBadgeComponent } from '../../../../shared/ui/forge-badge/forge-badge.component';

const DND_CONDITIONS = [
  'Blinded', 'Charmed', 'Deafened', 'Frightened', 'Grappled',
  'Incapacitated', 'Invisible', 'Paralyzed', 'Petrified',
  'Poisoned', 'Prone', 'Restrained', 'Stunned', 'Unconscious',
  'Exhaustion',
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
    ForgeBadgeComponent,
  ],
  templateUrl: './conditions-modal.component.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ConditionsModalComponent implements OnChanges {
  @Input() open = false;
  @Input() char: RuleSheetLike | null = null;
  @Input() set initialConditions(val: string[] | undefined) {
    this._latestInitialConditions = [...(val || [])];
    if (!this.open) {
      this.selectedConditions = new Set(this._latestInitialConditions);
    }
  }
  @Input() set initialConcentration(val: string | undefined) {
    this._latestInitialConcentration = val || '';
    if (!this.open) {
      this.concentratingOn = this._latestInitialConcentration;
    }
  }

  @Output() closed = new EventEmitter<void>();
  @Output() save = new EventEmitter<{ conditions: string[]; concentratingOn: string }>();

  private _latestInitialConditions: string[] = [];
  private _latestInitialConcentration = '';
  selectedConditions = new Set<string>();
  concentratingOn = '';

  ngOnChanges(changes: SimpleChanges): void {
    if (changes['open'] && this.open) {
      this.selectedConditions = new Set(this._latestInitialConditions);
      this.concentratingOn = this._latestInitialConcentration;
    }
  }

  readonly availableConditions = DND_CONDITIONS;

  get countermeasures(): ConditionCountermeasure[] {
    return getConditionCountermeasures(this.char);
  }

  get activeWarnings(): ConditionCountermeasure[] {
    return detectConditionWarnings(this.char, this.selectedConditions);
  }

  get activeImpactSummaries(): Array<{ condition: string; tags: string[] }> {
    const out: Array<{ condition: string; tags: string[] }> = [];
    for (const cond of this.selectedConditions) {
      const tags = describeConditionImpact(cond, this.char);
      if (tags.length > 0) {
        out.push({ condition: cond, tags });
      }
    }
    return out;
  }

  countermeasuresFor(cond: string): ConditionCountermeasure[] {
    const low = cond.trim().toLowerCase();
    return this.countermeasures.filter((c) => c.condition.toLowerCase() === low);
  }

  countermeasureTooltip(cond: string): string {
    const list = this.countermeasuresFor(cond);
    return list.map((c) => `${c.source}: ${c.detail}`).join(' · ');
  }

  toggleCondition(cond: string) {
    const next = new Set(this.selectedConditions);
    if (next.has(cond)) {
      next.delete(cond);
    } else {
      next.add(cond);
    }
    this.selectedConditions = next;
  }

  clearAll() {
    this.selectedConditions = new Set<string>();
    this.concentratingOn = '';
  }

  saveAndClose() {
    this.save.emit({
      conditions: Array.from(this.selectedConditions),
      concentratingOn: this.concentratingOn.trim(),
    });
    this.closed.emit();
  }
}
