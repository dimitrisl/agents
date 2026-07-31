import { Injectable, signal, computed } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, tap } from 'rxjs';
import { CharacterSchema } from '../models/character.model';
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

  // Default Fallback Hero if DB is empty
  private readonly defaultHero: CharacterSchema = {
    char_id: 'default_paladin',
    char_name: 'Sir Valeros',
    char_portrait: 'https://image.pollinations.ai/prompt/sir%20valeros%20dnd%20paladin%20knight%20in%20shining%20armor%20cinematic%20portrait?width=300&height=300&nologo=true',
    char_class: 'Paladin',
    subclass: 'Oath of Devotion',
    char_level: 5,
    race: 'Human',
    background: 'Soldier',
    alignment: 'Lawful Good',
    backstory: 'A valiant paladin who swore an oath of devotion to protect the innocent.',
    armor_class: 18,
    hp_max: 44,
    hp_current: 44,
    speed: 30,
    proficiency_bonus: 3,
    stats: { STR: 18, DEX: 12, CON: 15, INT: 10, WIS: 14, CHA: 16 },
    saving_throws: ['WIS', 'CHA'],
    skill_proficiencies: ['Athletics', 'Intimidation', 'Persuasion'],
    weapons: [
      { name: 'Longsword', attack_bonus: '+7', damage_dice: '1d8+4 slashing' }
    ],
    equipment: [
      { name: 'Chain mail', equipped: true },
      { name: 'Shield', equipped: true }
    ],
    features_traits: [
      { name: 'Divine Smite', description: 'Expend a spell slot to deal radiant damage.' }
    ]
  };

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
      tap({
        next: (chars) => {
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
          this.characters.set([]);
          this.activeCharacter.set(null);
        }
      })
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
