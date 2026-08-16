import { Injectable, signal, computed } from '@angular/core';
import { HttpClient, HttpErrorResponse } from '@angular/common/http';
import { Router } from '@angular/router';
import { Observable, shareReplay, tap } from 'rxjs';
import { User, AuthResponse } from '../models/user.model';
import { CharacterStateService } from './character-state.service';
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

  // The boot-time session check and the route guard both ask for the current
  // user, so they share one request instead of racing two identical ones.
  private currentUser$: Observable<User> | null = null;

  constructor(
    private http: HttpClient,
    private router: Router,
    private charState: CharacterStateService
  ) {
    if (this.token()) {
      this.fetchCurrentUser().subscribe({
        error: (error) => {
          if (this.isAuthFailure(error)) {
            this.logout();
          }
          this.authStatus.set('anonymous');
        },
      });
    }
  }

  login(credentials: any): Observable<AuthResponse> {
    const formData = new FormData();
    formData.append('username', credentials.username);
    formData.append('password', credentials.password);

    return this.http.post<AuthResponse>(`${this.API_URL}/login`, formData).pipe(
      tap((res) => {
        this.persistSession(res);
        this.token.set(res.access_token);
        this.currentUser.set(res.user);
        this.authStatus.set('authenticated');
      })
    );
  }

  demoLogin(demoType: string): Observable<AuthResponse> {
    return this.http.post<AuthResponse>(`${this.API_URL}/demo`, { demo_type: demoType }).pipe(
      tap((res) => {
        this.persistSession(res);
        this.token.set(res.access_token);
        this.currentUser.set(res.user);
        this.authStatus.set('authenticated');
      })
    );
  }

  register(userData: any): Observable<User> {
    return this.http.post<User>(`${this.API_URL}/register`, userData);
  }

  fetchCurrentUser(): Observable<User> {
    if (!this.currentUser$) {
      this.currentUser$ = this.http.get<User>(`${this.API_URL}/me`).pipe(
        tap({
          // Cleared once settled, so this only ever collapses concurrent callers
          // and a later check still re-validates the session against the server.
          next: (user) => {
            this.currentUser$ = null;
            localStorage.setItem(this.USER_STORAGE_KEY, JSON.stringify(user));
            this.currentUser.set(user);
            this.authStatus.set('authenticated');
          },
          error: () => {
            this.currentUser$ = null;
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
    localStorage.removeItem(this.TOKEN_STORAGE_KEY);
    localStorage.removeItem(this.USER_STORAGE_KEY);
    this.token.set(null);
    this.currentUser.set(null);
    this.authStatus.set('anonymous');
    this.currentUser$ = null;
    // The vault is cached for the whole session, so it has to be dropped here or
    // the next user to sign in would open onto the previous one's heroes.
    this.charState.reset();
    this.router.navigate(['/login']);
  }

  private persistSession(res: AuthResponse) {
    localStorage.setItem(this.TOKEN_STORAGE_KEY, res.access_token);
    localStorage.setItem(this.USER_STORAGE_KEY, JSON.stringify(res.user));
  }

  private isAuthFailure(error: unknown): boolean {
    return error instanceof HttpErrorResponse && [401, 403].includes(error.status);
  }
}
