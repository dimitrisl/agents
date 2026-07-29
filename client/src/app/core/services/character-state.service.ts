import { Injectable, signal, computed } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, tap } from 'rxjs';
import { CharacterSchema, StatBlock } from '../models/character.model';

@Injectable({
  providedIn: 'root',
})
export class CharacterStateService {
  private readonly API_URL = 'http://localhost:8000/api/v1/characters';

  // Signals
  readonly characters = signal<CharacterSchema[]>([]);
  readonly activeCharacter = signal<CharacterSchema | null>(null);
  readonly dndEdition = signal<string>('2014 Edition');

  // Computed Modifiers
  readonly abilityModifiers = computed(() => {
    const stats = this.activeCharacter()?.stats;
    if (!stats) return { STR: 0, DEX: 0, CON: 0, INT: 0, WIS: 0, CHA: 0 };
    return {
      STR: Math.floor((stats.STR - 10) / 2),
      DEX: Math.floor((stats.DEX - 10) / 2),
      CON: Math.floor((stats.CON - 10) / 2),
      INT: Math.floor((stats.INT - 10) / 2),
      WIS: Math.floor((stats.WIS - 10) / 2),
      CHA: Math.floor((stats.CHA - 10) / 2),
    };
  });

  readonly passivePerception = computed(() => {
    const wisMod = this.abilityModifiers().WIS;
    const profBonus = this.activeCharacter()?.proficiency_bonus || 2;
    const isProf = this.activeCharacter()?.skill_proficiencies?.includes('Perception');
    return 10 + wisMod + (isProf ? profBonus : 0);
  });

  constructor(private http: HttpClient) {}

  loadCharacters(): Observable<CharacterSchema[]> {
    return this.http.get<CharacterSchema[]>(this.API_URL).pipe(
      tap((chars) => {
        this.characters.set(chars);
        if (chars.length > 0 && !this.activeCharacter()) {
          this.activeCharacter.set(chars[0]);
        }
      })
    );
  }

  saveCharacter(char: CharacterSchema): Observable<CharacterSchema> {
    return this.http.post<CharacterSchema>(this.API_URL, char).pipe(
      tap((saved) => {
        this.activeCharacter.set(saved);
        this.loadCharacters().subscribe();
      })
    );
  }

  updateCharacter(id: string, char: CharacterSchema): Observable<CharacterSchema> {
    return this.http.put<CharacterSchema>(`${this.API_URL}/${id}`, char).pipe(
      tap((updated) => {
        this.activeCharacter.set(updated);
        this.loadCharacters().subscribe();
      })
    );
  }

  deleteCharacter(id: string): Observable<any> {
    return this.http.delete(`${this.API_URL}/${id}`).pipe(
      tap(() => {
        this.activeCharacter.set(null);
        this.loadCharacters().subscribe();
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
  }
}
