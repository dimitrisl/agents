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
    authServiceSpy.fetchCurrentUser.mockReturnValue(throwError(() => new Error('Invalid token')));

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
});
