import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, catchError, map, of, switchMap } from 'rxjs';
import { environment } from '../../../environments/environment';
import { CharacterSchema } from '../models/character.model';
import { CharacterStateService } from './character-state.service';

export type ImportSource = 'pdf' | 'dndbeyond' | 'foundry';

/** The saved hero plus anything the importer could not map cleanly. */
export type ImportedCharacter = CharacterSchema & { warnings?: string[] };

/**
 * Imports a hero from a 5e PDF, D&D Beyond or Foundry VTT.
 *
 * Every import is saved by the API as a NEW character (fresh char_id) — nothing
 * already in the vault is overwritten. On success the vault is refreshed and the
 * imported hero becomes the active one.
 */
@Injectable({ providedIn: 'root' })
export class CharacterImportService {
  private readonly api = `${environment.apiBaseUrl}/characters`;

  constructor(
    private http: HttpClient,
    private charState: CharacterStateService
  ) {}

  importPdf(file: File): Observable<ImportedCharacter> {
    return this.activate(this.http.post<ImportedCharacter>(`${this.api}/import-pdf`, this.form(file)));
  }

  importDndBeyond(urlOrId: string): Observable<ImportedCharacter> {
    return this.activate(
      this.http.post<ImportedCharacter>(`${this.api}/import-dndbeyond`, { url_or_id: urlOrId.trim() })
    );
  }

  importFoundry(file: File): Observable<ImportedCharacter> {
    return this.activate(this.http.post<ImportedCharacter>(`${this.api}/import-foundry`, this.form(file)));
  }

  private form(file: File): FormData {
    const formData = new FormData();
    formData.append('file', file);
    return formData;
  }

  /** Reload the vault so the new hero is listed, then make it the active one. */
  private activate(request: Observable<ImportedCharacter>): Observable<ImportedCharacter> {
    return request.pipe(
      switchMap((imported) =>
        this.charState.loadCharacters().pipe(
          // The hero is already saved; a failed refresh must not read as a failed import.
          catchError(() => of(null)),
          map(() => {
            this.charState.activeCharacter.set(imported);
            return imported;
          })
        )
      )
    );
  }
}
