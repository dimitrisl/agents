import { Injectable, signal, computed } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Router } from '@angular/router';
import { Observable, tap } from 'rxjs';
import { User, AuthResponse } from '../models/user.model';
import { environment } from '../../../environments/environment';

@Injectable({
  providedIn: 'root',
})
export class AuthService {
  private readonly API_URL = `${environment.apiBaseUrl}/auth`;

  // Angular Signals for active user state
  readonly currentUser = signal<User | null>(null);
  readonly token = signal<string | null>(localStorage.getItem('token'));

  readonly isAuthenticated = computed(() => !!this.currentUser() && !!this.token());

  constructor(private http: HttpClient, private router: Router) {
    if (this.token()) {
      this.fetchCurrentUser().subscribe({
        error: () => this.logout(),
      });
    }
  }

  login(credentials: any): Observable<AuthResponse> {
    const formData = new FormData();
    formData.append('username', credentials.username);
    formData.append('password', credentials.password);

    return this.http.post<AuthResponse>(`${this.API_URL}/login`, formData).pipe(
      tap((res) => {
        localStorage.setItem('token', res.access_token);
        this.token.set(res.access_token);
        this.currentUser.set(res.user);
      })
    );
  }

  demoLogin(demoType: string): Observable<AuthResponse> {
    return this.http.post<AuthResponse>(`${this.API_URL}/demo`, { demo_type: demoType }).pipe(
      tap((res) => {
        localStorage.setItem('token', res.access_token);
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
        next: (user) => this.currentUser.set(user),
        error: () => this.logout(),
      })
    );
  }

  updateTutorial(completed: boolean): Observable<User> {
    return this.http
      .put<User>(`${this.API_URL}/tutorial`, { has_completed_tutorial: completed })
      .pipe(tap((user) => this.currentUser.set(user)));
  }

  logout() {
    localStorage.removeItem('token');
    this.token.set(null);
    this.currentUser.set(null);
    this.router.navigate(['/login']);
  }
}
