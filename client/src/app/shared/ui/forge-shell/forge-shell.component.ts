import {
  ChangeDetectionStrategy,
  Component,
  HostListener,
  Input,
  inject,
  signal,
} from '@angular/core';
import { A11yModule } from '@angular/cdk/a11y';
import { BreakpointObserver } from '@angular/cdk/layout';
import { NgClass } from '@angular/common';
import { NavigationEnd, Router } from '@angular/router';
import { filter } from 'rxjs';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';

const DESKTOP_QUERY = '(min-width: 1024px)';

@Component({
  selector: 'forge-shell',
  standalone: true,
  imports: [A11yModule, NgClass],
  templateUrl: './forge-shell.component.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ForgeShellComponent {
  /**
   * Whether this screen has navigation. Set to `false` for screens that render
   * without a sidebar (Login) — the content region then goes full-bleed and no
   * mobile header is rendered.
   */
  @Input() hasSidebar = true;

  /**
   * Optional label beside the hamburger below `lg`, where the sidebar's brand
   * block is off-canvas.
   */
  @Input() mobileTitle?: string;

  private readonly breakpointObserver = inject(BreakpointObserver);
  private readonly router = inject(Router);

  readonly drawerOpen = signal(false);
  readonly isDesktop = signal(false);

  // Both subscriptions must live in the constructor: `takeUntilDestroyed()` with no
  // explicit DestroyRef requires an injection context, and `ngOnInit` is not one —
  // calling it there throws NG0203 the moment the shell is instantiated.
  constructor() {
    this.breakpointObserver
      .observe(DESKTOP_QUERY)
      .pipe(takeUntilDestroyed())
      .subscribe(({ matches }) => {
        this.isDesktop.set(matches);

        if (matches) {
          this.closeDrawer();
        }
      });

    this.router.events
      .pipe(
        filter((event): event is NavigationEnd => event instanceof NavigationEnd),
        takeUntilDestroyed(),
      )
      .subscribe(() => this.closeDrawer());
  }

  get shellClasses(): string {
    return this.hasSidebar ? 'lg:grid lg:grid-cols-[256px_minmax(0,1fr)]' : '';
  }

  /**
   * Off-canvas below `lg`. The `lg:` utilities in the template's static class list
   * override these at ≥1024px, since Tailwind emits variant rules after their base
   * counterparts. `invisible` (not just the transform) is what keeps the closed
   * drawer out of the tab order.
   */
  get drawerClasses(): string {
    return this.drawerOpen() ? 'translate-x-0 visible' : '-translate-x-full invisible';
  }

  /** Focus is trapped only while the sidebar is an actual modal drawer. */
  get trapFocus(): boolean {
    return this.drawerOpen() && !this.isDesktop();
  }

  openDrawer(): void {
    if (!this.isDesktop()) {
      this.drawerOpen.set(true);
    }
  }

  closeDrawer(): void {
    this.drawerOpen.set(false);
  }

  @HostListener('document:keydown.escape')
  handleEscape(): void {
    if (this.drawerOpen()) {
      this.closeDrawer();
    }
  }
}
