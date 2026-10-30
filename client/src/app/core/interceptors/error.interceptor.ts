import { HttpContextToken, HttpErrorResponse, HttpInterceptorFn } from '@angular/common/http';
import { inject } from '@angular/core';
import { catchError, throwError } from 'rxjs';
import { RollToastService } from '../services/roll-toast.service';

/**
 * Opt a request out of the global error toast, for calls that retry on their own
 * or fail harmlessly in the background:
 * `this.http.post(url, body, { context: new HttpContext().set(SILENT_HTTP_ERRORS, true) })`
 */
export const SILENT_HTTP_ERRORS = new HttpContextToken<boolean>(() => false);

/**
 * Surfaces failures no component can fix (offline, timeouts, rate limits, server
 * errors) so they never fail silently. Business errors (400/404/409/422) and auth
 * (401/403) are left to the caller and the auth flow.
 *
 * The error is always re-thrown. The toast has a single slot, so a caller that
 * shows its own, more specific message in its error handler replaces this one.
 */
export const errorInterceptor: HttpInterceptorFn = (req, next) => {
  const toast = inject(RollToastService);

  return next(req).pipe(
    catchError((err: unknown) => {
      if (err instanceof HttpErrorResponse && !req.context.get(SILENT_HTTP_ERRORS)) {
        const message = describeHttpError(err);
        if (message) {
          toast.showMessage(message.title, message.body);
        }
      }
      return throwError(() => err);
    })
  );
};

export function describeHttpError(err: HttpErrorResponse): { title: string; body: string } | null {
  const detail = typeof err.error?.detail === 'string' ? err.error.detail : '';

  if (err.status === 0) {
    return {
      title: '📡 CONNECTION LOST',
      body: 'Could not reach the Forge server. Check your connection and try again.',
    };
  }
  if (err.status === 408 || err.status === 504) {
    return { title: '⏳ REQUEST TIMED OUT', body: detail || 'The server took too long to answer. Try again.' };
  }
  if (err.status === 413) {
    return { title: '📦 TOO LARGE', body: detail || 'That file or request is too large.' };
  }
  if (err.status === 429) {
    return {
      title: '🐢 SLOW DOWN',
      body: detail || 'Too many requests in a short time. Wait a moment and try again.',
    };
  }
  if (err.status >= 500) {
    return {
      title: '⚠️ SERVER ERROR',
      body: detail || 'Something went wrong on the server. Try again in a moment.',
    };
  }
  return null;
}

/**
 * For a caller's error handler: true when the interceptor already told the user
 * (offline, rate limit, server error), so the caller only adds its own message
 * for business errors such as a 400 with a `detail`.
 */
export function isReportedGlobally(err: unknown): boolean {
  return err instanceof HttpErrorResponse && describeHttpError(err) !== null;
}
