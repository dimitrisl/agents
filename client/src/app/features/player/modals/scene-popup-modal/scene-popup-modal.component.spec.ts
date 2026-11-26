import { ComponentFixture, TestBed } from '@angular/core/testing';
import { HttpClientTestingModule, HttpTestingController } from '@angular/common/http/testing';
import { ScenePopupModalComponent } from './scene-popup-modal.component';

describe('ScenePopupModalComponent', () => {
  let fixture: ComponentFixture<ScenePopupModalComponent>;
  let component: ScenePopupModalComponent;
  let httpMock: HttpTestingController;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [HttpClientTestingModule, ScenePopupModalComponent],
    }).compileComponents();

    fixture = TestBed.createComponent(ScenePopupModalComponent);
    component = fixture.componentInstance;
    httpMock = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    httpMock.verify();
  });

  it('loads protected campaign asset images as blob URLs and revokes them when dismissed', () => {
    const createSpy = jest.fn().mockReturnValue('blob:http://localhost/handout-1');
    const revokeSpy = jest.fn();
    const origCreate = URL.createObjectURL;
    const origRevoke = URL.revokeObjectURL;
    (URL as any).createObjectURL = createSpy;
    (URL as any).revokeObjectURL = revokeSpy;

    try {
      fixture.componentRef.setInput('popup', {
        scene_id: 'sc-1',
        scene_title: 'Crimson Tavern',
        card_id: 'card-1',
        title: 'Lord Veylan',
        image_url: '/api/v1/campaigns/Test%20Camp/assets/veylan.png',
        caption: 'He removes his hood slowly.',
        target_mode: 'selected',
        target_char_ids: ['char-1'],
      });
      fixture.detectChanges();

      const req = httpMock.expectOne(
        (r) => r.url.endsWith('/campaigns/Test%20Camp/assets/veylan.png')
      );
      expect(req.request.responseType).toBe('blob');
      req.flush(new Blob(['img'], { type: 'image/png' }));
      fixture.detectChanges();

      const img = document.querySelector('[data-testid="player-scene-popup-image"]') as HTMLImageElement;
      expect(img?.getAttribute('src')).toBe('blob:http://localhost/handout-1');
      expect(document.body.textContent).toContain('Lord Veylan');
      expect(document.body.textContent).toContain('He removes his hood slowly.');
      expect(document.body.textContent).toContain('Private Reveal');

      let closeCount = 0;
      component.dismissed.subscribe(() => closeCount++);
      const closeBtn = document.querySelector('[data-testid="player-scene-popup-close"]') as HTMLButtonElement;
      closeBtn.click();
      expect(closeCount).toBe(1);

      fixture.destroy();
      expect(revokeSpy).toHaveBeenCalledWith('blob:http://localhost/handout-1');
    } finally {
      (URL as any).createObjectURL = origCreate;
      (URL as any).revokeObjectURL = origRevoke;
    }
  });
});
