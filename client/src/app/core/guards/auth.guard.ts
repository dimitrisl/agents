import { inject } from '@angular/core';
import { Router, CanActivateFn } from '@angular/router';
import { catchError, map, of } from 'rxjs';
import { AuthService } from '../services/auth.service';

export const authGuard: CanActivateFn = (route, state) => {
  const authService = inject(AuthService);
  const router = inject(Router);

  if (authService.isAuthenticated()) {
    return true;
  }

  if (authService.hasToken()) {
    return authService.fetchCurrentUser().pipe(
      map(() => true),
      catchError((error) => {
        // Only drop session on explicitly rejected auth (401/403)
        if (error.status === 401 || error.status === 403) {
          authService.logout();
          return of(router.createUrlTree(['/login']));
        }
        // For network errors or 5xx, allow access to proceed with cached local data
        // or let the route fail gracefully without destroying the user's session
        return of(true);
      })
    );
  }

  return router.createUrlTree(['/login']);
};
