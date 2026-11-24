import {
  Component,
  DestroyRef,
  HostListener,
  OnInit,
  Optional,
  TemplateRef,
  ViewChild,
  inject,
} from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { ActivatedRoute, Router } from '@angular/router';
import { AuthService } from '../../core/services/auth.service';
import { describeHttpError } from '../../core/interceptors/error.interceptor';
import { HttpErrorResponse } from '@angular/common/http';
import { ChoiceViewComponent } from './choice-view/choice-view.component';
import { TutorialViewComponent } from './tutorial-view/tutorial-view.component';
import { AuthFormViewComponent } from './auth-form-view/auth-form-view.component';
import { ForgeAuthShellComponent } from '../../shared/ui/forge-auth-shell/forge-auth-shell.component';

@Component({
  selector: 'app-login',
  standalone: true,
  imports: [ChoiceViewComponent, TutorialViewComponent, AuthFormViewComponent, ForgeAuthShellComponent],
  templateUrl: './login.component.html',
})
export class LoginComponent implements OnInit {
  @ViewChild('forgeLogo', { static: true }) forgeLogo!: TemplateRef<unknown>;

  mode: 'choice' | 'tutorial' | 'auth' = 'choice';
  tutorialStep = 0;
  tutorialRole: 'none' | 'player' | 'dm' | 'intro' = 'none';
  username = '';
  password = '';
  isRegister = false;
  error = '';
  discordEnabled = false;
  /** True while register/login runs: spins the submit button and blocks resubmits. */
  submitting = false;
  /** Separate loading flag for external Discord redirect so local buttons stay accurate & reset on bfcache. */
  discordSubmitting = false;

  private readonly destroyRef = inject(DestroyRef);

  constructor(
    private authService: AuthService,
    private router: Router,
    @Optional() private route?: ActivatedRoute
  ) {}

  ngOnInit() {
    const oauthErr = this.route?.snapshot?.queryParamMap?.get('oauth_error');
    if (oauthErr) {
      this.mode = 'auth';
      this.error = oauthErr;
      this.router.navigate([], {
        relativeTo: this.route ?? undefined,
        replaceUrl: true,
        queryParams: { oauth_error: null },
        queryParamsHandling: 'merge',
      });
    }

    this.authService
      .getProviders?.()
      ?.pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (providers) => {
          this.discordEnabled = Boolean(providers?.discord);
        },
        error: () => {
          this.discordEnabled = false;
        },
      });
  }

  @HostListener('window:pageshow')
  onPageShow() {
    this.discordSubmitting = false;
  }

  onDiscordLogin() {
    if (this.submitting || this.discordSubmitting) return;
    this.discordSubmitting = true;
    this.authService.startDiscordLogin?.();
  }

  toggleAuthMode() {
    this.isRegister = !this.isRegister;
    this.error = '';
  }

  backToChoice() {
    this.mode = 'choice';
    this.error = '';
  }

  openTutorial(role: 'none' | 'player' | 'dm' | 'intro' = 'none') {
    this.tutorialRole = role;
    this.tutorialStep = 0;
    this.mode = 'tutorial';
  }

  onSubmit() {
    if (this.submitting || this.discordSubmitting) return;
    if (!this.username || !this.password) {
      this.error = 'Please provide both username and password.';
      return;
    }

    this.error = '';
    this.submitting = true;
    if (this.isRegister) {
      this.authService.register({ username: this.username, password: this.password }).subscribe({
        next: () => {
          this.isRegister = false;
          this.login();
        },
        error: (err) => {
          this.submitting = false;
          this.error = this.describeFailure(err, 'Registration failed.');
        }
      });
    } else {
      this.login();
    }
  }

  private login() {
    this.authService.login({ username: this.username, password: this.password }).subscribe({
      next: (res) => {
        // Stays "submitting" through the navigation so the button cannot fire twice.
        this.router.navigate([res?.user?.must_change_password ? '/settings' : '/campaigns']);
      },
      error: (err) => {
        this.submitting = false;
        this.error = this.describeFailure(err, 'Invalid username or password.');
      }
    });
  }

  /** A dropped connection or a 500 is not a wrong password; say which it was. */
  private describeFailure(err: unknown, fallback: string): string {
    if (err instanceof HttpErrorResponse) {
      if (typeof err.error?.detail === 'string') return err.error.detail;
      const global = describeHttpError(err);
      if (global) return global.body;
    }
    return fallback;
  }
}
