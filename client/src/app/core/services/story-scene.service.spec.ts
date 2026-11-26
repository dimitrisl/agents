import { TestBed } from '@angular/core/testing';
import { HttpClientTestingModule, HttpTestingController } from '@angular/common/http/testing';
import { StorySceneService } from './story-scene.service';
import { environment } from '../../../environments/environment';

describe('StorySceneService', () => {
  let service: StorySceneService;
  let httpMock: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      imports: [HttpClientTestingModule],
      providers: [StorySceneService],
    });
    service = TestBed.inject(StorySceneService);
    httpMock = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    httpMock.verify();
  });

  it('encodes campaign names cleanly across CRUD, cast, and dismiss endpoints', () => {
    const camp = 'Sunken Vault & Ruins';
    const enc = encodeURIComponent(camp);

    service.listScenes(camp).subscribe();
    const listReq = httpMock.expectOne(`${environment.apiBaseUrl}/campaigns/${enc}/story-scenes`);
    expect(listReq.request.method).toBe('GET');
    listReq.flush([]);

    service
      .castCard(camp, 'sc-1', {
        card_id: 'c-1',
        target_mode: 'selected',
        target_char_ids: ['hero-2'],
      })
      .subscribe();
    const castReq = httpMock.expectOne(
      `${environment.apiBaseUrl}/campaigns/${enc}/story-scenes/sc-1/cast`
    );
    expect(castReq.request.method).toBe('POST');
    expect(castReq.request.body).toEqual({
      card_id: 'c-1',
      target_mode: 'selected',
      target_char_ids: ['hero-2'],
    });
    castReq.flush({ success: true, message: 'ok' });

    service.dismissPopup(camp, { target_mode: 'all', target_char_ids: [] }).subscribe();
    const disReq = httpMock.expectOne(
      `${environment.apiBaseUrl}/campaigns/${enc}/story-scenes/dismiss`
    );
    expect(disReq.request.method).toBe('POST');
    disReq.flush({ success: true, message: 'ok' });
  });
});
