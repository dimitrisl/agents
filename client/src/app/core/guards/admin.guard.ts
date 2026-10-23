import { inject } from '@angular/core';
import { Router, CanActivateFn } from '@angular/router';
import { catchError, map, of } from 'rxjs';
import { AuthService } from '../services/auth.service';

export const adminGuard: CanActivateFn = (route, state) => {
  const authService = inject(AuthService);
  const router = inject(Router);

  const user = authService.currentUser();
  if (user) {
    if (user.is_admin) {
      return true;
    }
    return router.createUrlTree(['/campaigns']);
  }

  if (authService.hasToken()) {
    return authService.fetchCurrentUser().pipe(
      map((fetchedUser) => {
        if (fetchedUser && fetchedUser.is_admin) {
          return true;
        }
        return router.createUrlTree(['/campaigns']);
      }),
      catchError(() => {
        return of(router.createUrlTree(['/campaigns']));
      })
    );
  }

  return router.createUrlTree(['/login']);
};
