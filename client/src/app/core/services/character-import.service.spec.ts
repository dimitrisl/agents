import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { CharacterImportService } from './character-import.service';
import { CharacterStateService } from './character-state.service';

describe('CharacterImportService', () => {
  let service: CharacterImportService;
  let charState: CharacterStateService;
  let http: HttpTestingController;

  const EXISTING: any = { char_id: 'edrann', char_name: 'Edrann', dnd_edition: '2014 Edition' };
  const IMPORTED: any = { char_id: 'new-uuid', char_name: 'Valeros', dnd_edition: '2014 Edition', warnings: [] };

  beforeEach(() => {
    TestBed.configureTestingModule({ providers: [provideHttpClient(), provideHttpClientTesting()] });
    service = TestBed.inject(CharacterImportService);
    charState = TestBed.inject(CharacterStateService);
    http = TestBed.inject(HttpTestingController);
    charState.characters.set([EXISTING]);
    charState.activeCharacter.set(EXISTING);
  });

  afterEach(() => http.verify());

  it('posts the PDF, reloads the vault and makes the NEW hero active, keeping the old one', () => {
    let result: any;
    service.importPdf(new File(['%PDF'], 'sheet.pdf')).subscribe((r) => (result = r));

    const post = http.expectOne((r) => r.method === 'POST' && r.url.endsWith('/characters/import-pdf'));
    expect(post.request.body instanceof FormData).toBe(true);
    post.flush(IMPORTED);

    http.expectOne((r) => r.method === 'GET' && r.url.endsWith('/characters')).flush({ characters: [EXISTING, IMPORTED] });

    expect(result.char_id).toBe('new-uuid');
    expect(charState.activeCharacter()?.char_id).toBe('new-uuid');
    expect(charState.characters().map((c) => c.char_id)).toEqual(['edrann', 'new-uuid']);
  });

  it('sends a trimmed D&D Beyond link', () => {
    service.importDndBeyond('  https://www.dndbeyond.com/characters/1  ').subscribe();
    const post = http.expectOne((r) => r.url.endsWith('/characters/import-dndbeyond'));
    expect(post.request.body).toEqual({ url_or_id: 'https://www.dndbeyond.com/characters/1' });
    post.flush(IMPORTED);
    http.expectOne((r) => r.url.endsWith('/characters')).flush({ characters: [EXISTING, IMPORTED] });
  });

  it('still succeeds when the import saved but the vault refresh failed', () => {
    let result: any;
    let failed = false;
    service.importFoundry(new File(['{}'], 'actor.json')).subscribe({ next: (r) => (result = r), error: () => (failed = true) });

    http.expectOne((r) => r.url.endsWith('/characters/import-foundry')).flush(IMPORTED);
    http.expectOne((r) => r.url.endsWith('/characters')).flush(null, { status: 500, statusText: 'Server Error' });

    expect(failed).toBe(false);
    expect(result.char_id).toBe('new-uuid');
    expect(charState.activeCharacter()?.char_id).toBe('new-uuid');
  });
});
