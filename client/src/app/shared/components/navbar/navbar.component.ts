import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterLink, RouterLinkActive } from '@angular/router';
import { AuthService } from '../../../core/services/auth.service';
import { CharacterStateService } from '../../../core/services/character-state.service';

@Component({
  selector: 'app-navbar',
  standalone: true,
  imports: [CommonModule, RouterLink, RouterLinkActive],
  template: `
    <header class="phyrexian-card navbar-header">
      <div class="brand-section">
        <div class="brand-logo">
          <svg width="32" height="32" viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg">
            <polygon points="50,15 85,35 85,75 50,90 15,75 15,35" stroke="var(--theme-accent)" stroke-width="6" fill="rgba(255, 75, 75, 0.15)" />
            <line x1="50" y1="15" x2="50" y2="90" stroke="var(--theme-accent)" stroke-width="4" />
          </svg>
        </div>
        <div>
          <h1 class="brand-title">Phyrexian Forge</h1>
          <span class="edition-sub">"All will be one • {{ charState.dndEdition() }}"</span>
        </div>
      </div>

      <nav class="nav-links">
        <a routerLink="/player" routerLinkActive="active" class="nav-btn">🗡️ Player Dashboard</a>
        <a routerLink="/forge" routerLinkActive="active" class="nav-btn">✨ Character Forge</a>
        <a routerLink="/dm" routerLinkActive="active" class="nav-btn">🏰 DM Workspace</a>
        <a routerLink="/rules" routerLinkActive="active" class="nav-btn">📚 Rules Library</a>
        <a routerLink="/settings" routerLinkActive="active" class="nav-btn">⚙️ Settings</a>
        <a *ngIf="isAdmin()" routerLink="/admin" routerLinkActive="active" class="nav-btn">🛡️ Admin</a>
      </nav>

      <div class="user-controls">
        <div class="edition-toggle">
          <label class="switch">
            <input type="checkbox" [checked]="is2024()" (change)="toggleEdition()" />
            <span class="slider"></span>
          </label>
          <span class="toggle-label">{{ is2024() ? '2024 Revision' : '2014 Legacy' }}</span>
        </div>

        <ng-container *ngIf="authService.currentUser() as user">
          <div class="user-greeting">
            <span>👤 Logged in as <strong class="user-name">{{ user.name || user.username }}</strong></span>
          </div>
          <button class="phyrexian-btn-secondary logout-btn" (click)="authService.logout()">
            Logout
          </button>
        </ng-container>
      </div>
    </header>
  `,
  styles: [`
    .navbar-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 1.5rem; border-radius: 0 0 12px 12px; padding: 0.8rem 1.5rem; }
    .brand-section { display: flex; align-items: center; gap: 0.75rem; }
    .brand-title { font-size: 1.4rem; color: var(--theme-accent); margin: 0; line-height: 1.1; }
    .edition-sub { font-size: 0.72rem; color: var(--text-muted); font-style: italic; }
    .nav-links { display: flex; gap: 0.75rem; }
    .nav-btn { color: var(--text-muted); text-decoration: none; font-weight: 600; padding: 0.5rem 0.9rem; border-radius: 6px; font-size: 0.9rem; transition: all 0.2s; }
    .nav-btn:hover, .nav-btn.active { color: var(--text-primary); background: rgba(255, 255, 255, 0.08); border-bottom: 2px solid var(--theme-accent); }
    .user-controls { display: flex; align-items: center; gap: 1.25rem; }
    .edition-toggle { display: flex; align-items: center; gap: 0.5rem; }
    .toggle-label { font-size: 0.78rem; color: var(--text-muted); }
    .switch { position: relative; display: inline-block; width: 36px; height: 20px; }
    .switch input { opacity: 0; width: 0; height: 0; }
    .slider { position: absolute; cursor: pointer; top: 0; left: 0; right: 0; bottom: 0; background-color: #333; transition: .3s; border-radius: 20px; }
    .slider:before { position: absolute; content: ""; height: 14px; width: 14px; left: 3px; bottom: 3px; background-color: white; transition: .3s; border-radius: 50%; }
    input:checked + .slider { background-color: var(--accent-violet); }
    input:checked + .slider:before { transform: translateX(16px); }
    .user-greeting { font-size: 0.82rem; color: var(--text-muted); }
    .user-name { color: var(--theme-accent); }
    .logout-btn { font-size: 0.78rem; padding: 0.35rem 0.75rem; }
  `]
})
export class NavbarComponent {
  constructor(
    public authService: AuthService,
    public charState: CharacterStateService
  ) {}

  is2024() {
    return this.charState.dndEdition().includes('2024');
  }

  toggleEdition() {
    this.charState.toggleEdition();
  }

  isAdmin(): boolean {
    const u = this.authService.currentUser();
    return u?.username === 'mitsos' || u?.id === 'local_user_mitsos';
  }
}
