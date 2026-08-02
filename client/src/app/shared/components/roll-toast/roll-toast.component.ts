import { Component, effect, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RollToastService } from '../../../core/services/roll-toast.service';
import { Dice3dComponent } from '../dice-3d/dice-3d.component';
import { ForgeBadgeComponent, ForgeButtonDirective } from '../../ui';

/** Longest we wait for the dice before showing the total regardless. */
const REVEAL_FALLBACK = 6500;

@Component({
  selector: 'app-roll-toast',
  standalone: true,
  imports: [CommonModule, Dice3dComponent, ForgeBadgeComponent, ForgeButtonDirective],
  templateUrl: './roll-toast.component.html',
  styleUrl: './roll-toast.component.css',
})
export class RollToastComponent {
  /** Fallback flat-die animation, only used when WebGL is unavailable. */
  isRolling = signal(false);
  webglFailed = signal(false);
  diceSettled = signal(false);
  /** Bumped per roll so the dice view replays even for identical numbers. */
  rollKey = signal(0);
  accent = signal('#d9b355');

  private revealTimer: ReturnType<typeof setTimeout> | null = null;

  constructor(public rollService: RollToastService) {
    // The dice view is lazy so three.js stays out of the initial bundle. Warm the
    // chunk up front so the first roll of a session does not wait on the network.
    import('../dice-3d/dice-3d.component').catch(() => this.webglFailed.set(true));

    effect(() => {
      const roll = this.rollService.activeRoll();
      if (!roll || roll.message) return;

      this.diceSettled.set(false);
      this.rollKey.update((key) => key + 1);
      this.accent.set(this.readAccent());
      // Reveal the result anyway if the dice never report back.
      this.armReveal();

      if (!this.webglFailed()) return;

      this.isRolling.set(false);
      setTimeout(() => {
        this.isRolling.set(true);
        setTimeout(() => {
          this.isRolling.set(false);
          this.onDiceSettled();
        }, 650);
      });
    });
  }

  onDiceSettled(): void {
    this.clearReveal();
    this.diceSettled.set(true);
    this.rollService.notifySettled();
  }

  onWebglUnsupported(): void {
    this.webglFailed.set(true);
    this.onDiceSettled();
  }

  displayTitle(title: string): string {
    return title.replace(/^[\u{1F3B2}]\s*/u, '');
  }

  private armReveal(): void {
    this.clearReveal();
    this.revealTimer = setTimeout(() => this.onDiceSettled(), REVEAL_FALLBACK);
  }

  private clearReveal(): void {
    if (this.revealTimer !== null) {
      clearTimeout(this.revealTimer);
      this.revealTimer = null;
    }
  }

  private readAccent(): string {
    const value = getComputedStyle(document.documentElement)
      .getPropertyValue('--theme-accent')
      .trim();
    // three.js only understands literal colours, not the computed forms a theme
    // variable can hold (color-mix, var chains, ...).
    return /^(#|rgb|hsl)/i.test(value) ? value : '#d9b355';
  }
}
