import { Injectable, signal } from '@angular/core';

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
  message?: string;
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

  private dismissTimer: ReturnType<typeof setTimeout> | null = null;

  showRoll(event: ActiveRollEvent) {
    const sides = event.sides ?? 20;
    event.rolls = event.rolls ?? [event.raw];
    event.isNat20 = sides === 20 && event.raw === 20;
    event.isNat1 = sides === 20 && event.raw === 1;
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
    if (event) {
      this.armDismiss(event, LINGER_AFTER_SETTLE);
    }
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
