import { Injectable, signal, computed } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, of, shareReplay, tap } from 'rxjs';
import { CharacterSchema } from '../models/character.model';
import { abilityModifier, proficiencyBonus } from '../rules';
import { environment } from '../../../environments/environment';

@Injectable({
  providedIn: 'root',
})
export class CharacterStateService {
  private readonly API_URL = `${environment.apiBaseUrl}/characters`;

  // Signals
  readonly characters = signal<CharacterSchema[]>([]);
  readonly activeCharacter = signal<CharacterSchema | null>(null);
  readonly dndEdition = signal<string>('2014 Edition');

  // Computed Modifiers
  readonly filteredCharacters = computed(() => {
    const activeEd = this.dndEdition();
    const is2024Mode = activeEd.includes('2024');
    return this.characters().filter(c => {
      const charEd = c.dnd_edition || '2014 Edition';
      const charIs2024 = charEd.includes('2024');
      return is2024Mode ? charIs2024 : !charIs2024;
    });
  });

  readonly abilityModifiers = computed(() => {
    const stats = this.activeCharacter()?.stats;
    if (!stats) return { STR: 0, DEX: 0, CON: 0, INT: 0, WIS: 0, CHA: 0 };
    return {
      STR: abilityModifier(stats.STR),
      DEX: abilityModifier(stats.DEX),
      CON: abilityModifier(stats.CON),
      INT: abilityModifier(stats.INT),
      WIS: abilityModifier(stats.WIS),
      CHA: abilityModifier(stats.CHA),
    };
  });

  readonly passivePerception = computed(() => {
    const wisMod = this.abilityModifiers().WIS;
    const profBonus = proficiencyBonus(this.activeCharacter());
    const isProf = this.activeCharacter()?.skill_proficiencies?.includes('Perception');
    return 10 + wisMod + (isProf ? profBonus : 0);
  });

  // The vault is fetched once per session; mutations patch the local list from
  // their own response instead of triggering another round trip.
  private loaded = false;
  private inFlight$: Observable<CharacterSchema[]> | null = null;

  constructor(private http: HttpClient) {}

  /**
   * Returns the vault, fetching it only the first time. Concurrent callers share
   * the same in-flight request, so navigating between features costs nothing.
   */
  ensureLoaded(): Observable<CharacterSchema[]> {
    if (this.loaded) {
      return of(this.characters());
    }
    if (!this.inFlight$) {
      this.inFlight$ = this.loadCharacters().pipe(shareReplay(1));
    }
    return this.inFlight$;
  }

  /** Forces a fresh fetch, bypassing the cache. */
  loadCharacters(): Observable<CharacterSchema[]> {
    return this.http.get<CharacterSchema[]>(this.API_URL).pipe(
      tap({
        next: (chars) => {
          this.loaded = true;
          this.inFlight$ = null;
          this.characters.set(chars || []);
          const available = this.filteredCharacters();
          const currentActive = this.activeCharacter();

          if (!currentActive) {
            this.activeCharacter.set(available.length > 0 ? available[0] : null);
          } else {
            const charEd = currentActive.dnd_edition || '2014 Edition';
            const is2024 = this.dndEdition().includes('2024');
            const charIs2024 = charEd.includes('2024');

            if (is2024 !== charIs2024) {
              this.activeCharacter.set(available.length > 0 ? available[0] : null);
            } else {
              const exists = chars?.find(c => c.char_id === currentActive.char_id);
              if (!exists && currentActive.char_id !== 'default_paladin') {
                this.characters.set([currentActive, ...(chars || [])]);
              }
            }
          }
        },
        error: () => {
          this.inFlight$ = null;
          this.characters.set([]);
          this.activeCharacter.set(null);
        }
      })
    );
  }

  /** Clears every cached signal so the next consumer refetches (used on logout). */
  reset(): void {
    this.loaded = false;
    this.inFlight$ = null;
    this.characters.set([]);
    this.activeCharacter.set(null);
  }

  /** Replaces a character in the local list, or appends it when it is new. */
  private upsertCharacter(char: CharacterSchema): void {
    if (!char?.char_id) return;
    const list = this.characters();
    const idx = list.findIndex((c) => c.char_id === char.char_id);
    this.characters.set(
      idx >= 0 ? list.map((c, i) => (i === idx ? char : c)) : [...list, char]
    );
  }

  selectCharacter(id: string): boolean {
    const target = this.characters().find(c => c.char_id === id);
    if (!target) return false;

    const charEd = target.dnd_edition || '2014 Edition';
    const is2024 = this.dndEdition().includes('2024');
    const charIs2024 = charEd.includes('2024');

    if (is2024 === charIs2024) {
      this.activeCharacter.set(target);
      return true;
    }
    return false;
  }

  saveCharacter(char: CharacterSchema): Observable<CharacterSchema> {
    return this.http.post<CharacterSchema>(this.API_URL, char).pipe(
      tap((saved) => {
        this.activeCharacter.set(saved);
        this.upsertCharacter(saved);
      })
    );
  }

  updateCharacter(id: string, char: CharacterSchema): Observable<CharacterSchema> {
    return this.http.put<CharacterSchema>(`${this.API_URL}/${id}`, char).pipe(
      tap((updated) => {
        this.activeCharacter.set(updated);
        this.upsertCharacter(updated);
      })
    );
  }

  deleteCharacter(id: string): Observable<any> {
    return this.http.delete(`${this.API_URL}/${id}`).pipe(
      tap(() => {
        this.characters.set(this.characters().filter((c) => c.char_id !== id));
        // Fall through to whatever hero is left in the active edition, matching
        // the selection the old post-delete refetch used to land on.
        if (this.activeCharacter()?.char_id === id) {
          const available = this.filteredCharacters();
          this.activeCharacter.set(available.length > 0 ? available[0] : null);
        }
      })
    );
  }

  toggleEdition() {
    const current = this.dndEdition();
    const next = current === '2014 Edition' ? '2024 Revision (5.5e)' : '2014 Edition';
    this.dndEdition.set(next);
    document.documentElement.setAttribute(
      'data-edition',
      next.includes('2024') ? '2024' : '2014'
    );

    // Auto switch active character to match the new edition
    const available = this.filteredCharacters();
    const currentActive = this.activeCharacter();

    if (currentActive) {
      const charEd = currentActive.dnd_edition || '2014 Edition';
      const is2024 = next.includes('2024');
      const charIs2024 = charEd.includes('2024');
      if (is2024 !== charIs2024) {
        this.activeCharacter.set(available.length > 0 ? available[0] : null);
      }
    } else if (available.length > 0) {
      this.activeCharacter.set(available[0]);
    }
  }
}
