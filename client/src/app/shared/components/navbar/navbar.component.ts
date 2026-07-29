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
        <h1 class="brand-title">Phyrexian Forge</h1>
        <span class="edition-badge" [class.badge-2024]="is2024()">
          {{ charState.dndEdition() }}
        </span>
      </div>

      <nav class="nav-links">
        <a routerLink="/player" routerLinkActive="active" class="nav-btn">🗡️ Player Hub</a>
        <a routerLink="/dm" routerLinkActive="active" class="nav-btn">🏰 DM Workspace</a>
        <a routerLink="/rules" routerLinkActive="active" class="nav-btn">📚 Rules Oracle</a>
      </nav>

      <div class="user-controls">
        <button class="phyrexian-btn-secondary toggle-btn" (click)="toggleEdition()">
          🔄 Switch Edition
        </button>

        <ng-container *ngIf="authService.currentUser() as user">
          <span class="user-greeting">👤 {{ user.name || user.username }}</span>
          <button class="phyrexian-btn-secondary logout-btn" (click)="authService.logout()">
            Logout
          </button>
        </ng-container>
      </div>
    </header>
  `,
  styles: [`
    .navbar-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 1.5rem;
      border-radius: 0 0 12px 12px;
    }
    .brand-section {
      display: flex;
      align-items: center;
      gap: 0.75rem;
    }
    .brand-title {
      font-size: 1.5rem;
      color: var(--theme-accent);
    }
    .edition-badge {
      font-size: 0.7rem;
      padding: 0.2rem 0.6rem;
      border-radius: 12px;
      background: rgba(255, 75, 75, 0.15);
      color: var(--primary-red);
      border: 1px solid var(--primary-red);
    }
    .badge-2024 {
      background: rgba(191, 90, 242, 0.15);
      color: var(--accent-violet);
      border-color: var(--accent-violet);
    }
    .nav-links {
      display: flex;
      gap: 1rem;
    }
    .nav-btn {
      color: var(--text-muted);
      text-decoration: none;
      font-weight: 600;
      padding: 0.5rem 1rem;
      border-radius: 6px;
      transition: all 0.2s;
    }
    .nav-btn:hover, .nav-btn.active {
      color: var(--text-primary);
      background: rgba(255, 255, 255, 0.08);
      border-bottom: 2px solid var(--theme-accent);
    }
    .user-controls {
      display: flex;
      align-items: center;
      gap: 1rem;
    }
    .user-greeting {
      font-size: 0.85rem;
      color: var(--text-muted);
    }
    .toggle-btn, .logout-btn {
      font-size: 0.8rem;
      padding: 0.4rem 0.8rem;
    }
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
}
