import { inject } from '@angular/core';
import { Router, CanActivateFn } from '@angular/router';
import { catchError, map, of } from 'rxjs';
import { AuthService } from '../services/auth.service';

export const authGuard: CanActivateFn = (_route, state) => {
  const authService = inject(AuthService);
  const router = inject(Router);

  const resolveAllowed = () => {
    const url = state?.url || '';
    if (authService.mustChangePassword?.() && !/^\/settings(?:[?#]|$)/.test(url)) {
      return router.createUrlTree(['/settings']);
    }
    return true;
  };

  if (authService.isAuthenticated()) {
    return resolveAllowed();
  }

  if (authService.hasToken()) {
    return authService.fetchCurrentUser().pipe(
      map(() => resolveAllowed()),
      catchError((error) => {
        // Only drop session on explicitly rejected auth (401/403)
        if (error.status === 401 || error.status === 403) {
          authService.logout();
          return of(router.createUrlTree(['/login']));
        }
        // For network errors or 5xx, proceed offline only if AuthService restored a cached user
        if (authService.isAuthenticated()) {
          return of(resolveAllowed());
        }
        return of(router.createUrlTree(['/login']));
      })
    );
  }

  return router.createUrlTree(['/login']);
};
