import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';
import { AuthService } from '../../core/services/auth.service';

@Component({
  selector: 'app-login',
  standalone: true,
  imports: [CommonModule, FormsModule],
  template: `
    <div class="login-wrapper">
      <div class="phyrexian-card login-card">
        <h1 class="login-title">🩸 Phyrexian Forge</h1>
        <p class="subtitle">"All will be one."</p>

        <div class="form-group">
          <label>Username:</label>
          <input type="text" class="phyrexian-input" [(ngModel)]="username" />
        </div>

        <div class="form-group">
          <label>Password:</label>
          <input type="password" class="phyrexian-input" [(ngModel)]="password" (keyup.enter)="onSubmit()" />
        </div>

        <div *ngIf="error" class="error-msg">{{ error }}</div>

        <div class="actions">
          <button class="phyrexian-btn full-btn" (click)="onSubmit()">
            {{ isRegister ? 'Create Account' : 'Enter Forge' }}
          </button>

          <button class="phyrexian-btn-secondary full-btn" (click)="isRegister = !isRegister">
            {{ isRegister ? 'Already registered? Login' : 'New Hero? Register' }}
          </button>
        </div>
      </div>
    </div>
  `,
  styles: [`
    .login-wrapper {
      display: flex;
      justify-content: center;
      align-items: center;
      min-height: 80vh;
    }
    .login-card {
      width: 100%;
      max-width: 400px;
      text-align: center;
    }
    .login-title {
      font-size: 2rem;
      color: var(--primary-red);
      margin-bottom: 0.2rem;
    }
    .subtitle {
      color: var(--text-muted);
      font-style: italic;
      margin-bottom: 1.5rem;
    }
    .form-group {
      text-align: left;
      margin-bottom: 1rem;
    }
    .error-msg {
      color: #ff4b4b;
      font-size: 0.85rem;
      margin-bottom: 1rem;
    }
    .actions {
      display: flex;
      flex-direction: column;
      gap: 0.75rem;
      margin-top: 1.5rem;
    }
    .full-btn {
      width: 100%;
      justify-content: center;
    }
  `]
})
export class LoginComponent {
  username = '';
  password = '';
  isRegister = false;
  error = '';

  constructor(private authService: AuthService, private router: Router) {}

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
