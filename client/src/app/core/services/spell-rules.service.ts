import { Injectable } from '@angular/core';
import { HttpClient, HttpContext } from '@angular/common/http';
import { Observable, catchError, map, of, shareReplay } from 'rxjs';
import { environment } from '../../../environments/environment';
import { SILENT_HTTP_ERRORS } from '../interceptors/error.interceptor';
import { SpellCastProfile, SpellRulesText, analyzeSpell } from '../rules';

/**
 * Spell rules text, loaded once per edition (one request for the whole list)
 * and turned into cast profiles on demand. Casting must keep working when the
 * rules can't be loaded: lookups then simply return null and no dice are rolled.
 */
@Injectable({ providedIn: 'root' })
export class SpellRulesService {
  private readonly byEdition = new Map<string, Observable<Map<string, SpellRulesText>>>();
  private readonly loaded = new Map<string, Map<string, SpellRulesText>>();
  private readonly profiles = new Map<string, SpellCastProfile>();

  constructor(private http: HttpClient) {}

  /** Starts (or reuses) the one-off load for an edition. */
  load(edition: string): Observable<Map<string, SpellRulesText>> {
    let request = this.byEdition.get(edition);
    if (!request) {
      request = this.http
        .get<SpellRulesText[]>(`${environment.apiBaseUrl}/rules/spells`, {
          params: { edition },
          // A missing spell list only means no automatic dice; don't alarm the player.
          context: new HttpContext().set(SILENT_HTTP_ERRORS, true),
        })
        .pipe(
          map((spells) => {
            const index = new Map(spells.map((spell) => [spell.name.trim().toLowerCase(), spell]));
            this.loaded.set(edition, index);
            return index;
          }),
          catchError(() => {
            this.byEdition.delete(edition); // try again next time
            return of(new Map<string, SpellRulesText>());
          }),
          shareReplay(1)
        );
      this.byEdition.set(edition, request);
    }
    return request;
  }

  profile(name: string, edition: string): Observable<SpellCastProfile | null> {
    return this.load(edition).pipe(map(() => this.profileNow(name, edition)));
  }

  /** Synchronous lookup once `load(edition)` has finished; null until then. */
  profileNow(name: string, edition: string): SpellCastProfile | null {
    const key = `${edition}|${name.trim().toLowerCase()}`;
    const cached = this.profiles.get(key);
    if (cached) return cached;
    const text = this.loaded.get(edition)?.get(name.trim().toLowerCase());
    if (!text) return null;
    const profile = analyzeSpell(text);
    this.profiles.set(key, profile);
    return profile;
  }
}
