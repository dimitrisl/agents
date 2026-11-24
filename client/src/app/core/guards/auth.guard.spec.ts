import { TestBed } from '@angular/core/testing';
import { Router, UrlTree } from '@angular/router';
import { of, throwError } from 'rxjs';
import { authGuard } from './auth.guard';
import { AuthService } from '../services/auth.service';

describe('authGuard', () => {
  let authServiceSpy: jest.Mocked<AuthService>;
  let routerSpy: jest.Mocked<Router>;
  let dummyRoute: any = {};
  let dummyState: any = {};

  beforeEach(() => {
    authServiceSpy = {
      isAuthenticated: jest.fn(),
      hasToken: jest.fn(),
      fetchCurrentUser: jest.fn(),
      logout: jest.fn(),
    } as unknown as jest.Mocked<AuthService>;

    routerSpy = {
      createUrlTree: jest.fn((commands) => `UrlTree(${commands})` as unknown as UrlTree),
    } as unknown as jest.Mocked<Router>;

    TestBed.configureTestingModule({
      providers: [
        { provide: AuthService, useValue: authServiceSpy },
        { provide: Router, useValue: routerSpy },
      ],
    });
  });

  const runGuard = () => TestBed.runInInjectionContext(() => authGuard(dummyRoute, dummyState));

  it('should allow access if already authenticated', () => {
    authServiceSpy.isAuthenticated.mockReturnValue(true);
    const result = runGuard();
    expect(result).toBe(true);
  });

  it('should fetch user and allow access if token exists', (done) => {
    authServiceSpy.isAuthenticated.mockReturnValue(false);
    authServiceSpy.hasToken.mockReturnValue(true);
    authServiceSpy.fetchCurrentUser.mockReturnValue(of({} as any));

    const result$ = runGuard() as any;
    result$.subscribe((res: any) => {
      expect(res).toBe(true);
      done();
    });
  });

  it('should logout and redirect if token validation fails', (done) => {
    authServiceSpy.isAuthenticated.mockReturnValue(false);
    authServiceSpy.hasToken.mockReturnValue(true);
    authServiceSpy.fetchCurrentUser.mockReturnValue(throwError(() => {
      const err = new Error('Invalid token') as any;
      err.status = 401;
      return err;
    }));

    const result$ = runGuard() as any;
    result$.subscribe((res: any) => {
      expect(authServiceSpy.logout).toHaveBeenCalled();
      expect(routerSpy.createUrlTree).toHaveBeenCalledWith(['/login']);
      expect(res).toBe('UrlTree(/login)');
      done();
    });
  });

  it('should redirect to login if not authenticated and no token', () => {
    authServiceSpy.isAuthenticated.mockReturnValue(false);
    authServiceSpy.hasToken.mockReturnValue(false);

    const result = runGuard();
    expect(routerSpy.createUrlTree).toHaveBeenCalledWith(['/login']);
    expect(result).toBe('UrlTree(/login)');
  });

  it('should redirect must_change_password users to /settings when navigating elsewhere', () => {
    authServiceSpy.isAuthenticated.mockReturnValue(true);
    (authServiceSpy as any).mustChangePassword = jest.fn().mockReturnValue(true);
    dummyState = { url: '/campaigns' };

    const result = runGuard();
    expect(routerSpy.createUrlTree).toHaveBeenCalledWith(['/settings']);
    expect(result).toBe('UrlTree(/settings)');
  });

  it('should allow must_change_password users on /settings', () => {
    authServiceSpy.isAuthenticated.mockReturnValue(true);
    (authServiceSpy as any).mustChangePassword = jest.fn().mockReturnValue(true);
    dummyState = { url: '/settings' };

    const result = runGuard();
    expect(result).toBe(true);
  });

  it('should redirect must_change_password users from lookalike /settings-other paths', () => {
    authServiceSpy.isAuthenticated.mockReturnValue(true);
    (authServiceSpy as any).mustChangePassword = jest.fn().mockReturnValue(true);
    dummyState = { url: '/settings-other' };

    const result = runGuard();
    expect(routerSpy.createUrlTree).toHaveBeenCalledWith(['/settings']);
    expect(result).toBe('UrlTree(/settings)');
  });
});
