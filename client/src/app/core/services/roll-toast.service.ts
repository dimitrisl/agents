import { Injectable, signal } from '@angular/core';

export interface ActiveRollEvent {
  title: string;
  expression: string;
  raw: number;
  modifier: number;
  total: number;
  mode?: 'normal' | 'advantage' | 'disadvantage';
  isNat20?: boolean;
  isNat1?: boolean;
  message?: string;
}

@Injectable({
  providedIn: 'root'
})
export class RollToastService {
  activeRoll = signal<ActiveRollEvent | null>(null);

  showRoll(event: ActiveRollEvent) {
    event.isNat20 = event.raw === 20;
    event.isNat1 = event.raw === 1;
    this.activeRoll.set(event);

    setTimeout(() => {
      if (this.activeRoll() === event) {
        this.activeRoll.set(null);
      }
    }, 4500);
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

    setTimeout(() => {
      if (this.activeRoll() === event) {
        this.activeRoll.set(null);
      }
    }, 4000);
  }

  dismiss() {
    this.activeRoll.set(null);
  }
}
