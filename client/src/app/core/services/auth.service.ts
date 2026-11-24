import { Injectable, signal, computed } from '@angular/core';
import { HttpClient, HttpContext, HttpErrorResponse } from '@angular/common/http';
import { Router } from '@angular/router';
import { Observable, shareReplay, tap } from 'rxjs';
import {
  User,
  AuthResponse,
  AuthProvidersResponse,
  ChangePasswordPayload,
} from '../models/user.model';
import { CharacterStateService } from './character-state.service';
import { SILENT_HTTP_ERRORS } from '../interceptors/error.interceptor';
import { environment } from '../../../environments/environment';

type AuthStatus = 'checking' | 'authenticated' | 'anonymous';

@Injectable({
  providedIn: 'root',
})
export class AuthService {
  private readonly API_URL = `${environment.apiBaseUrl}/auth`;
  private readonly TOKEN_STORAGE_KEY = 'token';
  private readonly USER_STORAGE_KEY = 'currentUser';

  // Angular Signals for active user state. A cached user is only used after the
  // token is validated with the API, so the shell never renders as logged-in
  // while the guard is about to reject the session.
  readonly currentUser = signal<User | null>(null);
  readonly token = signal<string | null>(localStorage.getItem(this.TOKEN_STORAGE_KEY));
  readonly authStatus = signal<AuthStatus>(this.token() ? 'checking' : 'anonymous');

  readonly isAuthenticated = computed(
    () => this.authStatus() === 'authenticated' && !!this.currentUser() && !!this.token()
  );
  readonly hasToken = computed(() => !!this.token());
  readonly mustChangePassword = computed(() => Boolean(this.currentUser()?.must_change_password));

  // The boot-time session check and the route guard both ask for the current
  // user, so they share one request instead of racing two identical ones.
  private currentUser$: Observable<User> | null = null;
  private sessionGeneration = 0;

  constructor(
    private http: HttpClient,
    private router: Router,
    private charState: CharacterStateService
  ) {
    const isOAuthCallback =
      typeof window !== 'undefined' &&
      window.location.pathname.replace(/\/+$/, '') === '/auth/callback';
    if (this.token() && !isOAuthCallback) {
      const bootGen = this.sessionGeneration;
      this.fetchCurrentUser().subscribe({
        error: (error) => {
          if (bootGen === this.sessionGeneration && this.isAuthFailure(error)) {
            this.logout();
            this.authStatus.set('anonymous');
          }
        },
      });
    }
  }

  login(credentials: any): Observable<AuthResponse> {
    const formData = new FormData();
    formData.append('username', credentials.username);
    formData.append('password', credentials.password);

    return this.http.post<AuthResponse>(`${this.API_URL}/login`, formData).pipe(
      tap((res) => this.applyAuthSession(res))
    );
  }

  demoLogin(demoType: string): Observable<AuthResponse> {
    return this.http.post<AuthResponse>(`${this.API_URL}/demo`, { demo_type: demoType }).pipe(
      tap((res) => this.applyAuthSession(res))
    );
  }

  getProviders(): Observable<AuthProvidersResponse> {
    return this.http.get<AuthProvidersResponse>(`${this.API_URL}/providers`, {
      context: new HttpContext().set(SILENT_HTTP_ERRORS, true),
    });
  }

  changePassword(payload: ChangePasswordPayload): Observable<AuthResponse> {
    return this.http.post<AuthResponse>(`${this.API_URL}/change-password`, payload).pipe(
      tap((res) => this.applyAuthSession(res))
    );
  }

  exchangeDiscordCode(code: string): Observable<AuthResponse> {
    const prevUserId = this.currentUser()?.id ?? this.readCachedUser()?.id ?? null;
    this.sessionGeneration++;
    this.currentUser$ = null;
    localStorage.removeItem(this.TOKEN_STORAGE_KEY);
    localStorage.removeItem(this.USER_STORAGE_KEY);
    this.token.set(null);
    this.currentUser.set(null);
    this.authStatus.set('anonymous');
    if (prevUserId) {
      this.charState.reset();
    }
    this.clearOfflineServiceWorkerDataCaches();
    return this.http.post<AuthResponse>(`${this.API_URL}/discord/exchange`, { code }).pipe(
      tap((res) => this.applyAuthSession(res))
    );
  }

