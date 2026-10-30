import { Component, TemplateRef, ViewChild } from '@angular/core';
import { Router } from '@angular/router';
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
export class LoginComponent {
  @ViewChild('forgeLogo', { static: true }) forgeLogo!: TemplateRef<unknown>;

  mode: 'choice' | 'tutorial' | 'auth' = 'choice';
  tutorialStep = 0;
  tutorialRole: 'none' | 'player' | 'dm' | 'intro' = 'none';
  username = '';
  password = '';
  isRegister = false;
  error = '';
  /** True while register/login runs: spins the submit button and blocks resubmits. */
  submitting = false;

  constructor(private authService: AuthService, private router: Router) {}

  openTutorial(role: 'none' | 'player' | 'dm' | 'intro' = 'none') {
    this.tutorialRole = role;
    this.tutorialStep = 0;
    this.mode = 'tutorial';
  }

  onSubmit() {
    if (this.submitting) return;
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
      next: () => {
        // Stays "submitting" through the navigation so the button cannot fire twice.
        this.router.navigate(['/campaigns']);
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
