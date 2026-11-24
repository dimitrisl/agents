import { TestBed, fakeAsync, tick } from '@angular/core/testing';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { provideHttpClient } from '@angular/common/http';
import { Router } from '@angular/router';
import { AuthService } from './auth.service';
import { CharacterStateService } from './character-state.service';
import { environment } from '../../../environments/environment';
import { User } from '../models/user.model';

describe('AuthService', () => {
  let service: AuthService;
  let httpTestingController: HttpTestingController;
  let routerSpy: jest.Mocked<Router>;
  let charStateSpy: jest.Mocked<CharacterStateService>;

  const mockUser: User = { id: '1', username: 'testuser', email: 'test@example.com', role: 'player', created_at: '2023-01-01', has_completed_tutorial: false };

  beforeEach(() => {
    localStorage.clear();

    routerSpy = {
      navigate: jest.fn(),
    } as unknown as jest.Mocked<Router>;

    charStateSpy = {
      reset: jest.fn(),
    } as unknown as jest.Mocked<CharacterStateService>;

    TestBed.configureTestingModule({
      providers: [
        AuthService,
        provideHttpClient(),
        provideHttpClientTesting(),
        { provide: Router, useValue: routerSpy },
        { provide: CharacterStateService, useValue: charStateSpy },
      ],
    });

    service = TestBed.inject(AuthService);
    httpTestingController = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    httpTestingController.verify();
  });

  it('should be created in anonymous state', () => {
    expect(service).toBeTruthy();
    expect(service.authStatus()).toBe('anonymous');
    expect(service.isAuthenticated()).toBe(false);
  });

  describe('login', () => {
    it('should authenticate user and store token', () => {
      service.login({ username: 'test', password: 'password' }).subscribe();

      const req = httpTestingController.expectOne(`${environment.apiBaseUrl}/auth/login`);
      expect(req.request.method).toBe('POST');
      req.flush({ access_token: 'fake-token', user: mockUser });

      expect(service.token()).toBe('fake-token');
      expect(service.currentUser()).toEqual(mockUser);
      expect(service.authStatus()).toBe('authenticated');
      expect(localStorage.getItem('token')).toBe('fake-token');
    });
  });

  describe('demoLogin', () => {
    it('should authenticate demo user and store token', () => {
      service.demoLogin('player').subscribe();

      const req = httpTestingController.expectOne(`${environment.apiBaseUrl}/auth/demo`);
      expect(req.request.method).toBe('POST');
      expect(req.request.body).toEqual({ demo_type: 'player' });
      req.flush({ access_token: 'demo-token', user: mockUser });

      expect(service.token()).toBe('demo-token');
      expect(service.currentUser()).toEqual(mockUser);
      expect(service.authStatus()).toBe('authenticated');
    });
  });

  describe('logout', () => {
    it('should clear state, clear local storage including forge keys, and navigate to login', () => {
      localStorage.setItem('token', 'fake-token');
      localStorage.setItem('phyrexian_forge_temp_hero', '{"char_name":"Hero"}');
      localStorage.setItem('phyrexian_forge_ai_draft', '{"aiClass":"Wizard"}');
      localStorage.setItem('phyrexian_forge_pending_generation', '123456789');
      service.logout();

      expect(service.token()).toBeNull();
      expect(service.currentUser()).toBeNull();
      expect(service.authStatus()).toBe('anonymous');
      expect(localStorage.getItem('token')).toBeNull();
      expect(localStorage.getItem('phyrexian_forge_temp_hero')).toBeNull();
      expect(localStorage.getItem('phyrexian_forge_ai_draft')).toBeNull();
      expect(localStorage.getItem('phyrexian_forge_pending_generation')).toBeNull();
      expect(charStateSpy.reset).toHaveBeenCalled();
      expect(routerSpy.navigate).toHaveBeenCalledWith(['/login']);
    });
  });

  describe('fetchCurrentUser', () => {
    it('should fetch user and share replay for concurrent requests', () => {
      let reqCount = 0;
      service.fetchCurrentUser().subscribe(() => reqCount++);
      service.fetchCurrentUser().subscribe(() => reqCount++);

      const req = httpTestingController.expectOne(`${environment.apiBaseUrl}/auth/me`);
      req.flush(mockUser);

      expect(reqCount).toBe(2);
      expect(service.currentUser()).toEqual(mockUser);
      expect(service.authStatus()).toBe('authenticated');
    });

    it('should handle auth failure gracefully', () => {
      service.fetchCurrentUser().subscribe({
        error: () => {}
      });

      const req = httpTestingController.expectOne(`${environment.apiBaseUrl}/auth/me`);
      req.flush('Unauthorized', { status: 401, statusText: 'Unauthorized' });

      expect(service.currentUser()).toBeNull();
      expect(service.authStatus()).toBe('anonymous');
    });

    it('restores cached user on transient 5xx failure when token exists', () => {
      localStorage.setItem('currentUser', JSON.stringify(mockUser));
      service.token.set('valid-token');

      service.fetchCurrentUser().subscribe({
        error: () => {}
      });

      const req = httpTestingController.expectOne(`${environment.apiBaseUrl}/auth/me`);
      req.flush('Server Error', { status: 503, statusText: 'Service Unavailable' });

      expect(service.currentUser()).toEqual(mockUser);
      expect(service.authStatus()).toBe('authenticated');
      expect(service.isAuthenticated()).toBe(true);
    });
  });

  describe('auth lifecycle (#266)', () => {
    it('fetches available auth providers', () => {
      let providersRes: any;
      service.getProviders().subscribe((res) => (providersRes = res));

      const req = httpTestingController.expectOne(`${environment.apiBaseUrl}/auth/providers`);
      expect(req.request.method).toBe('GET');
      req.flush({ local: true, discord: true });

      expect(providersRes).toEqual({ local: true, discord: true });
    });

    it('rotates token and clears must_change_password on changePassword()', () => {
      const updatedUser: User = { ...mockUser, must_change_password: false, has_password: true };
      service.currentUser.set({ ...mockUser, must_change_password: true });
      expect(service.mustChangePassword()).toBe(true);

      service.changePassword({ current_password: 'old-temp-password', new_password: 'NewStrongPassword99!' }).subscribe();

      const req = httpTestingController.expectOne(`${environment.apiBaseUrl}/auth/change-password`);
      expect(req.request.method).toBe('POST');
      req.flush({ access_token: 'rotated-token', token_type: 'bearer', user: updatedUser });

      expect(service.token()).toBe('rotated-token');
      expect(localStorage.getItem('token')).toBe('rotated-token');
      expect(service.mustChangePassword()).toBe(false);
    });

    it('exchanges Discord OAuth handoff code for session token', () => {
      service.exchangeDiscordCode('handoff-123').subscribe();

      const req = httpTestingController.expectOne(`${environment.apiBaseUrl}/auth/discord/exchange`);
      expect(req.request.method).toBe('POST');
      expect(req.request.body).toEqual({ code: 'handoff-123' });
      req.flush({ access_token: 'discord-jwt', token_type: 'bearer', user: mockUser });

      expect(service.token()).toBe('discord-jwt');
      expect(service.authStatus()).toBe('authenticated');
    });

    it('ignores late stale /auth/me 401 and 200 responses after exchangeDiscordCode supersedes session', () => {
      localStorage.setItem('token', 'expired-prev-token');
      const lateAuth = new AuthService(
        (service as any).http,
        routerSpy,
        charStateSpy
      );

      // Boot constructor issued GET /auth/me for 'expired-prev-token'
      const bootMeReq = httpTestingController.expectOne(`${environment.apiBaseUrl}/auth/me`);

      const discordUser: User = {
        id: 'discord_user_99',
        username: 'jace_discord',
        has_completed_tutorial: false,
      };
      lateAuth.exchangeDiscordCode('fresh-code').subscribe();
      const exReq = httpTestingController.expectOne(`${environment.apiBaseUrl}/auth/discord/exchange`);
      exReq.flush({ access_token: 'fresh-discord-jwt', token_type: 'bearer', user: discordUser });

      // Stale boot /auth/me now fails with 401: must NOT wipe the new Discord session
      bootMeReq.flush('Expired', { status: 401, statusText: 'Unauthorized' });

      expect(lateAuth.token()).toBe('fresh-discord-jwt');
      expect(lateAuth.currentUser()).toEqual(discordUser);
      expect(lateAuth.authStatus()).toBe('authenticated');
      expect(charStateSpy.reset).not.toHaveBeenCalled();
      expect(routerSpy.navigate).not.toHaveBeenCalledWith(['/login']);
    });

    it('ignores late stale /auth/me 200 user payload if session already changed', () => {
      localStorage.setItem('token', 'old-user-token');
      const lateAuth = new AuthService(
        (service as any).http,
        routerSpy,
        charStateSpy
      );
      const bootMeReq = httpTestingController.expectOne(`${environment.apiBaseUrl}/auth/me`);

      const newUser: User = { id: 'u_new', username: 'new_hero', has_completed_tutorial: true };
      lateAuth.exchangeDiscordCode('fresh-code-2').subscribe();
      const exReq = httpTestingController.expectOne(`${environment.apiBaseUrl}/auth/discord/exchange`);
      exReq.flush({ access_token: 'new-jwt', token_type: 'bearer', user: newUser });

      // Old /auth/me finally resolves with old user: must NOT overwrite currentUser
      bootMeReq.flush({ id: 'u_old', username: 'old_hero', has_completed_tutorial: true });
      expect(lateAuth.currentUser()).toEqual(newUser);
      expect(localStorage.getItem('currentUser')).toContain('new_hero');
    });
  });

  describe('offline Service Worker cache cleanup (#267)', () => {
    it('deletes :data: CacheStorage buckets on logout while keeping app shell caches intact', async () => {
      const originalCachesDescriptor = Object.getOwnPropertyDescriptor(globalThis, 'caches');
      const deletedKeys: string[] = [];
      const mockCaches = {
        keys: jest.fn().mockResolvedValue([
          'ngsw:/:1:assets:app:cache',
          'ngsw:/:data:dynamic:characters-api:cache',
          'ngsw:/:data:dynamic:rules-api:cache',
        ]),
        delete: jest.fn((key: string) => {
          deletedKeys.push(key);
          return Promise.resolve(true);
        }),
      };
      Object.defineProperty(globalThis, 'caches', {
        value: mockCaches,
        configurable: true,
        writable: true,
      });

      try {
        service.logout();
        // Flush microtask queue from caches.keys().then(...)
        await Promise.resolve();
        await Promise.resolve();

        expect(mockCaches.keys).toHaveBeenCalledTimes(1);
        expect(deletedKeys).toEqual([
          'ngsw:/:data:dynamic:characters-api:cache',
          'ngsw:/:data:dynamic:rules-api:cache',
        ]);
      } finally {
        if (originalCachesDescriptor) {
          Object.defineProperty(globalThis, 'caches', originalCachesDescriptor);
        } else {
          delete (globalThis as any).caches;
        }
      }
    });

    it('resets vault state and :data: caches on account switch via login(), but preserves them on same-user changePassword() (#267)', async () => {
      const originalCachesDescriptor = Object.getOwnPropertyDescriptor(globalThis, 'caches');
      const deletedKeys: string[] = [];
      Object.defineProperty(globalThis, 'caches', {
        value: {
          keys: jest.fn().mockResolvedValue(['ngsw:/:data:dynamic:rules-api:cache']),
          delete: jest.fn((key: string) => {
            deletedKeys.push(key);
            return Promise.resolve(true);
          }),
        },
        configurable: true,
        writable: true,
      });

      try {
        // Same-user password change: keeps active vault untouched
        service.currentUser.set(mockUser);
        localStorage.setItem('currentUser', JSON.stringify(mockUser));
        service.changePassword({ new_password: 'NewStrongPassword99!' }).subscribe();
        httpTestingController
          .expectOne(`${environment.apiBaseUrl}/auth/change-password`)
          .flush({ access_token: 'rotated', token_type: 'bearer', user: mockUser });
        expect(charStateSpy.reset).not.toHaveBeenCalled();

        // Logging in as a different user on an active SPA session wipes prior vault & :data: caches
        const userB: User = { id: 'u2', username: 'user_b', has_completed_tutorial: true };
        service.login({ username: 'user_b', password: 'secret' }).subscribe();
        httpTestingController
          .expectOne(`${environment.apiBaseUrl}/auth/login`)
          .flush({ access_token: 'jwt-user-b', token_type: 'bearer', user: userB });

        await Promise.resolve();
        expect(charStateSpy.reset).toHaveBeenCalledTimes(1);
        expect(deletedKeys).toEqual(['ngsw:/:data:dynamic:rules-api:cache']);
      } finally {
        if (originalCachesDescriptor) {
          Object.defineProperty(globalThis, 'caches', originalCachesDescriptor);
        } else {
          delete (globalThis as any).caches;
        }
      }
    });
  });
});
