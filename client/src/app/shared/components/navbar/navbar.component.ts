import { Component, Input } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Router, RouterLink, RouterLinkActive } from '@angular/router';
import { AuthService } from '../../../core/services/auth.service';
import { CharacterStateService } from '../../../core/services/character-state.service';
import { ForgeButtonDirective, ForgeToggleComponent } from '../../ui';

@Component({
  selector: 'app-navbar',
  standalone: true,
  imports: [CommonModule, RouterLink, RouterLinkActive, ForgeButtonDirective, ForgeToggleComponent],
  templateUrl: './navbar.component.html',
  styleUrl: './navbar.component.css',
})
export class NavbarComponent {
  @Input() section: 'brand' | 'nav' | 'user' = 'nav';

  constructor(
    public authService: AuthService,
    public charState: CharacterStateService,
    private router: Router
  ) {}

  is2024() {
    return this.charState.dndEdition().includes('2024');
  }

  toggleEdition() {
    this.charState.toggleEdition();
  }

  isAdmin(): boolean {
    return !!this.authService.currentUser()?.is_admin;
  }

  get userRoleLabel(): string {
    const user = this.authService.currentUser();
    if (user?.is_admin) return 'Administrator';
    if (user?.role === 'dm' || this.router.url.startsWith('/dm')) return 'Dungeon Master';
    return 'Player';
  }
}