  startDiscordLogin(): void {
    window.location.assign(`${this.API_URL}/discord/login`);
  }

  private applyAuthSession(res: AuthResponse): void {
    const prevUserId = this.currentUser()?.id ?? this.readCachedUser()?.id ?? null;
    const nextUserId = res.user?.id ?? null;
    if (prevUserId && prevUserId !== nextUserId) {
      this.charState.reset();
      this.clearOfflineServiceWorkerDataCaches();
    }
    this.sessionGeneration++;
    this.currentUser$ = null;
    this.persistSession(res);
    this.token.set(res.access_token);
    this.currentUser.set(res.user);
    this.authStatus.set('authenticated');
  }

  register(userData: any): Observable<User> {
    return this.http.post<User>(`${this.API_URL}/register`, userData);
  }

  fetchCurrentUser(): Observable<User> {
    if (!this.currentUser$) {
      const reqGen = this.sessionGeneration;
      this.currentUser$ = this.http.get<User>(`${this.API_URL}/me`).pipe(
        tap({
          // Cleared once settled, so this only ever collapses concurrent callers
          // and a later check still re-validates the session against the server.
          next: (user) => {
            this.currentUser$ = null;
            if (reqGen !== this.sessionGeneration) return;
            localStorage.setItem(this.USER_STORAGE_KEY, JSON.stringify(user));
            this.currentUser.set(user);
            this.authStatus.set('authenticated');
          },
          error: (error) => {
            this.currentUser$ = null;
            if (reqGen !== this.sessionGeneration) return;
            if (!this.isAuthFailure(error) && this.token()) {
              const cached = this.readCachedUser();
              if (cached) {
                this.currentUser.set(cached);
                this.authStatus.set('authenticated');
                return;
              }
            }
            this.currentUser.set(null);
            this.authStatus.set('anonymous');
          },
        }),
        shareReplay(1)
      );
    }
    return this.currentUser$;
  }

  updateTutorial(completed: boolean): Observable<User> {
    return this.http
      .put<User>(`${this.API_URL}/tutorial`, { has_completed_tutorial: completed })
      .pipe(
        tap((user) => {
          localStorage.setItem(this.USER_STORAGE_KEY, JSON.stringify(user));
          this.currentUser.set(user);
        })
      );
  }

  logout() {
    this.sessionGeneration++;
    localStorage.removeItem(this.TOKEN_STORAGE_KEY);
    localStorage.removeItem(this.USER_STORAGE_KEY);
    localStorage.removeItem('phyrexian_forge_temp_hero');
    localStorage.removeItem('phyrexian_forge_ai_draft');
    localStorage.removeItem('phyrexian_forge_pending_generation');
    this.token.set(null);
    this.currentUser.set(null);
    this.authStatus.set('anonymous');
    this.currentUser$ = null;
    // The vault is cached for the whole session, so it has to be dropped here or
    // the next user to sign in would open onto the previous one's heroes.
    this.charState.reset();
    this.clearOfflineServiceWorkerDataCaches();
    this.router.navigate(['/login']);
  }

  private clearOfflineServiceWorkerDataCaches(): void {
    if (typeof caches === 'undefined' || typeof caches.keys !== 'function') return;
    caches
      .keys()
      .then((keys) => {
        for (const key of keys) {
          if (key.includes(':data:')) {
            void caches.delete(key);
          }
        }
      })
      .catch(() => {});
  }

  private readCachedUser(): User | null {
    try {
      const raw = localStorage.getItem(this.USER_STORAGE_KEY);
      if (!raw) return null;
      const parsed = JSON.parse(raw) as User;
      return parsed && typeof parsed.username === 'string' ? parsed : null;
    } catch {
      return null;
    }
  }

  private persistSession(res: AuthResponse) {
    localStorage.setItem(this.TOKEN_STORAGE_KEY, res.access_token);
    localStorage.setItem(this.USER_STORAGE_KEY, JSON.stringify(res.user));
  }

  private isAuthFailure(error: unknown): boolean {
    return error instanceof HttpErrorResponse && [401, 403].includes(error.status);
  }
}
