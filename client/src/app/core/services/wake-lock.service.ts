import { Injectable, signal } from '@angular/core';

@Injectable({
  providedIn: 'root',
})
export class WakeLockService {
  readonly isSupported = signal<boolean>(typeof navigator !== 'undefined' && 'wakeLock' in navigator);
  readonly isEnabled = signal<boolean>(false);
  readonly isActive = signal<boolean>(false);

  private wakeLockSentinel: any = null;

  constructor() {
    if (typeof document !== 'undefined') {
      document.addEventListener('visibilitychange', () => {
        if (document.visibilityState === 'visible' && this.isEnabled()) {
          this.acquire();
        }
      });
    }
  }

  async toggle(): Promise<void> {
    if (this.isEnabled()) {
      await this.disable();
    } else {
      await this.enable();
    }
  }

  async enable(): Promise<void> {
    this.isEnabled.set(true);
    await this.acquire();
  }

  async disable(): Promise<void> {
    this.isEnabled.set(false);
    await this.release();
  }

  private async acquire(): Promise<void> {
    if (!this.isSupported() || typeof navigator === 'undefined') {
      return;
    }
    try {
      if (this.wakeLockSentinel && !this.wakeLockSentinel.released) {
        return;
      }
      this.wakeLockSentinel = await (navigator as any).wakeLock.request('screen');
      this.isActive.set(true);

      this.wakeLockSentinel.addEventListener('release', () => {
        this.isActive.set(false);
        this.wakeLockSentinel = null;
      });
    } catch {
      this.isActive.set(false);
      this.wakeLockSentinel = null;
    }
  }

  private async release(): Promise<void> {
    if (this.wakeLockSentinel) {
      try {
        await this.wakeLockSentinel.release();
      } catch {
        // no-op
      }
      this.wakeLockSentinel = null;
    }
    this.isActive.set(false);
  }
}
