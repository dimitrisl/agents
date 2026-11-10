import { Injectable, signal } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable, catchError, map, switchMap, tap, throwError } from 'rxjs';
import { environment } from '../../../environments/environment';
import {
  BestiaryCreateRequest,
  BestiaryDeleteResponse,
  BestiaryFilterParams,
  BestiaryMonster,
  BestiaryUpdateRequest,
  BestiaryVisibilityResponse,
} from '../models/bestiary.model';

@Injectable({
  providedIn: 'root',
})
export class BestiaryService {
  private readonly baseUrl = `${environment.apiBaseUrl}/bestiary`;

  // Reactive State Signals
  readonly monsters = signal<BestiaryMonster[]>([]);
  readonly isLoading = signal<boolean>(false);
  readonly error = signal<string | null>(null);
  readonly selectedMonster = signal<BestiaryMonster | null>(null);

  constructor(private http: HttpClient) {}

  /**
   * Search and filter Bestiary monsters from backend API.
   * Updates `monsters`, `isLoading`, and `error` signals.
   */
  getMonsters(filters: BestiaryFilterParams = {}): Observable<BestiaryMonster[]> {
    this.isLoading.set(true);
    this.error.set(null);

    let params = new HttpParams();

    if (filters.edition && filters.edition !== 'all') {
      params = params.set('edition', filters.edition.trim());
    }
    if (filters.search && filters.search.trim()) {
      params = params.set('search', filters.search.trim());
    }
    if (filters.cr && filters.cr.trim() && filters.cr !== 'all') {
      params = params.set('cr', filters.cr.trim());
    }
    if (filters.monster_type && filters.monster_type.trim() && filters.monster_type !== 'all') {
      params = params.set('monster_type', filters.monster_type.trim());
    }
    if (filters.include_official !== undefined) {
      params = params.set('include_official', filters.include_official.toString());
    }
    if (filters.include_mine !== undefined) {
      params = params.set('include_mine', filters.include_mine.toString());
    }
    if (filters.include_community !== undefined) {
      params = params.set('include_community', filters.include_community.toString());
    }

    return this.http.get<BestiaryMonster[]>(this.baseUrl, { params }).pipe(
      map((monsters) => {
        // Apply client-side CR range refinement if cr_min or cr_max are set
        if (filters.cr_min !== undefined || filters.cr_max !== undefined) {
          return monsters.filter((m) => {
            const num = m.cr_numeric ?? 0;
            if (filters.cr_min !== undefined && num < filters.cr_min) return false;
            if (filters.cr_max !== undefined && num > filters.cr_max) return false;
            return true;
          });
        }
        return monsters;
      }),
      tap((monsters) => {
        this.monsters.set(monsters);
        this.isLoading.set(false);
      }),
      catchError((err) => {
        const errorMsg = err?.error?.detail || 'Failed to load monsters from bestiary.';
        this.error.set(errorMsg);
        this.isLoading.set(false);
        return throwError(() => err);
      })
    );
  }

  /**
   * Fetch single monster by ID.
   */
  getMonsterById(id: string): Observable<BestiaryMonster> {
    return this.http.get<BestiaryMonster>(`${this.baseUrl}/${encodeURIComponent(id)}`).pipe(
      tap((monster) => this.selectedMonster.set(monster))
    );
  }

  /**
   * Create a new custom monster.
   */
  createMonster(data: BestiaryCreateRequest): Observable<BestiaryMonster> {
    return this.http.post<BestiaryMonster>(this.baseUrl, data).pipe(
      tap((newMonster) => {
        this.monsters.update((list) => [newMonster, ...list]);
      })
    );
  }

  /**
   * Clone an existing monster (official or custom) via `based_on`.
   */
  cloneMonster(
    sourceId: string,
    overrides: Partial<BestiaryCreateRequest> = {}
  ): Observable<BestiaryMonster> {
    return this.getMonsterById(sourceId).pipe(
      switchMap((source) => {
        const payload: BestiaryCreateRequest = {
          ...source,
          ...overrides,
          name: overrides.name || `${source.name} (Copy)`,
          based_on: sourceId,
        };
        return this.createMonster(payload);
      })
    );
  }

  /**
   * Update an existing custom monster owned by current DM.
   */
  updateMonster(id: string, data: BestiaryUpdateRequest): Observable<BestiaryMonster> {
    return this.http.put<BestiaryMonster>(`${this.baseUrl}/${encodeURIComponent(id)}`, data).pipe(
      tap((updated) => {
        this.monsters.update((list) =>
          list.map((m) => (m.id === id ? updated : m))
        );
        if (this.selectedMonster()?.id === id) {
          this.selectedMonster.set(updated);
        }
      })
    );
  }

  /**
   * Toggle custom monster visibility (is_public).
   */
  toggleVisibility(id: string, is_public: boolean): Observable<BestiaryVisibilityResponse> {
    return this.http
      .patch<BestiaryVisibilityResponse>(`${this.baseUrl}/${encodeURIComponent(id)}/visibility`, {
        is_public,
      })
      .pipe(
        tap((res) => {
          this.monsters.update((list) =>
            list.map((m) => (m.id === id ? { ...m, is_public: res.is_public } : m))
          );
          const current = this.selectedMonster();
          if (current?.id === id) {
            this.selectedMonster.set({ ...current, is_public: res.is_public });
          }
        })
      );
  }

  /**
   * Delete an existing custom monster owned by current DM.
   */
  deleteMonster(id: string): Observable<BestiaryDeleteResponse> {
    return this.http
      .delete<BestiaryDeleteResponse>(`${this.baseUrl}/${encodeURIComponent(id)}`)
      .pipe(
        tap(() => {
          this.monsters.update((list) => list.filter((m) => m.id !== id));
          if (this.selectedMonster()?.id === id) {
            this.selectedMonster.set(null);
          }
        })
      );
  }
}
