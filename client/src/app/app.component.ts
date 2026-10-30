import { Component, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import {
  NavigationCancel,
  NavigationEnd,
  NavigationError,
  NavigationStart,
  Router,
  RouterOutlet,
} from '@angular/router';
import { NavbarComponent } from './shared/components/navbar/navbar.component';
import { RollToastComponent } from './shared/components/roll-toast/roll-toast.component';
import { CommandPaletteComponent } from './shared/components/command-palette/command-palette.component';
import { AuthService } from './core/services/auth.service';
import { ForgeShellComponent } from './shared/ui';

/** Navigations faster than this never show the bar, so cached pages don't flicker. */
const NAVIGATION_BAR_DELAY_MS = 150;

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [CommonModule, RouterOutlet, NavbarComponent, RollToastComponent, CommandPaletteComponent, ForgeShellComponent],
  templateUrl: './app.component.html',
})
export class AppComponent {
  title = 'Phyrexian Forge';

  /** True while a page's lazy code is downloading (and its guards run). */
  readonly navigating = signal(false);
  private navigationTimer: ReturnType<typeof setTimeout> | null = null;

  constructor(public authService: AuthService, router: Router) {
    router.events.pipe(takeUntilDestroyed()).subscribe((event) => {
      if (event instanceof NavigationStart) {
        this.clearNavigationTimer();
        this.navigationTimer = setTimeout(() => this.navigating.set(true), NAVIGATION_BAR_DELAY_MS);
      } else if (
        event instanceof NavigationEnd ||
        event instanceof NavigationCancel ||
        event instanceof NavigationError
      ) {
        this.clearNavigationTimer();
        this.navigating.set(false);
      }
    });
  }

  private clearNavigationTimer() {
    if (this.navigationTimer !== null) {
      clearTimeout(this.navigationTimer);
      this.navigationTimer = null;
    }
  }
}
