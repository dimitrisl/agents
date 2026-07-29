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
    <div class="landing-container">
      <!-- 1. CHOICE VIEW -->
      <div *ngIf="mode === 'choice'" class="phyrexian-card choice-card">
        <div class="logo-wrapper">
          <svg width="100" height="100" viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg">
            <circle cx="50" cy="50" r="42" stroke="#ff4b4b" stroke-width="5" fill="none" class="glowing-ring" />
            <polygon points="50,15 85,35 85,75 50,90 15,75 15,35" stroke="#ff4b4b" stroke-width="3" fill="rgba(255, 75, 75, 0.1)" />
            <line x1="50" y1="15" x2="50" y2="90" stroke="#ff4b4b" stroke-width="3" />
            <line x1="15" y1="35" x2="85" y2="75" stroke="#ff4b4b" stroke-width="2" />
            <line x1="15" y1="75" x2="85" y2="35" stroke="#ff4b4b" stroke-width="2" />
          </svg>
        </div>

        <h1 class="brand-heading">PHYREXIAN FORGE</h1>
        <p class="brand-subtitle">"All Will Be One • 5e Legacy & 5.5e Edition"</p>

        <div class="choice-buttons">
          <button class="phyrexian-btn choice-btn" (click)="mode = 'tutorial'">
            ✨ I'm New Here!
            <span class="btn-subtext">Start your first adventure tutorial</span>
          </button>

          <button class="phyrexian-btn-secondary choice-btn" (click)="mode = 'auth'">
            ⚔️ Seasoned Adventurer
            <span class="btn-subtext">Enter the Forge with your credentials</span>
          </button>
        </div>

        <div class="quick-demo-section">
          <p class="demo-title">⚡ Quick Access (Instant Demo)</p>
          <div class="demo-grid">
            <button class="phyrexian-btn-secondary demo-btn" (click)="onQuickDemo('mitsos')">
              🎮 Demo DM (Mitsos)
            </button>
            <button class="phyrexian-btn-secondary demo-btn" (click)="onQuickDemo('guest')">
              🗡️ Demo Adventurer
            </button>
          </div>
        </div>
      </div>

      <!-- 2. WIZARD'S JOURNEY TUTORIAL VIEW -->
      <div *ngIf="mode === 'tutorial'" class="phyrexian-card tutorial-card">
        <h2 class="tutorial-header">🔮 Wizard's Journey: Step {{ tutorialStep + 1 }} of 3</h2>

        <div class="progress-dots">
          <span class="dot" [class.active]="tutorialStep === 0"></span>
          <span class="dot" [class.active]="tutorialStep === 1"></span>
          <span class="dot" [class.active]="tutorialStep === 2"></span>
        </div>

        <!-- Step 1 -->
        <div *ngIf="tutorialStep === 0" class="step-box">
          <div class="step-icon">🔮</div>
          <h3>Why the Forge?</h3>
          <p>
            Tired of messy scrolls and math-induced headaches? The Forge is your <b>arcane companion</b> that automates the complex mechanics of D&D 5e & 5.5e! We bridge the gap between imagination and rules, letting you focus on the story while we handle the heavy lifting.
          </p>
        </div>

        <!-- Step 2 -->
        <div *ngIf="tutorialStep === 1" class="step-box">
          <div class="step-icon">✨</div>
          <h3>Manifest Your Hero</h3>
          <p>
            Jump into the <b>Player Dashboard</b> to forge your legend. Use our friendly Gemini AI to write backstories, optimize stats, level up seamlessly, and generate beautiful hero portraits with AI image tools!
          </p>
        </div>

        <!-- Step 3 -->
        <div *ngIf="tutorialStep === 2" class="step-box">
          <div class="step-icon">🧙‍♂️</div>
          <h3>Command the Realm</h3>
          <p>
            DMs can organize epic campaigns in the <b>DM Workspace</b> with live party hit point trackers, initiative sequencing, whisper channels, and a complete 2014 & 2024 digital rules oracle!
          </p>
        </div>

        <div class="tutorial-nav">
          <button class="phyrexian-btn-secondary" (click)="tutorialStep > 0 ? tutorialStep = tutorialStep - 1 : mode = 'choice'">
            ⬅️ {{ tutorialStep > 0 ? 'Previous Spell' : 'Back to Choice' }}
          </button>

          <button *ngIf="tutorialStep < 2" class="phyrexian-btn" (click)="tutorialStep = tutorialStep + 1">
            Next Incantation ➡️
          </button>

          <button *ngIf="tutorialStep === 2" class="phyrexian-btn" (click)="mode = 'auth'">
            🚀 Enter the Forge
          </button>
        </div>
      </div>

      <!-- 3. AUTH FORM VIEW -->
      <div *ngIf="mode === 'auth'" class="phyrexian-card auth-card">
        <h2 class="auth-heading">{{ isRegister ? '🆕 Create Account' : '🔑 Seasoned Adventurer Login' }}</h2>

        <div class="form-group">
          <label>Username:</label>
          <input type="text" class="phyrexian-input" [(ngModel)]="username" />
        </div>

        <div class="form-group">
          <label>Password:</label>
          <input type="password" class="phyrexian-input" [(ngModel)]="password" (keyup.enter)="onSubmit()" />
        </div>

        <div *ngIf="error" class="error-msg">❌ {{ error }}</div>

        <div class="actions">
          <button class="phyrexian-btn full-btn" (click)="onSubmit()">
            {{ isRegister ? 'Create Account' : 'Enter Forge' }}
          </button>
          
          <button class="phyrexian-btn-secondary full-btn" (click)="isRegister = !isRegister">
            {{ isRegister ? 'Already registered? Login' : 'New Hero? Register' }}
          </button>
        </div>

        <div class="quick-demo-section" style="margin-top: 1.5rem;">
          <p class="demo-title">⚡ Instant Demo Access</p>
          <div class="demo-grid">
            <button class="phyrexian-btn-secondary demo-btn" (click)="onQuickDemo('mitsos')">
              🎮 DM Mitsos Demo
            </button>
            <button class="phyrexian-btn-secondary demo-btn" (click)="onQuickDemo('guest')">
              🗡️ Adventurer Demo
            </button>
          </div>
        </div>

        <button class="phyrexian-btn-secondary full-btn" style="margin-top: 1rem;" (click)="mode = 'choice'">
          ⬅️ Back to Choice
        </button>
      </div>
    </div>
  `,
  styles: [`
    .landing-container {
      display: flex;
      justify-content: center;
      align-items: center;
      min-height: 85vh;
      padding: 1.5rem;
    }
    .choice-card, .tutorial-card, .auth-card {
      width: 100%;
      max-width: 480px;
      text-align: center;
    }
    .logo-wrapper {
      margin-bottom: 1rem;
    }
    .glowing-ring {
      filter: drop-shadow(0 0 10px rgba(255, 75, 75, 0.5));
    }
    .brand-heading {
      font-size: 2.2rem;
      color: var(--primary-red);
      margin-bottom: 0.2rem;
    }
    .brand-subtitle {
      color: var(--text-muted);
      font-style: italic;
      margin-bottom: 1.75rem;
    }
    .choice-buttons {
      display: flex;
      flex-direction: column;
      gap: 1rem;
      margin-bottom: 2rem;
    }
    .choice-btn {
      display: flex;
      flex-direction: column;
      align-items: center;
      padding: 0.9rem;
      font-size: 1.1rem;
    }
    .btn-subtext {
      font-size: 0.75rem;
      font-weight: 400;
      opacity: 0.8;
      margin-top: 0.2rem;
    }
    .quick-demo-section {
      border-top: 1px solid var(--border-card);
      padding-top: 1.25rem;
    }
    .demo-title {
      font-size: 0.8rem;
      color: var(--text-muted);
      text-transform: uppercase;
      letter-spacing: 1px;
      margin-bottom: 0.75rem;
    }
    .demo-grid {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 0.75rem;
    }
    .demo-btn {
      font-size: 0.85rem;
      padding: 0.5rem;
      justify-content: center;
    }
    /* Tutorial styling */
    .tutorial-header {
      font-size: 1.4rem;
      color: var(--theme-accent);
      margin-bottom: 1rem;
    }
    .progress-dots {
      display: flex;
      justify-content: center;
      gap: 0.5rem;
      margin-bottom: 1.5rem;
    }
    .dot {
      width: 12px;
      height: 12px;
      border-radius: 50%;
      background: rgba(255, 255, 255, 0.2);
      transition: all 0.3s;
    }
    .dot.active {
      background: var(--theme-accent);
      box-shadow: 0 0 10px var(--theme-accent);
    }
    .step-box {
      background: rgba(0, 0, 0, 0.3);
      border: 1px solid var(--border-card);
      border-radius: 10px;
      padding: 1.5rem;
      margin-bottom: 1.5rem;
    }
    .step-icon {
      font-size: 3.5rem;
      margin-bottom: 0.5rem;
    }
    .step-box h3 {
      font-size: 1.3rem;
      margin-bottom: 0.75rem;
      color: var(--text-gold);
    }
    .step-box p {
      color: var(--text-primary);
      line-height: 1.6;
    }
    .tutorial-nav {
      display: flex;
      justify-content: space-between;
    }
    /* Auth Form Styling */
    .auth-heading {
      font-size: 1.5rem;
      color: var(--theme-accent);
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
