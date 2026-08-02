import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { CharacterStateService } from '../../core/services/character-state.service';
import {
  ForgeBadgeComponent,
  ForgeCardComponent,
  ForgeEmptyStateComponent,
  ForgePageComponent,
} from '../../shared/ui';

interface AdminUser {
  username: string;
  name: string;
  role: string;
  superadmin: boolean;
}

@Component({
  selector: 'app-admin',
  standalone: true,
  imports: [
    CommonModule,
    ForgeBadgeComponent,
    ForgeCardComponent,
    ForgeEmptyStateComponent,
    ForgePageComponent,
  ],
  templateUrl: './admin.component.html',
  styleUrl: './admin.component.css',
})
export class AdminComponent implements OnInit {
  activeUsers = 1;

  /** Reads straight off the shared vault so it stays in sync with forge/player. */
  get totalCharacters(): number {
    return this.charState.characters().length;
  }

  readonly users: AdminUser[] = [
    {
      username: 'mitsos',
      name: 'Mitsos (DM)',
      role: 'Superadmin',
      superadmin: true,
    },
    {
      username: 'michalis',
      name: 'Michalis (PLAYER)',
      role: 'Superadmin',
      superadmin: true,
    },
  ];

  constructor(private charState: CharacterStateService) {}

  trackUser(_index: number, user: AdminUser): string {
    return user.username;
  }

  ngOnInit() {
    // Reuses the shared vault, so opening admin after playing costs no request.
    this.charState.ensureLoaded().subscribe();
  }
}
