import { Injectable, signal } from '@angular/core';

@Injectable({
  providedIn: 'root',
})
export class HapticsService {
  readonly isSupported = signal<boolean>(
    typeof navigator !== 'undefined' && typeof navigator.vibrate === 'function'
  );

  lightTap(): void {
    this.vibrate(15);
  }

  critSuccess(): void {
    this.vibrate([40, 60, 100]);
  }

  critFail(): void {
    this.vibrate([120, 80, 120]);
  }

  turnAlert(): void {
    this.vibrate([80, 50, 80, 50, 150]);
  }

  damageTaken(): void {
    this.vibrate([50, 30, 50]);
  }

  private vibrate(pattern: number | number[]): void {
    if (this.isSupported() && typeof navigator !== 'undefined' && navigator.vibrate) {
      try {
        navigator.vibrate(pattern);
      } catch {
        // no-op if vibration is blocked or not permitted
      }
    }
  }
}
