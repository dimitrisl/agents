import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { VttGridComponent } from './vtt-grid.component';
import { WebSocketService } from '../../../core/services/websocket.service';
import { VTTScene, VTTSceneHistory } from '../../../core/models/vtt.model';
import { environment } from '../../../../environments/environment';

describe('VttGridComponent', () => {
  let component: VttGridComponent;
  let http: HttpTestingController;
  let wsService: WebSocketService;

  const MOCK_SCENE: VTTScene = {
    scene_id: 'sc_1',
    campaign_name: 'TestCampaign',
    name: 'Dungeon Level 1',
    dm_notes: 'Secret door behind altar',
    grid: { width: 30, height: 30, cell_size: 50 },
    tokens: [],
    fog: { enabled: true, revealed: [0, 1, 2] },
    order: 0,
    is_active_scene: true,
  };

  const MOCK_HISTORY: VTTSceneHistory = {
    campaign_name: 'TestCampaign',
    scene_id: 'sc_1',
    scene_name: 'Dungeon Level 1',
    activated_at: '2026-10-24T12:00:00Z',
    activated_by_user_id: 'dm_user_1',
  };

  beforeEach(() => {
    TestBed.configureTestingModule({
      imports: [VttGridComponent],
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        WebSocketService,
      ],
    });

    http = TestBed.inject(HttpTestingController);
    wsService = TestBed.inject(WebSocketService);
    const fixture = TestBed.createComponent(VttGridComponent);
    component = fixture.componentInstance;
    component.campaignName = 'TestCampaign';
    component.role = 'dm';
  });

  afterEach(() => {
    http.verify();
  });

  it('initializes with default scene modal tab as scenes', () => {
    expect(component.sceneModalTab).toBe('scenes');
  });

  it('switches to history tab and loads scene history', () => {
    component.setSceneModalTab('history');
    expect(component.sceneModalTab).toBe('history');

    const req = http.expectOne(`${environment.apiBaseUrl}/campaigns/TestCampaign/scenes/history`);
    expect(req.request.method).toBe('GET');
    req.flush([MOCK_HISTORY]);

    expect(component.sceneHistory.length).toBe(1);
    expect(component.sceneHistory[0].scene_name).toBe('Dungeon Level 1');
  });

  it('toggles scene notes editor and saves scene notes', () => {
    component.toggleSceneNotes(MOCK_SCENE);
    expect(component.expandedSceneNotesId).toBe('sc_1');

    MOCK_SCENE.dm_notes = 'Updated trap location';
    component.saveSceneNotes(MOCK_SCENE);

    const putReq = http.expectOne(`${environment.apiBaseUrl}/campaigns/TestCampaign/scenes/sc_1`);
    expect(putReq.request.method).toBe('PUT');
    expect(putReq.request.body).toEqual({
      name: 'Dungeon Level 1',
      dm_notes: 'Updated trap location',
    });
    putReq.flush({ ...MOCK_SCENE, dm_notes: 'Updated trap location' });

    // Expect scenes list to be reloaded after save
    const getReq = http.expectOne(`${environment.apiBaseUrl}/campaigns/TestCampaign/scenes`);
    getReq.flush([MOCK_SCENE]);

    expect(component.expandedSceneNotesId).toBeNull();
  });

  it('supports rectangle fog selection modes and sends rect payload', () => {
    jest.spyOn(wsService, 'sendVttFogReveal').mockImplementation();
    jest.spyOn(wsService, 'sendVttFogHide').mockImplementation();

    component.setFogBrush('rect_reveal');
    expect(component.fogBrushMode).toBe('rect_reveal');

    // Simulate mouse drag rectangle: from (2, 3) to (5, 7)
    component.rectStartCol = 2;
    component.rectStartRow = 3;
    component.rectCurrentCol = 5;
    component.rectCurrentRow = 7;
    (component as any).isPaintingFog = true;

    component.onFogMouseUp();

    expect(wsService.sendVttFogReveal).toHaveBeenCalledWith(undefined, {
      x: 2,
      y: 3,
      w: 4,
      h: 5,
    });
    expect(component.rectStartCol).toBeNull();

    // Box hide mode
    component.setFogBrush('rect_hide');
    component.rectStartCol = 4;
    component.rectStartRow = 4;
    component.rectCurrentCol = 1;
    component.rectCurrentRow = 2;
    (component as any).isPaintingFog = true;

    component.onFogMouseUp();

    expect(wsService.sendVttFogHide).toHaveBeenCalledWith(undefined, {
      x: 1,
      y: 2,
      w: 4,
      h: 3,
    });
  });
});
