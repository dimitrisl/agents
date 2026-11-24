import { DestroyRef, Injectable, computed, effect, inject, signal } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, of, shareReplay, tap } from 'rxjs';
import { CharacterSchema } from '../models/character.model';
import { abilityModifier, passivePerceptionOf, proficiencyBonus } from '../rules';
import { environment } from '../../../environments/environment';

/** The hero the player last had open, restored after a page refresh. */
const ACTIVE_CHARACTER_KEY = 'phyrexian_forge_active_char';
const ACTIVE_CHARACTER_SNAPSHOT_KEY = 'phyrexian_forge_active_char_snapshot';
const VAULT_SNAPSHOT_KEY = 'phyrexian_forge_vault_snapshot';
const ACTIVE_EDITION_KEY = 'phyrexian_forge_active_edition';
const USER_STORAGE_KEY = 'currentUser';

interface VaultSnapshot {
  ownerId: string | null;
  savedAt: string;
  characters: CharacterSchema[];
  unreadable?: any[];
  isLegacy?: boolean;
}

@Injectable({
  providedIn: 'root',
})
export class CharacterStateService {
  private readonly API_URL = `${environment.apiBaseUrl}/characters`;
  private readonly destroyRef = inject(DestroyRef);

  // Signals
  readonly characters = signal<CharacterSchema[]>([]);
  readonly unreadableCharacters = signal<any[]>([]);
  readonly activeCharacter = signal<CharacterSchema | null>(null);
  readonly dndEdition = signal<string>(this.readStoredEdition());

