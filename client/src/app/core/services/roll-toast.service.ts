import { Injectable, computed, signal } from '@angular/core';

export interface ActiveRollEvent {
  title: string;
  expression: string;
  raw: number;
  rolls?: number[];
  sides?: number;
  modifier: number;
  total: number;
  mode?: 'normal' | 'advantage' | 'disadvantage';
  isNat20?: boolean;
  isNat1?: boolean;
  /** Per-die sizes parallel to `rolls`, for mixed throws (2d6 + 6d8). */
  diceSides?: number[];
  /** A critical-hit damage roll: dice already doubled; shown with the critical effects. */
  isCritHit?: boolean;
  /**
   * One line per part of a damage roll (weapon, each rider). When present the
   * card lists them, and parts with `saveHalf` get a "passed the save → ½" button.
   */
  damageParts?: RollDamagePart[];
  message?: string;
}

export interface RollDamagePart {
  label: string;
  /** "3d8 (8+5+2)" or "1d6 (3) +7" */
  detail: string;
  total: number;
  /** The target can save for half against this part; `dc` is e.g. "DC 16 CON". */
  saveHalf?: { dc?: string };
}

/** Safety net in case the dice never report back (no WebGL, tab in background). */
const MAX_ROLL_LIFETIME = 11000;
/** How long the result stays up once the dice have come to rest. */
const LINGER_AFTER_SETTLE = 3400;
const MESSAGE_LIFETIME = 4000;

@Injectable({
  providedIn: 'root'
})
export class RollToastService {
  activeRoll = signal<ActiveRollEvent | null>(null);

  /** Damage parts the player marked as saved-for-half on the roll being shown. */
  readonly halvedParts = signal<ReadonlySet<number>>(new Set());

  /** The total as it stands after any halving (PHB: halve, round down, per part). */
  readonly displayTotal = computed(() => {
    const roll = this.activeRoll();
    if (!roll?.damageParts) return roll?.total ?? 0;
    const halved = this.halvedParts();
    return roll.damageParts.reduce((sum, part, i) => sum + this.partTotal(part, halved.has(i)), 0);
  });

  partTotal(part: RollDamagePart, halved: boolean): number {
    return halved ? Math.floor(part.total / 2) : part.total;
  }

  /** Flip a part between full and half; the dice are not rolled again. */
  togglePartHalved(index: number) {
    const next = new Set(this.halvedParts());
    if (!next.delete(index)) next.add(index);
    this.halvedParts.set(next);
  }

  private dismissTimer: ReturnType<typeof setTimeout> | null = null;

  showRoll(event: ActiveRollEvent) {
    const sides = event.sides ?? 20;
    event.rolls = event.rolls ?? [event.raw];
    event.isNat20 = sides === 20 && event.raw === 20;
    event.isNat1 = sides === 20 && event.raw === 1;
    this.halvedParts.set(new Set());
    this.activeRoll.set(event);
    this.armDismiss(event, MAX_ROLL_LIFETIME);
  }

  showMessage(title: string, message: string) {
    const event: ActiveRollEvent = {
      title,
      expression: '',
      raw: 0,
      modifier: 0,
      total: 0,
      message
    };
    this.activeRoll.set(event);
    this.armDismiss(event, MESSAGE_LIFETIME);
  }

  /** Called by the dice view once the physics simulation has settled. */
  notifySettled() {
    const event = this.activeRoll();
    if (!event) return;
    if (event.damageParts?.some((part) => part.saveHalf)) {
      // The player still has to say whether the target saved: stay until closed.
      this.clearTimer();
      return;
    }
    this.armDismiss(event, LINGER_AFTER_SETTLE);
  }

  dismiss() {
    this.clearTimer();
    this.activeRoll.set(null);
  }

  private armDismiss(event: ActiveRollEvent, delay: number) {
    this.clearTimer();
    this.dismissTimer = setTimeout(() => {
      this.dismissTimer = null;
      if (this.activeRoll() === event) {
        this.activeRoll.set(null);
      }
    }, delay);
  }

  private clearTimer() {
    if (this.dismissTimer !== null) {
      clearTimeout(this.dismissTimer);
      this.dismissTimer = null;
    }
  }
}
