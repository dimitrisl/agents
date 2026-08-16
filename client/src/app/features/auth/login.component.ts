import { Component, TemplateRef, ViewChild } from '@angular/core';
import { Router } from '@angular/router';
import { AuthService } from '../../core/services/auth.service';
import { ChoiceViewComponent } from './choice-view/choice-view.component';
import { TutorialViewComponent } from './tutorial-view/tutorial-view.component';
import { AuthFormViewComponent } from './auth-form-view/auth-form-view.component';

@Component({
  selector: 'app-login',
  standalone: true,
  imports: [ChoiceViewComponent, TutorialViewComponent, AuthFormViewComponent],
  templateUrl: './login.component.html',
})
export class LoginComponent {
  @ViewChild('forgeLogo', { static: true }) forgeLogo!: TemplateRef<unknown>;

  mode: 'choice' | 'tutorial' | 'auth' = 'choice';
  tutorialStep = 0;
  username = '';
  password = '';
  isRegister = false;
  error = '';

  constructor(private authService: AuthService, private router: Router) {}

  onQuickDemo(type: string) {
    this.authService.demoLogin(type).subscribe({
      next: () => this.router.navigate(['/player']),
      error: (err) => (this.error = 'Demo login failed.')
    });
  }

  onSubmit() {
    if (!this.username || !this.password) {
      this.error = 'Please provide both username and password.';
      return;
    }

    if (this.isRegister) {
      this.authService.register({ username: this.username, password: this.password }).subscribe({
        next: () => {
          this.isRegister = false;
          this.login();
        },
        error: (err) => {
          this.error = err.error?.detail || 'Registration failed.';
        }
      });
    } else {
      this.login();
    }
  }

  private login() {
    this.authService.login({ username: this.username, password: this.password }).subscribe({
      next: () => {
        this.router.navigate(['/player']);
      },
      error: (err) => {
        this.error = err.error?.detail || 'Invalid username or password.';
      }
    });
  }
}
