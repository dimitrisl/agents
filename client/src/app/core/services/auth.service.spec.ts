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
    it('should clear state, clear local storage, and navigate to login', () => {
      localStorage.setItem('token', 'fake-token');
      service.logout();

      expect(service.token()).toBeNull();
      expect(service.currentUser()).toBeNull();
      expect(service.authStatus()).toBe('anonymous');
      expect(localStorage.getItem('token')).toBeNull();
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
  });
});
