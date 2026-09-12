import { ChangeDetectionStrategy, Component, EventEmitter, Input, Output } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import {
  ForgeBadgeComponent,
  ForgeButtonDirective,
  ForgeEmptyStateComponent,
  ForgeInputDirective,
  ForgeModalComponent,
} from '../../../../shared/ui';
import type {
  CombatantCondition,
  InitiativeCombatant,
} from '../../../../core/models/initiative.model';

/** The three dots the tracker draws for each half of a death-save tally. */
const DEATH_SAVE_SLOTS = [1, 2, 3];

@Component({
  selector: 'app-initiative-panel',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    ForgeBadgeComponent,
    ForgeButtonDirective,
    ForgeEmptyStateComponent,
    ForgeInputDirective,
    ForgeModalComponent,
  ],
  templateUrl: './initiative-panel.component.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class InitiativePanelComponent {
  @Input() combatants: InitiativeCombatant[] = [];
  @Input() activeCombatantId: string | null = null;
  @Input() round = 0;
  @Input() availableConditions: string[] = [];
  @Input() newCombatantName = '';
  @Input() newCombatantInit = 10;
  @Input() newCombatantHp = 20;

  @Output() newCombatantNameChange = new EventEmitter<string>();
  @Output() newCombatantInitChange = new EventEmitter<number>();
  @Output() newCombatantHpChange = new EventEmitter<number>();
  @Output() importParty = new EventEmitter<void>();
  @Output() rollAll = new EventEmitter<void>();
  @Output() advanceTurn = new EventEmitter<void>();
  @Output() rewindTurn = new EventEmitter<void>();
  @Output() endCombat = new EventEmitter<void>();
  @Output() addCombatant = new EventEmitter<void>();
  @Output() openStatblock = new EventEmitter<InitiativeCombatant>();
  @Output() removeCombatant = new EventEmitter<number>();
  @Output() hpChange = new EventEmitter<{ combatant: InitiativeCombatant; hp: number }>();
  @Output() applyCondition = new EventEmitter<{
    combatant: InitiativeCombatant;
    condition: string;
    rounds: number;
  }>();
  @Output() removeCondition = new EventEmitter<{
    combatant: InitiativeCombatant;
    condition: string;
  }>();
  @Output() setDeathSave = new EventEmitter<{
    combatant: InitiativeCombatant;
    kind: 'successes' | 'failures';
    value: number;
  }>();

  readonly deathSaveSlots = DEATH_SAVE_SLOTS;

  /** Local to the panel: a destructive action asks before it fires. */
  showEndCombatConfirm = false;

  /** Which combatant has its condition palette open, and the duration to apply. */
  private openConditionsFor: string | null = null;
  conditionRounds = 1;

  get roundLabel(): string {
    return this.round > 0 ? `Round ${this.round}` : 'Not started';
  }

  get hasStarted(): boolean {
    return this.round > 0;
  }

  get currentTurnName(): string {
    return this.combatants.find((c) => c.id === this.activeCombatantId)?.name || '—';
  }

  trackCombatant(_index: number, combatant: InitiativeCombatant): string {
    return combatant.id || combatant.name;
  }

  trackCondition(_index: number, condition: CombatantCondition): string {
    return condition.name;
  }

  /**
   * A lapsed condition is filtered out of the view, not deleted, so stepping
   * the round back with Previous Turn brings it honestly back.
   */
  activeConditions(combatant: InitiativeCombatant): CombatantCondition[] {
    return combatant.conditions.filter(
      (condition) => condition.expiresAtRound === null || condition.expiresAtRound > this.round
    );
  }

  hasCondition(combatant: InitiativeCombatant, condition: string): boolean {
    return this.activeConditions(combatant).some((active) => active.name === condition);
  }

  /** Rounds left, counted from the round the condition is anchored to expire on. */
  conditionRemaining(condition: CombatantCondition): number | null {
    if (condition.expiresAtRound === null) return null;
    return Math.max(0, condition.expiresAtRound - Math.max(1, this.round));
  }

  conditionLabel(condition: CombatantCondition): string {
    const remaining = this.conditionRemaining(condition);
    return remaining === null ? '∞' : `${remaining}`;
  }

  onConditionToggle(combatant: InitiativeCombatant, condition: string): void {
    if (this.hasCondition(combatant, condition)) {
      this.removeCondition.emit({ combatant, condition });
      return;
    }
    this.applyCondition.emit({ combatant, condition, rounds: this.conditionRounds });
  }

  isConditionsOpen(combatant: InitiativeCombatant): boolean {
    return this.openConditionsFor === combatant.id;
  }

  toggleConditions(combatant: InitiativeCombatant): void {
    this.openConditionsFor = this.isConditionsOpen(combatant) ? null : combatant.id;
  }

  /**
   * Committed on blur rather than on every keystroke: clearing the field to
   * type a new total would otherwise read as 0 for a moment and flash the death
   * saves open. The clamped figure is written straight back to the element, so
   * the DM never reads a number the tracker did not accept.
   */
  onHpInput(combatant: InitiativeCombatant, input: HTMLInputElement): void {
    const typed = input.valueAsNumber;
    const hp = Number.isFinite(typed)
      ? Math.max(0, Math.min(combatant.max_hp, Math.round(typed)))
      : combatant.hp;

    input.value = `${hp}`;
    this.hpChange.emit({ combatant, hp });
  }

  /** Players only, and only once they are down — monsters simply die. */
  showsDeathSaves(combatant: InitiativeCombatant): boolean {
    return combatant.is_player && combatant.hp <= 0;
  }

  deathSaveCount(combatant: InitiativeCombatant, kind: 'successes' | 'failures'): number {
    return combatant.deathSaves?.[kind] ?? 0;
  }

  deathSaveOutcome(combatant: InitiativeCombatant): 'stable' | 'dead' | null {
    if (this.deathSaveCount(combatant, 'failures') >= 3) return 'dead';
    if (this.deathSaveCount(combatant, 'successes') >= 3) return 'stable';
    return null;
  }

  confirmEndCombat(): void {
    this.showEndCombatConfirm = false;
    this.endCombat.emit();
  }
}
