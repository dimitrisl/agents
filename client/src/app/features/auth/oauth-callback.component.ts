import { ChangeDetectionStrategy, Component, OnInit, signal } from '@angular/core';
import { HttpErrorResponse } from '@angular/common/http';
import { Router } from '@angular/router';
import { AuthService } from '../../core/services/auth.service';
import { describeHttpError } from '../../core/interceptors/error.interceptor';
import {
  ForgeAuthShellComponent,
  ForgeButtonDirective,
  ForgeCardComponent,
  ForgeSpinnerComponent,
} from '../../shared/ui';

@Component({
  selector: 'app-oauth-callback',
  standalone: true,
  imports: [ForgeAuthShellComponent, ForgeButtonDirective, ForgeCardComponent, ForgeSpinnerComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <forge-auth-shell>
      <forge-card class="w-full max-w-md text-center" [hoverable]="false" padding="lg">
        @if (!errorMessage()) {
          <div class="flex flex-col items-center gap-4 py-4">
            <forge-spinner size="md" tone="accent" label="Completing Discord sign-in" />
            <h1 class="font-display text-title text-ink">Completing Sign-In…</h1>
            <p class="text-body text-muted">Verifying your Discord session with Phyrexian Forge.</p>
          </div>
        } @else {
          <div class="flex flex-col items-center gap-4 py-2" role="alert">
            <h1 class="font-display text-title text-ink">Discord Sign-In Failed</h1>
            <p class="text-body text-red">{{ errorMessage() }}</p>
            <button forgeButton variant="primary" size="md" type="button" (click)="backToLogin()">
              Return to Login
            </button>
          </div>
        }
      </forge-card>
    </forge-auth-shell>
  `,
})
export class OAuthCallbackComponent implements OnInit {
  readonly errorMessage = signal('');

  constructor(private authService: AuthService, private router: Router) {}

  ngOnInit(): void {
    const rawHash = typeof window !== 'undefined' ? window.location.hash : '';
    const params = new URLSearchParams(rawHash.replace(/^#/, ''));
    const code = params.get('code')?.trim() || '';

    if (typeof window !== 'undefined' && window.history?.replaceState) {
      window.history.replaceState(null, '', window.location.pathname + window.location.search);
    }

    if (!code) {
      this.errorMessage.set('Missing Discord exchange code. Please try signing in again.');
      return;
    }

    this.authService.exchangeDiscordCode(code).subscribe({
      next: (res) => {
        this.router.navigate([res.user?.must_change_password ? '/settings' : '/campaigns']);
      },
      error: (err) => {
        const detail =
          typeof err?.error?.detail === 'string'
            ? err.error.detail
            : err instanceof HttpErrorResponse
              ? describeHttpError(err)?.body
              : undefined;
        this.errorMessage.set(detail || 'Invalid or expired Discord login session.');
      },
    });
  }

  backToLogin(): void {
    this.router.navigate(['/login']);
  }
}