  // Computed Modifiers
  readonly filteredCharacters = computed(() => {
    const activeEd = this.dndEdition();
    const is2024Mode = activeEd.includes('2024');
    return this.characters().filter((c: any) => {
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
    return passivePerceptionOf(this.activeCharacter());
  });

  // The vault is fetched once per session; mutations patch the local list from
  // their own response instead of triggering another round trip.
  private loaded = false;
  private inFlight$: Observable<any> | null = null;

  /**
   * 'idle' until the first fetch starts. Lets pages tell "still loading" and
   * "could not load" apart from a genuinely empty vault.
   */
  readonly vaultStatus = signal<'idle' | 'loading' | 'loaded' | 'error'>('idle');
  readonly isOfflineCached = signal<boolean>(false);
  readonly isOnline = signal<boolean>(
    typeof navigator !== 'undefined' ? navigator.onLine !== false : true
  );
  readonly cachedAt = signal<string | null>(null);

  constructor(private http: HttpClient) {
    // Remember whichever hero becomes active, however it got selected
    // (switcher, import, forge), so a refresh doesn't fall back to the first one.
    effect(() => {
      const char = this.activeCharacter();
      const id = char?.char_id;
      if (id && id !== 'default_paladin' && !this.isOfflineCached()) {
        this.storeActiveId(id);
        this.storeActiveSnapshot(char);
      }
    });

    // Persist full vault snapshot whenever live server state updates
    effect(() => {
      const list = this.characters();
      const unreadable = this.unreadableCharacters();
      if (this.loaded && !this.isOfflineCached()) {
        this.storeVaultSnapshot(list, unreadable);
      }
    });

    effect(() => {
      const edition = this.dndEdition();
      this.storeEdition(edition);
      if (typeof document !== 'undefined' && document.documentElement) {
        document.documentElement.setAttribute(
          'data-edition',
          edition.includes('2024') ? '2024' : '2014'
        );
      }
    });

    if (typeof window !== 'undefined' && typeof window.addEventListener === 'function') {
      const onOnline = () => {
        this.isOnline.set(true);
        if (this.isOfflineCached() || this.vaultStatus() === 'error') {
          this.loadCharacters().subscribe({ error: () => {} });
        }
      };
      const onOffline = () => {
        this.isOnline.set(false);
      };
      window.addEventListener('online', onOnline);
      window.addEventListener('offline', onOffline);
      this.destroyRef.onDestroy(() => {
        window.removeEventListener('online', onOnline);
        window.removeEventListener('offline', onOffline);
      });
    }
  }

  /**
   * Returns the vault, fetching it only the first time. Concurrent callers share
   * the same in-flight request, so navigating between features costs nothing.
   */
  ensureLoaded(): Observable<any> {
    if (this.loaded) {
      return of(this.characters());
    }
    if (!this.inFlight$) {
      this.inFlight$ = this.loadCharacters().pipe(shareReplay(1));
    }
    return this.inFlight$;
  }

  /** Forces a fresh fetch, bypassing the cache. */
  loadCharacters(): Observable<any> {
    // A background refresh keeps showing the vault we already have.
    if (this.vaultStatus() !== 'loaded') this.vaultStatus.set('loading');
    return this.http.get<any>(this.API_URL).pipe(
      tap({
        next: (resp) => {
          this.loaded = true;
          this.vaultStatus.set('loaded');
          this.isOfflineCached.set(false);
          this.isOnline.set(true);
          this.cachedAt.set(null);
          this.inFlight$ = null;
          const chars = resp.characters || [];
          const unreadable = resp.unreadable || [];
          this.unreadableCharacters.set(unreadable);
          this.characters.set(chars);
          this.storeVaultSnapshot(chars, unreadable);
          const available = this.filteredCharacters();
          const currentActive = this.activeCharacter();

          if (!currentActive) {
            this.activeCharacter.set(this.preferredActive(available));
          } else {
            const charEd = currentActive.dnd_edition || '2014 Edition';
            const is2024 = this.dndEdition().includes('2024');
            const charIs2024 = charEd.includes('2024');

            if (is2024 !== charIs2024) {
              this.activeCharacter.set(this.preferredActive(available));
            } else {
              const exists = chars?.find((c: any) => c.char_id === currentActive.char_id);
              if (exists) {
                this.activeCharacter.set(exists);
              } else if (currentActive.char_id !== 'default_paladin') {
                this.characters.set([currentActive, ...(chars || [])]);
              }
            }
          }
        },
        error: (err) => {
          this.inFlight$ = null;
          const status = err?.status;
          if (status === 401 || status === 403) {
            this.loaded = false;
            this.vaultStatus.set('error');
            this.isOfflineCached.set(false);
            this.cachedAt.set(null);
            this.characters.set([]);
            this.activeCharacter.set(null);
            return;
          }
          if (status === 0 && (typeof navigator === 'undefined' || navigator.onLine === false)) {
            this.isOnline.set(false);
          }
          const snapshot = this.readVaultSnapshot();
          if (snapshot && snapshot.characters.length > 0) {
            this.vaultStatus.set('loaded');
            this.isOfflineCached.set(true);
            this.cachedAt.set(snapshot.savedAt || null);
            this.unreadableCharacters.set(snapshot.unreadable || []);
            this.characters.set(snapshot.characters);
            const available = this.filteredCharacters();
            const currentActive = this.activeCharacter();
            if (currentActive && available.some((c) => c.char_id === currentActive.char_id)) {
              const matched = available.find((c) => c.char_id === currentActive.char_id) || null;
              this.activeCharacter.set(matched);
            } else {
              const fallbackPool =
                available.length > 0 ? available : snapshot.isLegacy ? snapshot.characters : [];
              this.activeCharacter.set(this.preferredActive(fallbackPool));
            }
          } else {
            this.vaultStatus.set('error');
            this.isOfflineCached.set(false);
            this.cachedAt.set(null);
            this.characters.set([]);
            this.activeCharacter.set(null);
          }
        }
      })
    );
  }

  /**
   * The remembered hero if it is in this vault (and edition), else the first one.
   * Checking against the vault means another account in the same browser never
   * inherits it.
   */
  private preferredActive(available: CharacterSchema[]): CharacterSchema | null {
    const remembered = this.readActiveId();
    return available.find((c) => c.char_id === remembered) ?? available[0] ?? null;
  }

  private readStoredEdition(): string {
    try {
      const saved = localStorage.getItem(ACTIVE_EDITION_KEY);
      if (saved && saved.includes('2024')) return '2024 Revision (5.5e)';
      if (saved) return '2014 Edition';
    } catch {
      // Ignore storage access restrictions
    }
    return '2014 Edition';
  }

  private storeEdition(edition: string): void {
    try {
      localStorage.setItem(ACTIVE_EDITION_KEY, edition);
    } catch {
      // Ignore storage access restrictions
    }
  }

  private readActiveId(): string | null {
    try {
      return localStorage.getItem(ACTIVE_CHARACTER_KEY);
    } catch {
      return null; // storage blocked (private mode, policies): just pick the first hero
    }
  }

  private storeActiveId(id: string): void {
    try {
      localStorage.setItem(ACTIVE_CHARACTER_KEY, id);
    } catch {
      // Not remembering the hero is harmless.
    }
  }

  private readCurrentUserId(): string | null {
    try {
      const raw = localStorage.getItem(USER_STORAGE_KEY);
      if (!raw) return null;
      const parsed = JSON.parse(raw) as { id?: unknown };
      return typeof parsed?.id === 'string' ? parsed.id : null;
    } catch {
      return null;
    }
  }

  private readActiveSnapshot(): CharacterSchema | null {
    try {
      const raw = localStorage.getItem(ACTIVE_CHARACTER_SNAPSHOT_KEY);
      if (!raw) return null;
      const parsed = JSON.parse(raw) as CharacterSchema;
      return parsed && typeof parsed.char_id === 'string' ? parsed : null;
    } catch {
      return null;
    }
  }

  private readVaultSnapshot(): VaultSnapshot | null {
    const currentUserId = this.readCurrentUserId();
    try {
      const raw = localStorage.getItem(VAULT_SNAPSHOT_KEY);
      if (raw) {
        const parsed = JSON.parse(raw) as Partial<VaultSnapshot>;
        const ownerMismatch = currentUserId
          ? parsed.ownerId !== currentUserId
          : Boolean(parsed.ownerId);
        if (ownerMismatch) {
          this.clearActiveSnapshot();
          return null;
        }
        if (Array.isArray(parsed.characters)) {
          const valid = parsed.characters.filter((c) => c && typeof c.char_id === 'string');
          return {
            ownerId: typeof parsed.ownerId === 'string' ? parsed.ownerId : null,
            savedAt: typeof parsed.savedAt === 'string' ? parsed.savedAt : '',
            characters: valid,
            unreadable: Array.isArray(parsed.unreadable) ? parsed.unreadable : [],
            isLegacy: false,
          };
        }
      }
    } catch {
      // Ignore corrupt vault snapshot; fall back to single snapshot check below.
    }

    const legacy = this.readActiveSnapshot();
    if (!legacy) return null;
    const legacyOwner = (legacy as any).owner_id ?? (legacy as any).user_id;
    const legacyMismatch = currentUserId
      ? typeof legacyOwner === 'string' && legacyOwner !== currentUserId
      : typeof legacyOwner === 'string';
    if (legacyMismatch) {
      this.clearActiveSnapshot();
      return null;
    }
    return {
      ownerId: typeof legacyOwner === 'string' ? legacyOwner : currentUserId,
      savedAt: '',
      characters: [legacy],
      unreadable: [],
      isLegacy: true,
    };
  }

  private storeActiveSnapshot(char: CharacterSchema | null): void {
    const ownerId = this.readCurrentUserId();
    if (!char?.char_id || !ownerId) return;
    try {
      localStorage.setItem(
        ACTIVE_CHARACTER_SNAPSHOT_KEY,
        JSON.stringify({ ...char, owner_id: (char as any).owner_id ?? ownerId })
      );
    } catch {
      // Storage quota/private mode errors are non-fatal for offline cache.
    }
  }

  private storeVaultSnapshot(characters: CharacterSchema[], unreadable: any[] = []): void {
    const ownerId = this.readCurrentUserId();
    if (!ownerId) return;
    try {
      const snapshot: VaultSnapshot = {
        ownerId,
        savedAt: new Date().toISOString(),
        characters,
        unreadable,
      };
      localStorage.setItem(VAULT_SNAPSHOT_KEY, JSON.stringify(snapshot));
    } catch {
      // Storage quota/private mode errors are non-fatal for offline cache.
    }
  }

  private clearActiveSnapshot(): void {
    try {
      localStorage.removeItem(ACTIVE_CHARACTER_SNAPSHOT_KEY);
      localStorage.removeItem(VAULT_SNAPSHOT_KEY);
    } catch {
      // Ignore storage errors.
    }
  }

  /** Clears every cached signal so the next consumer refetches (used on logout). */
  reset(): void {
    this.loaded = false;
    this.vaultStatus.set('idle');
    this.isOfflineCached.set(false);
    this.cachedAt.set(null);
    this.clearActiveSnapshot();
    try {
      localStorage.removeItem(ACTIVE_CHARACTER_KEY);
      localStorage.removeItem(ACTIVE_EDITION_KEY);
    } catch {
      // Ignore storage errors.
    }
    this.inFlight$ = null;
    this.characters.set([]);
    this.activeCharacter.set(null);
  }

  /** Replaces a character in the local list, or appends it when it is new. */
  upsertCharacter(char: CharacterSchema): void {
    if (!char?.char_id) return;
    const list = this.characters();
    const idx = list.findIndex((c) => c.char_id === char.char_id);
    this.characters.set(
      idx >= 0 ? list.map((c, i) => (i === idx ? char : c)) : [...list, char]
    );
  }

  selectCharacter(id: string): boolean {
    const target = this.characters().find((c: any) => c.char_id === id);
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

  applyShortRest(
    id: string,
    payload: {
      dice_to_spend: number;
      die_size?: number;
      hp_healed: number;
      arcane_recovery_slots?: Record<string, number>;
      natural_recovery_slots?: Record<string, number>;
      harness_divine_power_slot?: number | null;
      expected_version?: number;
    }
  ): Observable<CharacterSchema> {
    return this.http.post<CharacterSchema>(`${this.API_URL}/${id}/short-rest`, payload).pipe(
      tap((updated) => {
        this.activeCharacter.set(updated);
        this.upsertCharacter(updated);
      })
    );
  }

  applyLongRest(
    id: string,
    payload: { expected_version?: number } = {}
  ): Observable<CharacterSchema> {
    return this.http.post<CharacterSchema>(`${this.API_URL}/${id}/long-rest`, payload).pipe(
      tap((updated) => {
        this.activeCharacter.set(updated);
        this.upsertCharacter(updated);
      })
    );
  }

  addHomebrewToCharacter(charId: string, itemId: string): Observable<CharacterSchema> {
    return this.http.post<CharacterSchema>(`${this.API_URL}/${charId}/homebrew/${itemId}`, {}).pipe(
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
