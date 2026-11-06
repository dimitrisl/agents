import { TestBed } from '@angular/core/testing';
import { NavbarComponent } from './navbar.component';
import { AuthService } from '../../../core/services/auth.service';
import { CharacterStateService } from '../../../core/services/character-state.service';
import { Router } from '@angular/router';
import { signal } from '@angular/core';

describe('NavbarComponent', () => {
  let component: NavbarComponent;
  let authServiceMock: { currentUser: ReturnType<typeof signal<any>> };
  let charStateMock: any;
  let routerMock: { url: string };

  beforeEach(() => {
    authServiceMock = {
      currentUser: signal({
        id: 'u1',
        username: 'testuser',
        has_completed_tutorial: true,
      }),
    };

    charStateMock = {
      dndEdition: signal('2024'),
      toggleEdition: jest.fn(),
    };

    routerMock = {
      url: '/player',
    };

    TestBed.configureTestingModule({
      imports: [NavbarComponent],
      providers: [
        { provide: AuthService, useValue: authServiceMock },
        { provide: CharacterStateService, useValue: charStateMock },
        { provide: Router, useValue: routerMock },
      ],
    });

    const fixture = TestBed.createComponent(NavbarComponent);
    component = fixture.componentInstance;
  });

  it('renders "Player" by default for normal players', () => {
    expect(component.userRoleLabel).toBe('Player');
  });

  it('renders "Administrator" when is_admin is true', () => {
    authServiceMock.currentUser.set({
      id: 'u_admin',
      username: 'admin',
      has_completed_tutorial: true,
      is_admin: true,
    });
    expect(component.userRoleLabel).toBe('Administrator');
  });

  it('renders "Dungeon Master" when user role is dm', () => {
    authServiceMock.currentUser.set({
      id: 'u_dm',
      username: 'dungeonmaster',
      has_completed_tutorial: true,
      role: 'dm',
    });
    expect(component.userRoleLabel).toBe('Dungeon Master');
  });

  it('renders "Dungeon Master" when route is inside /dm', () => {
    routerMock.url = '/dm/campaign/test';
    expect(component.userRoleLabel).toBe('Dungeon Master');
  });
});
