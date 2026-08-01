import { Injectable, signal, computed } from '@angular/core';
import { HttpClient, HttpErrorResponse } from '@angular/common/http';
import { Router } from '@angular/router';
import { Observable, tap } from 'rxjs';
import { User, AuthResponse } from '../models/user.model';
import { environment } from '../../../environments/environment';

@Injectable({
  providedIn: 'root',
})
export class AuthService {
  private readonly API_URL = `${environment.apiBaseUrl}/auth`;
  private readonly TOKEN_STORAGE_KEY = 'token';
  private readonly USER_STORAGE_KEY = 'currentUser';

  // Angular Signals for active user state
  readonly currentUser = signal<User | null>(this.readStoredUser());
  readonly token = signal<string | null>(localStorage.getItem(this.TOKEN_STORAGE_KEY));

  readonly isAuthenticated = computed(() => !!this.currentUser() && !!this.token());
  readonly hasToken = computed(() => !!this.token());

  constructor(private http: HttpClient, private router: Router) {
    if (this.token()) {
      this.fetchCurrentUser().subscribe({
        error: (error) => {
          if (this.isAuthFailure(error)) {
            this.logout();
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
      tap((res) => {
        this.persistSession(res);
        this.token.set(res.access_token);
        this.currentUser.set(res.user);
      })
    );
  }

  demoLogin(demoType: string): Observable<AuthResponse> {
    return this.http.post<AuthResponse>(`${this.API_URL}/demo`, { demo_type: demoType }).pipe(
      tap((res) => {
        this.persistSession(res);
        this.token.set(res.access_token);
        this.currentUser.set(res.user);
      })
    );
  }

  register(userData: any): Observable<User> {
    return this.http.post<User>(`${this.API_URL}/register`, userData);
  }

  fetchCurrentUser(): Observable<User> {
    return this.http.get<User>(`${this.API_URL}/me`).pipe(
      tap({
        next: (user) => {
          localStorage.setItem(this.USER_STORAGE_KEY, JSON.stringify(user));
          this.currentUser.set(user);
        },
      })
    );
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
    this.router.navigate(['/login']);
  }

  private persistSession(res: AuthResponse) {
    localStorage.setItem(this.TOKEN_STORAGE_KEY, res.access_token);
    localStorage.setItem(this.USER_STORAGE_KEY, JSON.stringify(res.user));
  }

  private readStoredUser(): User | null {
    const storedUser = localStorage.getItem(this.USER_STORAGE_KEY);
    if (!storedUser) {
      return this.readUserFromToken();
    }

    try {
      return JSON.parse(storedUser) as User;
    } catch {
      localStorage.removeItem(this.USER_STORAGE_KEY);
      return this.readUserFromToken();
    }
  }

  private isAuthFailure(error: unknown): boolean {
    return error instanceof HttpErrorResponse && [401, 403].includes(error.status);
  }

  private readUserFromToken(): User | null {
    const token = localStorage.getItem(this.TOKEN_STORAGE_KEY);
    if (!token) {
      return null;
    }

    try {
      const encodedPayload = token.split('.')[1].replace(/-/g, '+').replace(/_/g, '/');
      const paddedPayload = encodedPayload.padEnd(
        Math.ceil(encodedPayload.length / 4) * 4,
        '='
      );
      const payload = JSON.parse(atob(paddedPayload));
      if (!payload.sub || !payload.username) {
        return null;
      }

      return {
        id: payload.sub,
        username: payload.username,
        email: `${payload.username}@phyrexian.forge`,
        name: payload.username,
        has_completed_tutorial: true,
      };
    } catch {
      return null;
    }
  }
}
